# sync/types.py

import enum
from typing import Optional, List
import strawberry
from strawberry.scalars import JSON


@strawberry.enum
class SyncMutationTypeEnum(enum.Enum):
    CREATE_RECEIPT      = "CREATE_RECEIPT"
    CREATE_ORDER        = "CREATE_ORDER"
    ADD_ORDER_ITEM      = "ADD_ORDER_ITEM"
    ADD_MENU_ORDER_ITEM = "ADD_MENU_ORDER_ITEM"
    SUBMIT_ORDER        = "SUBMIT_ORDER"
    ACCEPT_PAYMENT      = "ACCEPT_PAYMENT"
    CREATE_EXPENSE      = "CREATE_EXPENSE"
    PAY_BALANCE         = "PAY_BALANCE"
    ADD_STOCK          = "ADD_STOCK"
    REMOVE_STOCK       = "REMOVE_STOCK"
    CREATE_CATEGORY    = "CREATE_CATEGORY"
    CREATE_PRODUCT     = "CREATE_PRODUCT"
    CREATE_PRODUCT_WITH_STOCK = "CREATE_PRODUCT_WITH_STOCK"
    ADD_STOCK_FROM_EXPENSE = "ADD_STOCK_FROM_EXPENSE"
    REFUND_RECEIPT = "REFUND_RECEIPT"
    SELF_CHECK_IN = "SELF_CHECK_IN"
    SELF_CHECK_OUT = "SELF_CHECK_OUT"
    REQUEST_LEAVE = "REQUEST_LEAVE"


@strawberry.enum
class SyncStatusEnum(enum.Enum):
    SUCCESS           = "SUCCESS"
    DUPLICATE_IGNORED = "DUPLICATE_IGNORED"
    VALIDATION_ERROR  = "VALIDATION_ERROR"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    CONFLICT          = "CONFLICT"
    INTERNAL_ERROR    = "INTERNAL_ERROR"


@strawberry.input
class SyncMutationInput:
    client_id: str
    mutation_type: SyncMutationTypeEnum
    payload: JSON


@strawberry.type
class SyncItemResult:
    client_id: str
    mutation_type: SyncMutationTypeEnum
    status: SyncStatusEnum
    error: Optional[str] = None
    payload_response: Optional[JSON] = None


@strawberry.type
class PushSyncPayload:
    results: List[SyncItemResult]


@strawberry.type
class PullSyncResponse:
    changes: JSON
    timestamp: float
