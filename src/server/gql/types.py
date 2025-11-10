import strawberry
from typing import List
from enum import Enum
from typing import Optional
from datetime import date, datetime

@strawberry.type
class ScholarshipSource:
    """
    Simplified scholarship fields matching actual data structure.
    Maps directly to: id, name, university, open_time, close_time, amount, field_of_study, url
    """
    name: Optional[str]
    university: Optional[str]
    open_time: Optional[str]
    close_time: Optional[str]
    amount: Optional[str]
    field_of_study: Optional[str]
    url: Optional[str]

    @strawberry.field(description="Số ngày còn lại trước hạn nộp (computed field)")
    def days_until_deadline(self) -> Optional[str]:
        """Tính số ngày còn lại từ hôm nay đến close_time. Returns 'Expired' if deadline has passed."""
        if not self.close_time:
            return None
        try:
            # Handle DD/MM/YYYY format
            if '/' in self.close_time:
                day, month, year = self.close_time.split('/')
                end = date(int(year), int(month), int(day))
            else:
                # Fallback to ISO format
                end = date.fromisoformat(self.close_time)
            today = date.today()
            days_left = (end - today).days
            
            # Return "Expired" if deadline has passed
            if days_left < 0:
                return "Expired"
            return str(days_left)
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


@strawberry.enum
class SortOrder(str, Enum):
    ASC = "asc"
    DESC = "desc"


@strawberry.input
class ScholarshipFilter:
    """
    Filter scholarships by their fields.
    All fields are optional - provide only the fields you want to filter by.
    """
    name: Optional[str] = None
    university: Optional[str] = None
    field_of_study: Optional[str] = None
    amount: Optional[str] = None


@strawberry.type
class SearchHit:
    id: str
    score: Optional[float]
    source: Optional[ScholarshipSource]


@strawberry.type
class SearchResult:
    total: int
    items: List[SearchHit]


# ---- Match Profile domain ----

@strawberry.input
class UserProfileInput:
    """
    User profile input for matching scholarships.
    All fields are optional - provide only the fields you want to filter by.
    Maps to actual scholarship fields: name, university, open_time, close_time, amount, field_of_study, url
    """
    # Basic scholarship preferences
    name: Optional[str] = None  # Scholarship name keyword search
    university: Optional[List[str]] = None  # List of preferred universities
    field_of_study: Optional[str] = None  # Desired field of study
    
    # Amount/funding preferences
    min_amount: Optional[str] = None  # Minimum scholarship amount
    max_amount: Optional[str] = None  # Maximum scholarship amount
    
    # Deadline preferences (DD/MM/YYYY format)
    deadline_after: Optional[str] = None  # Only scholarships closing after this date
    deadline_before: Optional[str] = None  # Only scholarships closing before this date
    


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
