import strawberry
from typing import List
from enum import Enum
from typing import Optional
from datetime import date, datetime

@strawberry.type
class ScholarshipSource:
    """
    Normalized scholarship fields for GraphQL (no aliasing to ES keys).
    Mapping from ES keys happens in resolvers.
    """
    name: Optional[str]
    country: Optional[str]
    start_date: Optional[str]
    end_date: Optional[str]
    amount: Optional[str]

    @strawberry.field(description="Số ngày còn lại trước hạn nộp (computed field)")
    def days_until_deadline(self) -> Optional[int]:
        """Tính số ngày còn lại từ hôm nay đến End_Date"""
        if not self.end_date:
            return None
        try:
            end = date.fromisoformat(self.end_date)
            today = date.today()
            return (end - today).days
        except Exception:
            return None

@strawberry.enum
class InterFieldOperator(str, Enum):
    AND = "AND"
    OR = "OR"


@strawberry.enum
class IntraFieldOperator(str, Enum):
    AND = "AND"
    OR = "OR"


@strawberry.input
class FilterInput:
    """
    Strongly-typed filter values to avoid generic JSON.
    Only one of *_values needs to be provided; multiple will be merged.
    """
    field: str
    string_values: Optional[List[str]] = None
    int_values: Optional[List[int]] = None
    float_values: Optional[List[float]] = None
    operator: IntraFieldOperator = IntraFieldOperator.OR


@strawberry.type
class SearchHit:
    id: str
    score: float
    source: Optional[ScholarshipSource]


@strawberry.type
class SearchResult:
    total: int
    items: List[SearchHit]


# ---- Match Profile domain ----

@strawberry.input
class UserProfileInput:
    gpa_range_4: Optional[float] = None
    degree: Optional[str] = None
    field_of_study: Optional[str] = None
    # Flexible optional filters for expanded use cases
    desired_scholarship_type: Optional[List[str]] = None
    desired_funding_level: Optional[List[str]] = None
    desired_application_mode: Optional[List[str]] = None
    # Deadline range (ISO date strings)
    deadline_after: Optional[str] = None
    deadline_before: Optional[str] = None


@strawberry.type
class MatchItem:
    id: str
    es_score: float
    match_score: float
    matched_fields: List[str]
    summary_name: Optional[str]
    summary_start_date: Optional[str]
    summary_end_date: Optional[str]
    summary_amount: Optional[str]


@strawberry.type
class MatchResult:
    total: int
    items: List[MatchItem]
    hasNextPage: bool
    nextOffset: Optional[int]
    warnings: Optional[List[str]] = None
