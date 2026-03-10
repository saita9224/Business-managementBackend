# expenses/queries.py

import strawberry
from typing import List
from asgiref.sync import sync_to_async

from employees.decorators import permission_required

from .types import (
    ExpenseItemType,
    ExpensePaymentType,
    SupplierType,
    ExpenseDetailsType,
)

from .services import (
    list_expenses_by_supplier,
    list_expenses_by_item_name,
    list_expenses_by_product,
    get_expense_details,
)

from .models import Supplier, ExpenseItem, ExpensePayment


@strawberry.type
class ExpenseQuery:

    # =========================================================
    # ALL EXPENSES
    # =========================================================

    @strawberry.field
    @permission_required("expenses.view")
    async def all_expenses(self, info) -> List[ExpenseItemType]:
        return await sync_to_async(list)(
            ExpenseItem.objects
            .select_related("supplier", "product")
            .order_by("-created_at")
        )

    # =========================================================
    # ALL PAYMENTS
    # Returns every payment across all expenses ordered by
    # paid_at desc. Frontend uses paid_at to group payments
    # by day for accurate daily expenditure totals —
    # a balance paid today on yesterday's expense appears
    # under today, not yesterday.
    # =========================================================

    @strawberry.field
    @permission_required("expenses.view")
    async def all_payments(self, info) -> List[ExpensePaymentType]:
        return await sync_to_async(list)(
            ExpensePayment.objects
            .select_related("expense", "expense__supplier")
            .order_by("-paid_at")
        )

    # =========================================================
    # SEARCH EXPENSES
    # =========================================================

    @strawberry.field
    @permission_required("expenses.view")
    async def expenses_by_supplier(
        self,
        info,
        supplier_id: int,
    ) -> List[ExpenseItemType]:
        return await sync_to_async(list)(
            list_expenses_by_supplier(supplier_id)
        )

    @strawberry.field
    @permission_required("expenses.view")
    async def expenses_by_item(
        self,
        info,
        item_name: str,
    ) -> List[ExpenseItemType]:
        return await sync_to_async(list)(
            list_expenses_by_item_name(item_name)
        )

    @strawberry.field
    @permission_required("expenses.view")
    async def expenses_by_product(
        self,
        info,
        product_id: int,
    ) -> List[ExpenseItemType]:
        return await sync_to_async(list)(
            list_expenses_by_product(product_id)
        )

    # =========================================================
    # SUPPLIERS
    # =========================================================

    @strawberry.field
    @permission_required("expenses.view")
    async def suppliers(self, info) -> List[SupplierType]:
        return await sync_to_async(list)(
            Supplier.objects.all().order_by("name")
        )

    # =========================================================
    # EXPENSE DETAILS
    # =========================================================

    @strawberry.field
    @permission_required("expenses.view")
    async def expense_details(
        self,
        info,
        expense_id: int,
    ) -> ExpenseDetailsType:
        result = await sync_to_async(get_expense_details)(expense_id)
        return ExpenseDetailsType(
            expense=result["expense"],
            payments=result["payments"],
            remaining_balance=result["remaining_balance"],
        )