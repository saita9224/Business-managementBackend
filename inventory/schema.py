import strawberry
from .queries import InventoryQuery
from .mutations import InventoryMutation

@strawberry.type
class Query(InventoryQuery):
    pass

@strawberry.type
class Mutation(InventoryMutation):
    pass

inventory_schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
)
