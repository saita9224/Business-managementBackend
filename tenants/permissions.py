"""
Permissions for tenant/business profile management.
"""

PERMISSIONS = {
    "tenant.manage_profile",
}

PERMISSION_META = {
    "tenant.manage_profile": (
        "Manage Business Profile",
        "Can update the business name and logo",
    ),
}
