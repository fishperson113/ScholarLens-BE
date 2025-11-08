import os
from typing import List, Optional

from elasticsearch import Elasticsearch

from services.es_svc import search_keyword, filter_advanced
from .types import (
    FilterInput,
    InterFieldOperator,
    ScholarshipSource,
    SearchHit,
    SearchResult,
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
    size: int = 10,
    offset: int = 0,
) -> SearchResult:
    es = _es_client()
    try:
        def _to_scholarship_source(src: dict) -> ScholarshipSource:
            # Map ES document keys to normalized ScholarshipSource fields
            return ScholarshipSource(
                name=src.get("Scholarship_Name"),
                country=src.get("Country"),
                start_date=src.get("Start_Date"),
                end_date=src.get("End_Date"),
                amount=src.get("Funding_Level"),
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

        # Case 1: keyword-only
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

        # Case 2: filters-only
        if filters_as_dicts and not q:
            result = filter_advanced(
                client=es,
                index=collection,
                collection=collection,
                filters=filters_as_dicts,
                inter_field_operator=inter_field_operator.value,
                size=size,
                offset=offset,
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

        # Case 3: both keyword and filters — intersect results, preserve keyword ranking
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
