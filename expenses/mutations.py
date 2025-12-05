# expenses/mutations.py

import strawberry
from strawberry.exceptions import GraphQLError

from employees.decorators import permission_required

from .types import (
    ExpenseItemType,
    SupplierType,
    ExpenseInput,
    PayBalanceInput,
)
from .services import (
    create_supplier,
    update_supplier,
    delete_supplier,
    create_expense_item,
    record_payment,
)


@strawberry.type
class ExpenseMutation:

    # --------------------------------------------------------
    # SUPPLIER MANAGEMENT
    # --------------------------------------------------------

    @strawberry.mutation
    @permission_required("expenses.manage_suppliers")
    def create_supplier(self, info, name: str) -> SupplierType:
        try:
            return create_supplier(name)
        except Exception as e:
            raise GraphQLError(str(e))

    @strawberry.mutation
    @permission_required("expenses.manage_suppliers")
    def update_supplier(self, info, supplier_id: int, name: str) -> SupplierType:
        try:
            return update_supplier(supplier_id, name)
        except Exception as e:
            raise GraphQLError(str(e))

    @strawberry.mutation
    @permission_required("expenses.manage_suppliers")
    def delete_supplier(self, info, supplier_id: int) -> bool:
        try:
            return delete_supplier(supplier_id)
        except Exception as e:
            raise GraphQLError(str(e))

    # --------------------------------------------------------
    # EXPENSE CREATION
    # --------------------------------------------------------

    @strawberry.mutation
    @permission_required("expenses.create")
    def create_expense(self, info, data: ExpenseInput) -> ExpenseItemType:
        try:
            return create_expense_item(
                supplier_id=data.supplier_id,
                product_id=data.product_id,
                item_name=data.item_name,
                unit_price=data.price,
                quantity=data.quantity,
            )
        except Exception as e:
            raise GraphQLError(str(e))

    # --------------------------------------------------------
    # RECORD PAYMENT
    # --------------------------------------------------------

    @strawberry.mutation
    @permission_required("expenses.update")  # ✔ Pay is an update action
    def pay_balance(self, info, data: PayBalanceInput) -> ExpenseItemType:
        try:
            result = record_payment(data.expense_id, data.amount)
            return result["payment"].expense  # return updated expense
        except Exception as e:
            raise GraphQLError(str(e))
