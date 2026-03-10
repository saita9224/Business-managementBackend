# expenses/mutations.py

import strawberry
import logging

from asgiref.sync import sync_to_async
from strawberry.exceptions import GraphQLError
from django.core.exceptions import ValidationError

from employees.decorators import permission_required

from .types import (
    SupplierType,
    ExpenseItemType,
    CreateExpenseResult,   # 👈 new return type
    InventoryProductType,  # 👈 for building matched_product
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


# ============================================================
# VALIDATION ERROR FORMATTER
# ============================================================

def format_validation_error(e: ValidationError) -> str:
    if hasattr(e, "message_dict"):
        messages = []
        for field, errors in e.message_dict.items():
            for error in errors:
                messages.append(f"{field}: {error}")
        return "; ".join(messages)
    if hasattr(e, "messages"):
        return "; ".join(e.messages)
    return str(e)


# ============================================================
# EXPENSE MUTATIONS
# ============================================================

@strawberry.type
class ExpenseMutation:

    # ========================================================
    # SUPPLIER MUTATIONS
    # ========================================================

    @strawberry.mutation
    @permission_required("expenses.manage_suppliers")
    async def create_supplier(self, info, name: str) -> SupplierType:
        try:
            return await sync_to_async(create_supplier)(name=name)
        except ValidationError as e:
            raise GraphQLError(format_validation_error(e))
        except Exception:
            logger.exception("Unexpected error while creating supplier")
            raise GraphQLError("Internal server error")


    @strawberry.mutation
    @permission_required("expenses.manage_suppliers")
    async def update_supplier(
        self,
        info,
        supplier_id: int,
        name: str,
    ) -> SupplierType:
        try:
            return await sync_to_async(update_supplier)(
                supplier_id=supplier_id,
                name=name,
            )
        except ValidationError as e:
            raise GraphQLError(format_validation_error(e))
        except Exception:
            logger.exception("Unexpected error while updating supplier")
            raise GraphQLError("Internal server error")


    @strawberry.mutation
    @permission_required("expenses.manage_suppliers")
    async def delete_supplier(self, info, supplier_id: int) -> bool:
        try:
            return await sync_to_async(delete_supplier)(supplier_id=supplier_id)
        except ValidationError as e:
            raise GraphQLError(format_validation_error(e))
        except Exception:
            logger.exception("Unexpected error while deleting supplier")
            raise GraphQLError("Internal server error")


    # ========================================================
    # CREATE EXPENSE — now returns CreateExpenseResult
    # ========================================================

    @strawberry.mutation
    @permission_required("expenses.create")
    async def create_expense(
        self,
        info,
        data: ExpenseInput,
    ) -> CreateExpenseResult:  # 👈 changed from ExpenseItemType

        try:
            result = await sync_to_async(create_expense_item)(
                supplier_id=data.supplier_id,
                supplier_name=data.supplier_name,
                product_id=data.product_id,
                item_name=data.item_name,
                unit_price=data.unit_price,
                quantity=data.quantity,
            )

            expense = result["expense"]
            matched_product = result["matched_product"]

            # 👇 Build InventoryProductType if a match was found
            inventory_product = None
            if matched_product:
                stock = await info.context.current_stock_loader.load(
                    matched_product.id
                )
                inventory_product = InventoryProductType(
                    id=matched_product.id,
                    name=matched_product.name,
                    unit=matched_product.unit,
                    current_stock=float(stock or 0),
                )

            return CreateExpenseResult(
                expense=expense,
                matched_product=inventory_product,
            )

        except ValidationError as e:
            raise GraphQLError(format_validation_error(e))
        except Exception:
            logger.exception("Unexpected error while creating expense")
            raise GraphQLError("Internal server error")


    # ========================================================
    # PAY BALANCE
    # ========================================================

    @strawberry.mutation
    @permission_required("expenses.pay")
    async def pay_balance(
        self,
        info,
        data: PayBalanceInput,
    ) -> ExpenseItemType:
        try:
            result = await sync_to_async(record_payment)(
                expense_id=data.expense_id,
                amount=data.amount,
            )
            return result["expense"]
        except ValidationError as e:
            raise GraphQLError(format_validation_error(e))
        except Exception:
            logger.exception("Unexpected error while processing payment")
            raise GraphQLError("Internal server error")