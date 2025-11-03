import strawberry
from typing import Optional, List

from .types import FilterInput, InterFieldOperator, SearchResult
from .search_resolver import search_es as search_es_resolver


@strawberry.type
class Query:
    @strawberry.field(description="Unified ES search combining keyword and structured filters")
    def search_es(
        self,
        collection: str,
        index: str,
        q: Optional[str] = None,
        filters: Optional[List[FilterInput]] = None,
        inter_field_operator: InterFieldOperator = InterFieldOperator.AND,
        size: int = 10,
        offset: int = 0,
    ) -> SearchResult:
        return search_es_resolver(
            collection=collection,
            index=index,
            q=q,
            filters=filters,
            inter_field_operator=inter_field_operator,
            size=size,
            offset=offset,
        )


schema = strawberry.Schema(query=Query)
