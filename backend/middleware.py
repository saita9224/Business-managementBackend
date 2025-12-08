# backend/middleware.py

import logging
from django.contrib.auth import get_user_model
from strawberry.extensions import SchemaExtension
from authentication.services import decode_jwt_token

from expenses.dataloaders import (
    load_suppliers,
    load_products,
    load_payments,   # ← FIXED
)

from strawberry.dataloader import DataLoader

logger = logging.getLogger(__name__)
User = get_user_model()


class JWTMiddleware(SchemaExtension):
    def on_request_start(self):

        context = self.execution_context.context

        # Normalize context so we can write to it
        def set_attr(ctx, key, value):
            try:
                setattr(ctx, key, value)
            except Exception:
                try:
                    ctx[key] = value
                except Exception:
                    logger.debug(f"Could not set {key} on context")

        # -----------------------------
        # JWT AUTHENTICATION
        # -----------------------------
        set_attr(context, "user", None)

        request = getattr(context, "request", None) or (
            context.get("request") if isinstance(context, dict) else None
        )
        if request:
            auth_header = request.headers.get("Authorization") or request.META.get("HTTP_AUTHORIZATION")

            if auth_header:
                parts = auth_header.split()
                if len(parts) == 2:
                    prefix, token = parts
                    if prefix.lower() == "bearer":
                        user = decode_jwt_token(token)
                        if user:
                            set_attr(context, "user", user)

        # -----------------------------
        # GRAPHQL DATALOADERS (PER REQUEST)
        # -----------------------------
        set_attr(context, "supplier_loader", DataLoader(load_suppliers))
        set_attr(context, "product_loader", DataLoader(load_products))
        set_attr(context, "payments_by_expense_loader", DataLoader(load_payments))  # ← FIXED

        logger.debug("Injected dataloaders into GraphQL context")
