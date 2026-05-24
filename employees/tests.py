from django.test import SimpleTestCase

from employees.permissions import (
    PERMISSION_META,
    PERMISSIONS,
    clear_permission_cache,
    get_permissions_for_role,
)


class EmployeePermissionConfigTests(SimpleTestCase):
    def test_all_permissions_have_metadata(self):
        self.assertEqual(PERMISSIONS, set(PERMISSION_META))

    def test_clear_permission_cache_resets_cached_role_lookup(self):
        get_permissions_for_role.cache_clear()

        clear_permission_cache()
        info = get_permissions_for_role.cache_info()

        self.assertEqual(info.currsize, 0)
