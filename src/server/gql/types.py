import strawberry
from typing import List
from strawberry.scalars import JSON
from enum import Enum


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
    source: JSON


@strawberry.type
class SearchResult:
    total: int
    items: List[SearchHit]
