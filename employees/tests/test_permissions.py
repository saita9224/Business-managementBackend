import pytest
from employees.helpers import require_permission
from graphql import GraphQLError


@pytest.mark.django_db
def test_require_permission_allows_user_with_role_permission(
    employee_with_role_permission,
    info_context
):
    user = employee_with_role_permission
    info = info_context(user)

    # Should NOT raise
    require_permission(info, "employees.view")


@pytest.mark.django_db
def test_require_permission_denies_user_without_permission(employee, info_context):
    info = info_context(employee)

    with pytest.raises(GraphQLError):
        require_permission(info, "employees.view")
