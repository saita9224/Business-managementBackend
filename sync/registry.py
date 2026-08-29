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
    handle_add_stock,
    handle_remove_stock,
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
    SyncMutationTypeEnum.ADD_STOCK: {
        "permission": "inventory.stock.in",
        "handler": handle_add_stock,
    },
    SyncMutationTypeEnum.REMOVE_STOCK: {
        "permission": "inventory.stock.out",
        "handler": handle_remove_stock,
    },
}
