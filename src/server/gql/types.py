import strawberry
from typing import List
from strawberry.scalars import JSON
from enum import Enum
from typing import Optional
from datetime import date, datetime

@strawberry.type
class ScholarshipSource:
    name: Optional[str] = strawberry.field(name="Scholarship_Name")
    country: Optional[str] = strawberry.field(name="Country")
    start_date: Optional[str] = strawberry.field(name="Start_Date")
    end_date: Optional[str] = strawberry.field(name="End_Date")
    amount: Optional[str] = strawberry.field(name="Funding_Level")

    @strawberry.field(description="Số ngày còn lại trước hạn nộp (computed field)")
    def days_until_deadline(self) -> Optional[int]:
        """Tính số ngày còn lại từ hôm nay đến End_Date"""
        if not self.end_date:
            return None
        try:
            # Hỗ trợ cả dạng 'YYYY-MM-DD' hoặc 'DD/MM/YYYY'
            try:
                end = date.fromisoformat(self.end_date)
            except ValueError:
                end = datetime.strptime(self.end_date, "%d/%m/%Y").date()
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
    field: str
    values: List[JSON]
    operator: IntraFieldOperator = IntraFieldOperator.OR


@strawberry.type
class SearchHit:
    id: str
    score: float
    source: ScholarshipSource


@strawberry.type
class SearchResult:
    total: int
    items: List[SearchHit]

