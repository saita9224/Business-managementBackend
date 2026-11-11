# sync/registry.py

from .types import SyncMutationTypeEnum
from .handlers import (
    handle_create_receipt,
    handle_create_order,
    handle_add_order_item,
    handle_add_menu_order_item,
    handle_submit_order,
    handle_accept_payment,
    handle_create_expense,
    handle_pay_balance,
    handle_add_stock,
    handle_remove_stock,
    handle_create_category,
    handle_create_product,
    handle_create_product_with_stock,
    handle_add_stock_from_expense,
    handle_refund_receipt,
    handle_self_check_in,
    handle_self_check_out,
    handle_request_leave,
)

SYNC_MUTATION_REGISTRY = {
    SyncMutationTypeEnum.CREATE_RECEIPT: {
        "permission": "pos.create_order",
        "handler": handle_create_receipt,
    },
    SyncMutationTypeEnum.CREATE_ORDER: {
        "permission": "pos.create_order",
        "handler": handle_create_order,
    },
    SyncMutationTypeEnum.ADD_ORDER_ITEM: {
        "permission": "pos.create_order",
        "handler": handle_add_order_item,
    },
    SyncMutationTypeEnum.ADD_MENU_ORDER_ITEM: {
        "permission": "pos.create_order",
        "handler": handle_add_menu_order_item,
    },
    SyncMutationTypeEnum.SUBMIT_ORDER: {
        "permission": "pos.create_order",
        "handler": handle_submit_order,
    },
    SyncMutationTypeEnum.ACCEPT_PAYMENT: {
        "permission": "pos.accept_payment",
        "handler": handle_accept_payment,
    },
    SyncMutationTypeEnum.CREATE_EXPENSE: {
        "permission": "expenses.create",
        "handler": handle_create_expense,
    },
    SyncMutationTypeEnum.PAY_BALANCE: {
        "permission": "expenses.pay",
        "handler": handle_pay_balance,
    },
    SyncMutationTypeEnum.ADD_STOCK: {
        "permission": "inventory.stock.in",
        "handler": handle_add_stock,
    },
    SyncMutationTypeEnum.REMOVE_STOCK: {
        "permission": "inventory.stock.out",
        "handler": handle_remove_stock,
    },
    SyncMutationTypeEnum.CREATE_CATEGORY: {"permission": "inventory.product.create", "handler": handle_create_category},
    SyncMutationTypeEnum.CREATE_PRODUCT: {"permission": "inventory.product.create", "handler": handle_create_product},
    SyncMutationTypeEnum.CREATE_PRODUCT_WITH_STOCK: {"permission": "inventory.product.create", "handler": handle_create_product_with_stock},
    SyncMutationTypeEnum.ADD_STOCK_FROM_EXPENSE: {"permission": "inventory.stock.in", "handler": handle_add_stock_from_expense},
    SyncMutationTypeEnum.REFUND_RECEIPT: {"permission": "pos.refund_order", "handler": handle_refund_receipt},
    SyncMutationTypeEnum.SELF_CHECK_IN: {"permission": "hr.self_checkin", "handler": handle_self_check_in},
    SyncMutationTypeEnum.SELF_CHECK_OUT: {"permission": "hr.self_checkin", "handler": handle_self_check_out},
    SyncMutationTypeEnum.REQUEST_LEAVE: {"permission": "hr.request_leave", "handler": handle_request_leave},
}
