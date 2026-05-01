# employees/permissions_loader.py

"""
Scans every installed app for a permissions.py module containing:

    PERMISSIONS = {"permission.code", ...}

and syncs those codes into the Permission table for the *currently active*
tenant schema.

Usage
-----
Single tenant (e.g. from a management command or shell):

    from employees.permissions_loader import load_permissions
    load_permissions()

All tenants at once (e.g. post-deploy script):

    from employees.permissions_loader import load_permissions_all_tenants
    load_permissions_all_tenants()

The loader is intentionally idempotent — running it multiple times is safe.
Existing Permission rows are never deleted; new codes are created, and the
name/description of existing ones are updated if they have drifted.
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
    Sync all PERMISSIONS from installed apps into the Permission table
    of the currently active PostgreSQL schema (tenant).

    Returns a summary dict: {"created": int, "updated": int, "unchanged": int}
    """

    # Import here (not at module level) so this file can be imported
    # safely before Django's app registry is fully ready, and to avoid
    # any circular-import risk at startup.
    from .models import Permission

    summary = {"created": 0, "updated": 0, "unchanged": 0}

    for app_config in apps.get_app_configs():
        module_name = f"{app_config.name}.permissions"

        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError:
            # Most apps won't have a permissions.py — that's fine.
            continue
        except Exception as exc:
            # Catch unexpected import errors so one bad app doesn't
            # abort the whole sync.
            logger.warning(
                "Could not import %s: %s", module_name, exc, exc_info=True
            )
            continue

        if not hasattr(module, "PERMISSIONS"):
            logger.debug("%s has no PERMISSIONS attribute — skipping", module_name)
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

            # Use get_or_create so the loader is safe to run repeatedly.
            # If the row already exists we check whether name/description
            # have drifted and update them so the DB stays consistent with
            # the source-of-truth in permissions.py files.
            perm, created = Permission.objects.get_or_create(
                code=code,
                defaults={
                    "name": code,
                    "description": f"Auto-loaded from {app_config.name}.permissions",
                },
            )

            if created:
                summary["created"] += 1
                logger.debug("  ✅ Created: %s", code)
            else:
                # Update name/description if they still match the old
                # auto-generated defaults (i.e. haven't been manually edited).
                # We never overwrite a manually customised description.
                needs_save = False

                if perm.name == code and perm.name != code:
                    # name has drifted from code — realign
                    perm.name = code
                    needs_save = True

                auto_description = f"Auto-loaded from {app_config.name}.permissions"
                if perm.description != auto_description and perm.name == perm.code:
                    # Only update if description looks auto-generated
                    # (i.e. it equals the code string, the old default).
                    if perm.description == perm.code:
                        perm.description = auto_description
                        needs_save = True

                if needs_save:
                    perm.save(update_fields=["name", "description"])
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
# MULTI-TENANT WRAPPER — iterates every tenant schema
# ======================================================

def load_permissions_all_tenants() -> dict:
    """
    Run load_permissions() inside every tenant's schema.

    This is the right function to call from a post-deploy
    management command or CI step when you've added new
    permission codes and want them seeded into all existing
    tenant schemas at once.

    Skips the 'public' schema (no Permission table there).

    Returns a combined summary across all tenants.
    """

    from django_tenants.utils import schema_context, get_tenant_model

    TenantModel = get_tenant_model()
    combined = {"created": 0, "updated": 0, "unchanged": 0}

    tenants = TenantModel.objects.exclude(schema_name="public")

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
            # Log and continue — a broken tenant schema shouldn't
            # abort the sync for all other tenants.
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