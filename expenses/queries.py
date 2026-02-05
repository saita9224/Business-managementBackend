# expenses/queries.py

import strawberry
from typing import List

from employees.decorators import permission_required

from .types import ExpenseItemType, SupplierType, ExpenseDetailsType
from .services import (
    list_expenses_by_supplier,
    list_expenses_by_item_name,
    list_expenses_by_product,
    get_expense_details,
)
from .models import Supplier


@strawberry.type
class ExpenseQuery:

    # -------------------------------
    # SEARCH
    # -------------------------------
    @strawberry.field
    @permission_required("expenses.view")
    def expenses_by_supplier(self, info, supplier_id: int) -> List[ExpenseItemType]:
        return list_expenses_by_supplier(supplier_id)

    @strawberry.field
    @permission_required("expenses.view")
    def expenses_by_item(self, info, item_name: str) -> List[ExpenseItemType]:
        return list_expenses_by_item_name(item_name)

    @strawberry.field
    @permission_required("expenses.view")
    def expenses_by_product(self, info, product_id: int) -> List[ExpenseItemType]:
        return list_expenses_by_product(product_id)

    # -------------------------------
    # SUPPLIERS
    # -------------------------------
    @strawberry.field
    @permission_required("expenses.view")
    def suppliers(self, info) -> List[SupplierType]:
        return list(Supplier.objects.all())

    # -------------------------------
    # DETAILS
    # -------------------------------
    @strawberry.field
    @permission_required("expenses.view")
    def expense_details(self, info, expense_id: int) -> ExpenseDetailsType:
        result = get_expense_details(expense_id)
        return ExpenseDetailsType(
            expense=result["expense"],
            payments=result["payments"],
            remaining_balance=result["remaining_balance"],
        )
