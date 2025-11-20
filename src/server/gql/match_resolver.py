import os
from typing import List, Optional, Dict, Any

from elasticsearch import Elasticsearch

from services.es_svc import filter_advanced
from .types import (
    UserProfileInput,
    MatchItem,
    MatchResult,
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


def _to_summary_fields(src: dict):
    return {
        "summary_name": src.get("name"),
        "summary_start_date": src.get("open_time"),
        "summary_end_date": src.get("close_time"),
        "summary_amount": src.get("amount"),
        "summary_url": src.get("url"),
    }

def _build_matched_fields(profile: Optional[UserProfileInput], source: Dict[str, Any]) -> List[str]:
    """
    Build list of reasons why this scholarship matched the user profile.
    Based on actual scholarship fields: name, university, open_time, close_time, amount, field_of_study, url
    """
    reasons: List[str] = []

    if not profile:
        return reasons

    # Field of study match
    if profile.field_of_study:
        scholarship_fields = source.get("field_of_study", "")
        if scholarship_fields and profile.field_of_study.lower() in scholarship_fields.lower():
            reasons.append(f"field_of_study_match:{profile.field_of_study}")

    # University match
    if profile.university:
        scholarship_uni = source.get("university", "")
        if scholarship_uni:
            for desired_uni in profile.university:
                if desired_uni.lower() in scholarship_uni.lower():
                    reasons.append(f"university_match:{desired_uni}")
                    break

    # Name/keyword match
    if profile.name:
        scholarship_name = source.get("name", "")
        if profile.name.lower() in scholarship_name.lower():
            reasons.append(f"name_keyword_match:{profile.name}")

    # Amount match (if specified)
    if profile.min_amount or profile.max_amount:
        scholarship_amount = source.get("amount")
        if scholarship_amount:
            reasons.append(f"amount_specified:{scholarship_amount}")

    return reasons


def _profile_to_filters(profile: Optional[UserProfileInput]) -> List[Dict[str, Any]]:
    """
    Convert user profile preferences to Elasticsearch filters.
    Maps to actual scholarship fields: name, university, open_time, close_time, amount, field_of_study, url
    """
    filters: List[Dict[str, Any]] = []
    if not profile:
        return filters
    
    # Name/keyword search
    if profile.name:
        filters.append({"field": "name", "values": [profile.name], "operator": "OR"})

    # University filter
    if profile.university:
        filters.append({"field": "university", "values": list(profile.university), "operator": "OR"})

    # Field of Study
    if profile.field_of_study:
        filters.append({"field": "field_of_study", "values": [profile.field_of_study], "operator": "OR"})

    # Amount range filters (if your ES service supports range queries on amount)
    # Note: This may require custom handling since amount can be strings like "450 USD" or "10,000,000 VNĐ"
    if profile.min_amount:
        filters.append({
            "field": "amount",
            "values": [profile.min_amount],
            "operator": "OR",
        })
    
    if profile.max_amount:
        filters.append({
            "field": "amount",
            "values": [profile.max_amount],
            "operator": "OR",
        })

    # Deadline range filters (close_time field)
    # Using range mode if supported by your ES service
    if profile.deadline_after or profile.deadline_before:
        rng: Dict[str, Any] = {"field": "close_time", "mode": "range"}
        if profile.deadline_after:
            rng["min"] = profile.deadline_after
        if profile.deadline_before:
            rng["max"] = profile.deadline_before
        filters.append(rng)

    return filters


def _load_scholarships_by_ids(client: Elasticsearch, index: str, ids: List[str]) -> Dict[str, Dict[str, Any]]:
    if not ids:
        return {}
    try:
        res = client.mget(index=index, ids=ids)
        out: Dict[str, Dict[str, Any]] = {}
        for doc in res.get("docs", []):
            if doc.get("found"):
                out[str(doc.get("_id"))] = doc.get("_source", {})
        return out
    except Exception:
        return {}


def match_scholarships(
    *,
    profile: Optional[UserProfileInput],
    size: int = 10,
    offset: int = 0,
) -> MatchResult:
    es = _es_client()
    try:
        collection = "scholar_lens"
        filters = _profile_to_filters(profile)

        # Use broad retrieval with OR to get diverse candidates
        res = filter_advanced(
            client=es,
            index=collection,
            collection=collection,
            filters=filters,
            inter_field_operator="OR",
            size=size,
            offset=offset,
        ) if filters else {"total": 0, "items": []}

        items: List[MatchItem] = []
        warnings: List[str] = []
        hits = res.get("items", [])
        ids = [h.get("id", "") for h in hits]
        sources_by_id = _load_scholarships_by_ids(es, collection, ids)
        if hits and not sources_by_id:
            warnings.append("Unable to batch load sources; using inline ES sources when available.")

        for h in hits:
            sid = h.get("id", "")
            src = sources_by_id.get(sid) or h.get("source") or {}
            matched_fields = _build_matched_fields(profile, src)
            items.append(
                MatchItem(
                    id=sid,
                    es_score=float(h.get("score", 0.0) or 0.0),
                    # ES handles ranking; keep match_score for backward compatibility
                    match_score=0.0,
                    matched_fields=matched_fields,
                    **_to_summary_fields(src),
                )
            )

        # Preserve ES order; no Python-side re-ranking

        total_hits = res.get("total", len(items))
        has_next = (offset + size) < total_hits
        next_off = (offset + size) if has_next else None

        return MatchResult(
            total=total_hits,
            items=items,
            hasNextPage=has_next,
            nextOffset=next_off,
            warnings=warnings or None,
        )
    finally:
        es.close()
