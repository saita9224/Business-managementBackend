import pytest
from employees.decorators import permission_required
from graphql import GraphQLError


@pytest.mark.django_db
def test_permission_decorator_blocks_unauthorized(employee, info_context):
    @permission_required("employees.view")
    def resolver(root, info):
        return "OK"

    info = info_context(employee)

    with pytest.raises(GraphQLError):
        resolver(None, info)


@pytest.mark.django_db
def test_permission_decorator_allows_authorized(employee_with_role_permission, info_context):
    @permission_required("employees.view")
    def resolver(root, info):
        return "OK"

    info = info_context(employee_with_role_permission)

    assert resolver(None, info) == "OK"
