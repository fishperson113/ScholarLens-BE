import os
from typing import List, Optional
from datetime import date, timedelta

from elasticsearch import Elasticsearch

from services.es_svc import search_keyword, filter_advanced
from .types import (
    FilterInput,
    InterFieldOperator,
    ScholarshipSource,
    SearchHit,
    SearchResult,
    SortOrder,
)


ES_HOST = os.getenv("ELASTICSEARCH_HOST")
ES_USER = os.getenv("ELASTIC_USER")
ES_PASS = os.getenv("ELASTIC_PASSWORD")


def _es_client() -> Elasticsearch:
    return Elasticsearch(
        hosts=[ES_HOST],
        basic_auth=(ES_USER, ES_PASS),
        verify_certs=False,
        max_retries=30,
        retry_on_timeout=True,
        request_timeout=30,
    )


def search_es(
    *,
    collection: str,
    q: Optional[str] = None,
    filters: Optional[List[FilterInput]] = None,
    inter_field_operator: InterFieldOperator = InterFieldOperator.AND,
    sort_by_deadline: bool = True,
    sort_order: SortOrder = SortOrder.ASC,
    size: int = 10,
    offset: int = 0,
) -> SearchResult:
    es = _es_client()
    try:
        def _to_scholarship_source(src: dict) -> ScholarshipSource:
            return ScholarshipSource(
                name=src.get("name"),
                university=src.get("university"),
                open_time=src.get("open_time"),
                close_time=src.get("close_time"),
                amount=src.get("amount"),
                field_of_study=src.get("field_of_study"),
                url=src.get("url"),
            )

        def _combine_values(f: FilterInput):
            vals = []
            if f.string_values:
                vals.extend([str(v) for v in f.string_values])
            if f.int_values:
                vals.extend([str(v) for v in f.int_values])
            if f.float_values:
                vals.extend([str(v) for v in f.float_values])
            return vals

        filters_as_dicts = [
            {
                "field": f.field,
                "values": _combine_values(f),
                "operator": f.operator.value,
            }
            for f in (filters or [])
        ]

        # Case 1: No query, no filters - return all sorted by deadline
        if not q and not filters_as_dicts:
            query_body = {"bool": {}}
            if collection:
                query_body["bool"]["filter"] = [{"term": {"collection": collection}}]
            
            if not query_body["bool"]:
                query_body = {"match_all": {}}
            
            search_params = {
                "index": collection,
                "query": query_body,
                "size": size * 5 if sort_by_deadline else size,  # Fetch more for sorting
                "from_": 0 if sort_by_deadline else offset,
            }
            
            result = es.search(**search_params)
            
            hits = [
                {
                    "id": h["_id"],
                    "score": h["_score"],
                    "source": h["_source"]
                }
                for h in result["hits"]["hits"]
            ]
            
            # Sort by deadline on server side if needed
            if sort_by_deadline and hits:
                def parse_date(date_str):
                    """Parse DD/MM/YYYY to comparable date"""
                    if not date_str:
                        return date.max if sort_order.value == "asc" else date.min
                    try:
                        if '/' in date_str:
                            day, month, year = date_str.split('/')
                            return date(int(year), int(month), int(day))
                        return date.fromisoformat(date_str)
                    except:
                        return date.max if sort_order.value == "asc" else date.min
                
                hits.sort(
                    key=lambda x: parse_date(x.get("source", {}).get("close_time")),
                    reverse=(sort_order.value == "desc")
                )
                
                # Apply pagination after sorting
                hits = hits[offset:offset + size]
            
            return SearchResult(
                total=result["hits"]["total"]["value"],
                items=[
                    SearchHit(
                        id=h["id"],
                        score=h["score"],
                        source=_to_scholarship_source(h["source"]) if h.get("source") else None,
                    )
                    for h in hits
                ],
            )

        # Case 2: keyword-only
        if q and not filters_as_dicts:
            result = search_keyword(
                client=es,
                q=q,
                index=collection,
                size=size,
                offset=offset,
                collection=collection,
            )
            return SearchResult(
                total=result.get("total", 0),
                items=[
                    SearchHit(
                        id=i["id"],
                        score=i["score"],
                        source=_to_scholarship_source(i["source"]) if i.get("source") else None,
                    )
                for i in result.get("items", [])
                ],
            )

        # Case 3: filters-only
        if filters_as_dicts and not q:
            result = filter_advanced(
                client=es,
                index=collection,
                collection=collection,
                filters=filters_as_dicts,
                inter_field_operator=inter_field_operator.value,
                size=size,
                offset=offset,
                sort_field="close_time" if sort_by_deadline else None,
                sort_order=sort_order.value,
            )
            return SearchResult(
                total=result.get("total", 0),
                items=[
                    SearchHit(
                        id=i["id"],
                        score=i["score"],
                        source=_to_scholarship_source(i["source"]) if i.get("source") else None,
                    )
                for i in result.get("items", [])
                ],
            )

        # Case 4: both keyword and filters — intersect results, preserve keyword ranking
        kw = search_keyword(
            client=es,
            q=q or "",
            index=collection,
            size=size,
            offset=offset,
            collection=collection,
        )
        flt = filter_advanced(
            client=es,
            index=collection,
            collection=collection,
            filters=filters_as_dicts,
            inter_field_operator=inter_field_operator.value,
            size=size,
            offset=offset,
            sort_field="close_time" if sort_by_deadline else None,
            sort_order=sort_order.value,
        )

        flt_ids = {i["id"] for i in flt.get("items", [])}
        merged_items = [
            SearchHit(
                id=i["id"],
                score=i["score"],
                source=_to_scholarship_source(i["source"]) if i.get("source") else None,
            )
            for i in kw.get("items", [])
            if i["id"] in flt_ids
        ]
        return SearchResult(total=len(merged_items), items=merged_items)
    finally:
        es.close()

