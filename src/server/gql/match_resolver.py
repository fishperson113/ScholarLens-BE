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
        "summary_name": src.get("Scholarship_Name"),
        "summary_start_date": src.get("Start_Date"),
        "summary_end_date": src.get("End_Date"),
        "summary_amount": src.get("Funding_Level"),
    }

def _build_matched_fields(profile: Optional[UserProfileInput], source: Dict[str, Any]) -> List[str]:
    reasons: List[str] = []

    if not profile:
        return reasons

    # Field of study — for ease-of-use, mark as matched when profile filter is applied
    if profile.field_of_study:
        reasons.append(f"field_of_study_match:{profile.field_of_study}")

    # Degree
    if profile.degree:
        degree_fields = (
            source.get("Degree")
            or source.get("Eligible_Degree")
            or source.get("required_degree")
        )
        required_degree = source.get("required_degree")
        if isinstance(degree_fields, list):
            if profile.degree in degree_fields:
                if required_degree:
                    reasons.append(f"degree_match:profile={profile.degree};required_degree={required_degree}")
                else:
                    reasons.append(f"degree_match:profile={profile.degree}")
        elif isinstance(degree_fields, str):
            if profile.degree == degree_fields:
                if required_degree:
                    reasons.append(f"degree_match:profile={profile.degree};required_degree={required_degree}")
                else:
                    reasons.append(f"degree_match:profile={profile.degree}")

    # GPA requirement (explanatory only)
    if profile.gpa_range_4 is not None:
        # Assume normalized numeric GPA field(s) in source
        min_gpa_value: Optional[float] = None
        for key in ("Min_GPA", "Minimum_GPA", "GPA"):
            v = source.get(key)
            if isinstance(v, (int, float)):
                min_gpa_value = float(v)
                break
        if min_gpa_value is not None:
            if profile.gpa_range_4 >= min_gpa_value:
                reasons.append("gpa_requirement_met")
            else:
                reasons.append("gpa_below_requirement")

    return reasons


def _profile_to_filters(profile: Optional[UserProfileInput]) -> List[Dict[str, Any]]:
    filters: List[Dict[str, Any]] = []
    if not profile:
        return filters
    # Degree filters
    if profile.degree:
        # Support multiple degree mappings including required_degree
        filters.append({"field": "Degree", "values": [profile.degree], "operator": "OR"})
        filters.append({"field": "Eligible_Degree", "values": [profile.degree], "operator": "OR"})
        filters.append({"field": "required_degree", "values": [profile.degree], "operator": "OR"})

    # Field of Study
    if profile.field_of_study:
        filters.append({"field": "Eligible_Fields", "values": [profile.field_of_study], "operator": "OR"})

    # Countries
    if getattr(profile, "desired_countries", None):
        filters.append({
            "field": "Country",
            "values": list(profile.desired_countries or []),
            "operator": "OR",
            # leave default match mode for broad recall
        })

    # Scholarship type
    if getattr(profile, "desired_scholarship_type", None):
        filters.append({
            "field": "Scholarship_Type",
            "values": list(profile.desired_scholarship_type or []),
            "operator": "OR",
        })

    # Funding level
    if getattr(profile, "desired_funding_level", None):
        filters.append({
            "field": "Funding_Level",
            "values": list(profile.desired_funding_level or []),
            "operator": "OR",
        })

    # Application mode
    if getattr(profile, "desired_application_mode", None):
        filters.append({
            "field": "Application_Mode",
            "values": list(profile.desired_application_mode or []),
            "operator": "OR",
        })

    # GPA minimum as range (if normalized numeric field exists)
    if profile.gpa_range_4 is not None:
        filters.append({
            "field": "Min_GPA",
            "mode": "range",
            "min": float(profile.gpa_range_4),
        })

    # Deadline range
    if getattr(profile, "deadline_after", None) or getattr(profile, "deadline_before", None):
        rng: Dict[str, Any] = {"field": "End_Date", "mode": "range"}
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
        collection = "scholarships"
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
