# backend/middleware.py

import logging
from strawberry.extensions import SchemaExtension
from asgiref.sync import sync_to_async
from django.db import connection
from authentication.services import decode_jwt_token

logger = logging.getLogger(__name__)


def _get_current_schema_name():
    """
    Looks up connection.schema_name on whichever thread this runs on.
    Must be called via sync_to_async so it resolves against the same
    thread that resolvers will actually query on.
    """
    from django.db import connection as conn
    return getattr(conn, "schema_name", None)


def _set_schema(schema_name):
    """
    Resolves `connection` and calls set_schema entirely inside this
    function -- never as a bare attribute access outside sync_to_async.
    connection is thread-local, so resolving it before dispatching to
    a worker thread binds to the wrong thread's connection and is a
    silent no-op for every query that runs afterward.
    """
    from django.db import connection as conn
    conn.set_schema(schema_name)


def _set_schema_to_public():
    from django.db import connection as conn
    conn.set_schema_to_public()


class JWTMiddleware(SchemaExtension):

    async def on_operation(self):
        """
        Runs before and after every GraphQL operation.
        Must yield to allow execution to proceed.

        Also derives and activates the tenant schema from the JWT's
        schema_name claim (set at login/registration -- see
        authentication/services.py create_jwt_token), so clients no
        longer need to send X-Tenant on authenticated requests.

        IMPORTANT: connection is thread-local. Every read or write of
        connection/schema state here must happen INSIDE a function
        passed to sync_to_async, never as a bare attribute access in
        this async method's own body -- otherwise it resolves against
        the event-loop thread instead of the pinned worker thread that
        resolvers (via sync_to_async(thread_sensitive=True)) actually
        query on, and the switch silently does nothing.
        """

        context = self.execution_context.context

        def set_attr(ctx, key, value):
            if isinstance(ctx, dict):
                ctx[key] = value
            else:
                setattr(ctx, key, value)

        def get_attr(ctx, key, default=None):
            if isinstance(ctx, dict):
                return ctx.get(key, default)
            return getattr(ctx, key, default)

        # Default to unauthenticated
        set_attr(context, "user", None)

        request = get_attr(context, "request")

        schema_switched = False

        if request:
            auth_header = (
                request.headers.get("Authorization")
                or request.META.get("HTTP_AUTHORIZATION")
            )

            if auth_header:
                parts = auth_header.split()

                if len(parts) == 2:
                    prefix, token = parts

                    if prefix.lower() == "bearer":
                        # FIX: resolve current_schema via sync_to_async
                        # so it's read on the same thread queries run on.
                        current_schema = await sync_to_async(
                            _get_current_schema_name
                        )()

                        if current_schema and current_schema != "public":
                            expected_schema_name = current_schema
                        else:
                            expected_schema_name = None

                        user = await decode_jwt_token(
                            token,
                            expected_schema_name=expected_schema_name,
                        )

                        if user:
                            set_attr(context, "user", user)
                            logger.debug(f"Authenticated: {user.email}")

                            if (
                                current_schema == "public"
                                or current_schema is None
                            ):
                                jwt_schema_name = getattr(
                                    user, "_jwt_schema_name", None
                                )
                                if jwt_schema_name:
                                    # FIX: entire connection lookup +
                                    # set_schema call happens inside
                                    # _set_schema, dispatched via
                                    # sync_to_async -- not resolved
                                    # eagerly on the event-loop thread.
                                    await sync_to_async(_set_schema)(
                                        jwt_schema_name
                                    )
                                    schema_switched = True
                        else:
                            logger.debug("Invalid or expired token")

        yield  # 👈 resolvers execute here

        if schema_switched:
            # FIX: same pattern -- resolve connection inside the
            # sync_to_async-dispatched function.
            await sync_to_async(_set_schema_to_public)()