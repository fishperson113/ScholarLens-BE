import strawberry
from typing import Optional, List

from .types import ScholarshipFilter, InterFieldOperator, SearchResult, UserProfileInput, MatchResult, SortOrder
from .search_resolver import search_es as search_es_resolver
from .match_resolver import match_scholarships as match_resolver


@strawberry.type
class Query:
    @strawberry.field(description="Unified ES search combining keyword and structured filters")
    def search_es(
        self,
        collection: str,
        q: Optional[str] = None,
        filter: Optional[ScholarshipFilter] = None,
        inter_field_operator: InterFieldOperator = InterFieldOperator.AND,
        sort_by_deadline: bool = True,
        sort_order: SortOrder = SortOrder.ASC,
        size: int = 10,
        offset: int = 0,
    ) -> SearchResult:
        return search_es_resolver(
            collection=collection,
            q=q,
            filter=filter,
            inter_field_operator=inter_field_operator,
            sort_by_deadline=sort_by_deadline,
            sort_order=sort_order,
            size=size,
            offset=offset,
        )

    @strawberry.field(name="matchScholarships", description="Recommend scholarships for a given user profile")
    def match_scholarships(
        self,
        profile: Optional[UserProfileInput] = None,
        size: int = 10,
        offset: int = 0,
    ) -> MatchResult:
        return match_resolver(
            profile=profile,
            size=size,
            offset=offset,
        )


schema = strawberry.Schema(query=Query)
