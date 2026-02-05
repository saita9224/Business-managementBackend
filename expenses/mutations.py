# expenses/mutations.py

import strawberry
from strawberry.exceptions import GraphQLError
from django.core.exceptions import ValidationError
import logging

from employees.decorators import permission_required

from .types import (
    SupplierType,
    ExpenseItemType,
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

logger = logging.getLogger(__name__)


@strawberry.type
class ExpenseMutation:

    # -------------------------------
    # SUPPLIERS
    # -------------------------------
    @strawberry.mutation
    @permission_required("expenses.manage_suppliers")
    def create_supplier(self, info, name: str) -> SupplierType:
        try:
            return create_supplier(name)
        except ValidationError as e:
            raise GraphQLError(e.message)
        except Exception:
            logger.exception("Error creating supplier")
            raise GraphQLError("Internal server error")

    @strawberry.mutation
    @permission_required("expenses.manage_suppliers")
    def update_supplier(self, info, supplier_id: int, name: str) -> SupplierType:
        try:
            return update_supplier(supplier_id, name)
        except ValidationError as e:
            raise GraphQLError(e.message)
        except Exception:
            logger.exception("Error updating supplier")
            raise GraphQLError("Internal server error")

    @strawberry.mutation
    @permission_required("expenses.manage_suppliers")
    def delete_supplier(self, info, supplier_id: int) -> bool:
        try:
            return delete_supplier(supplier_id)
        except ValidationError as e:
            raise GraphQLError(e.message)
        except Exception:
            logger.exception("Error deleting supplier")
            raise GraphQLError("Internal server error")

    # -------------------------------
    # EXPENSE
    # -------------------------------
    @strawberry.mutation
    @permission_required("expenses.create")
    def create_expense(self, info, data: ExpenseInput) -> ExpenseItemType:
        try:
            return create_expense_item(
                supplier_id=data.supplier_id,
                product_id=data.product_id,
                item_name=data.item_name,
                unit_price=data.unit_price,  # ✅ FIXED
                quantity=data.quantity,
            )
        except ValidationError as e:
            raise GraphQLError(e.message)
        except Exception:
            logger.exception("Error creating expense")
            raise GraphQLError("Internal server error")

    # -------------------------------
    # PAY BALANCE
    # -------------------------------
    @strawberry.mutation
    @permission_required("expenses.pay")
    def pay_balance(self, info, data: PayBalanceInput) -> ExpenseItemType:
        try:
            result = record_payment(
                expense_id=data.expense_id,
                amount=data.amount,
            )
            return result["expense"]
        except ValidationError as e:
            raise GraphQLError(e.message)
        except Exception:
            logger.exception("Error processing payment")
            raise GraphQLError("Internal server error")
