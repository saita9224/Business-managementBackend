# pos/schema.py

import strawberry
from strawberry.types import Info

from .queries import POSQuery
from .mutations import POSMutation
from .dataloaders import create_pos_dataloaders


# ======================================================
# POS SCHEMA
# ======================================================

@strawberry.type
class Query(POSQuery):
    """
    POS Query root.
    Inherits all fields from POSQuery.
    """
    pass


@strawberry.type
class Mutation(POSMutation):
    """
    POS Mutation root.
    Inherits all fields from POSMutation.
    """
    pass


# ======================================================
# CONTEXT INJECTION
# ======================================================

def build_pos_context(request) -> dict:
    """
    Builds request-scoped GraphQL context for POS.

    Expected to be merged with the main app context.
    """

    context = {
        "request": request,
        "user": request.user,  # Employee
    }

    # Inject POS dataloaders (request-scoped)
    context.update(create_pos_dataloaders())

    return context


# ======================================================
# SCHEMA EXPORT
# ======================================================

pos_schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
)
