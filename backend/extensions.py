# backend/extensions.py

"""
GraphQL query depth limiting.

Rejects operations whose selection nesting exceeds GRAPHQL_MAX_DEPTH
(default 12). Prevents abusive deeply-nested queries that amplify
DB load through dataloaders/joins.
"""

import logging

from django.conf import settings
from graphql import GraphQLError, OperationDefinitionNode
from strawberry.extensions import SchemaExtension

logger = logging.getLogger(__name__)

MAX_DEPTH = getattr(settings, "GRAPHQL_MAX_DEPTH", 12)


def _selection_depth(selection_set, level: int) -> int:
    """Return the deepest field level reachable from a selection set."""
    deepest = level
    for selection in selection_set.selections:
        if getattr(selection, "selection_set", None):
            deepest = max(
                deepest,
                _selection_depth(selection.selection_set, level + 1),
            )
        else:
            deepest = max(deepest, level + 1)
    return deepest


class DepthLimitExtension(SchemaExtension):
    """Schema extension that rejects operations deeper than MAX_DEPTH."""

    async def on_operation(self):
        document = self.execution_context.graphql_document
        operation_name = self.execution_context.operation_name

        for definition in document.definitions:
            if not isinstance(definition, OperationDefinitionNode):
                continue
            if operation_name is not None:
                op_name = definition.name.value if definition.name else None
                if op_name != operation_name:
                    continue

            depth = _selection_depth(definition.selection_set, 0)
            if depth > MAX_DEPTH:
                logger.warning(
                    "Rejected GraphQL operation exceeding depth %s (got %s)",
                    MAX_DEPTH,
                    depth,
                )
                raise GraphQLError(
                    f"Query is too deeply nested (max depth {MAX_DEPTH})."
                )

        yield
