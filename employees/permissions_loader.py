# employees/permissions_loader.py

"""
Scans every installed app for a permissions.py module containing:

    PERMISSIONS = {"permission.code", ...}

and syncs those codes into the Permission table for the currently
active tenant schema.

Usage
-----
Single tenant (from shell or management command):

    from employees.permissions_loader import load_permissions
    load_permissions()

All tenants at once (post-deploy):

    from employees.permissions_loader import load_permissions_all_tenants
    load_permissions_all_tenants()

The loader is intentionally idempotent — safe to run multiple times.
Existing Permission rows are never deleted. New codes are created,
and descriptions of existing ones are updated only if they still
match the auto-generated default (i.e. have not been manually edited).
"""

import importlib
import logging
from django.apps import apps

logger = logging.getLogger(__name__)


# ======================================================
# CORE LOADER — runs inside the currently active schema
# ======================================================

def load_permissions() -> dict:
    """
    Sync all PERMISSIONS from installed apps into the Permission
    table of the currently active PostgreSQL schema (tenant).

    Returns {"created": int, "updated": int, "unchanged": int}.
    """
    from .models import Permission

    summary = {"created": 0, "updated": 0, "unchanged": 0}

    for app_config in apps.get_app_configs():
        module_name = f"{app_config.name}.permissions"

        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError:
            continue
        except Exception as exc:
            logger.warning(
                "Could not import %s: %s", module_name, exc, exc_info=True
            )
            continue

        if not hasattr(module, "PERMISSIONS"):
            continue

        app_permissions = module.PERMISSIONS

        if not isinstance(app_permissions, (set, list, tuple)):
            logger.warning(
                "%s.PERMISSIONS is not a set/list/tuple — skipping", module_name
            )
            continue

        logger.info(
            "Loading %d permission(s) from %s",
            len(app_permissions),
            module_name,
        )

        for code in app_permissions:
            if not isinstance(code, str) or not code.strip():
                logger.warning("Skipping invalid permission code: %r", code)
                continue

            code = code.strip()
            auto_description = f"Auto-loaded from {app_config.name}.permissions"

            perm, created = Permission.objects.get_or_create(
                code=code,
                defaults={
                    "name":        code,
                    "description": auto_description,
                },
            )

            if created:
                summary["created"] += 1
                logger.debug("  ✅ Created: %s", code)
            else:
                # Only update description if it still matches the old
                # auto-generated default — never overwrite manual edits.
                needs_save = False

                if perm.description == perm.code:
                    # Old default was the code string itself — update it
                    perm.description = auto_description
                    needs_save = True

                if needs_save:
                    perm.save(update_fields=["description"])
                    summary["updated"] += 1
                    logger.debug("  🔄 Updated: %s", code)
                else:
                    summary["unchanged"] += 1
                    logger.debug("  ✓  Unchanged: %s", code)

    logger.info(
        "Permission sync complete — created: %d, updated: %d, unchanged: %d",
        summary["created"],
        summary["updated"],
        summary["unchanged"],
    )

    return summary


# ======================================================
# MULTI-TENANT WRAPPER
# ======================================================

def load_permissions_all_tenants() -> dict:
    """
    Run load_permissions() inside every tenant schema.

    Call this from a post-deploy management command when new
    permission codes have been added. Skips the public schema.

    Returns a combined summary across all tenants.
    """
    from django_tenants.utils import schema_context, get_tenant_model

    TenantModel = get_tenant_model()
    combined    = {"created": 0, "updated": 0, "unchanged": 0}
    tenants     = TenantModel.objects.exclude(schema_name="public")

    if not tenants.exists():
        logger.warning("No tenants found — nothing to sync.")
        return combined

    for tenant in tenants:
        logger.info(
            "── Syncing permissions for tenant: %s (schema: %s)",
            tenant.name,
            tenant.schema_name,
        )
        try:
            with schema_context(tenant.schema_name):
                result = load_permissions()
            for key in combined:
                combined[key] += result[key]
        except Exception as exc:
            logger.error(
                "Failed to sync permissions for tenant %s: %s",
                tenant.schema_name,
                exc,
                exc_info=True,
            )

    logger.info(
        "All-tenant sync complete — created: %d, updated: %d, unchanged: %d",
        combined["created"],
        combined["updated"],
        combined["unchanged"],
    )

    return combined