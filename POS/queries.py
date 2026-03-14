# POS/queries.py

from typing import List, Optional
from datetime import date

import strawberry
from strawberry.types import Info
from asgiref.sync import sync_to_async

from employees.decorators import permission_required

from .models import POSSession, Receipt, MenuItem, CreditAccount
from .services import sync_inventory_to_menu, get_menu_with_frequency
from .types import POSSessionType, ReceiptType, MenuItemType, CreditAccountType

# ── shared select_related chain used everywhere ──────────
RECEIPT_SELECT = [
    "session",
    "session__employee",
    "created_by",
    "refunded_by",
]


@strawberry.type
class POSQuery:

    # ── SESSION ───────────────────────────────────────────

    @strawberry.field
    @permission_required("pos.view_orders")
    async def active_pos_session(self, info: Info) -> Optional[POSSessionType]:
        user = info.context.user
        def fetch():
            return (
                POSSession.objects
                .filter(employee=user, is_active=True)
                .select_related("employee")
                .first()
            )
        return await sync_to_async(fetch)()

    @strawberry.field
    @permission_required("pos.view_orders")
    async def pos_sessions(
        self,
        info: Info,
        employee_id: Optional[int] = None,
        active_only: bool = False,
    ) -> List[POSSessionType]:
        def fetch():
            qs = POSSession.objects.select_related("employee").order_by("-opened_at")
            if employee_id:
                qs = qs.filter(employee_id=employee_id)
            if active_only:
                qs = qs.filter(is_active=True)
            return list(qs)
        return await sync_to_async(fetch)()

    # ── RECEIPTS (WAITER) ─────────────────────────────────

    @strawberry.field
    @permission_required("pos.view_orders")
    async def receipt(self, info: Info, receipt_id: strawberry.ID) -> ReceiptType:
        def fetch():
            return (
                Receipt.objects
                .select_related(*RECEIPT_SELECT)
                .get(pk=receipt_id)
            )
        return await sync_to_async(fetch)()

    @strawberry.field
    @permission_required("pos.view_orders")
    async def receipt_by_number(self, info: Info, receipt_number: str) -> ReceiptType:
        def fetch():
            return (
                Receipt.objects
                .select_related(*RECEIPT_SELECT)
                .get(receipt_number=receipt_number)
            )
        return await sync_to_async(fetch)()

    @strawberry.field
    @permission_required("pos.view_orders")
    async def receipts_by_session(
        self, info: Info, session_id: strawberry.ID
    ) -> List[ReceiptType]:
        """Waiter's own receipts for the current session."""
        def fetch():
            return list(
                Receipt.objects
                .filter(session_id=session_id)
                .select_related(*RECEIPT_SELECT)
                .order_by("-created_at")
            )
        return await sync_to_async(fetch)()

    @strawberry.field
    @permission_required("pos.view_orders")
    async def my_pending_receipts(
        self, info: Info, session_id: strawberry.ID
    ) -> List[ReceiptType]:
        """
        Waiter — returns their own DRAFT and PENDING receipts in the
        current session so they can recall and modify them.
        """
        user = info.context.user
        def fetch():
            return list(
                Receipt.objects
                .filter(
                    session_id=session_id,
                    created_by=user,
                    status__in=[Receipt.DRAFT, Receipt.PENDING],
                )
                .select_related(*RECEIPT_SELECT)
                .order_by("-created_at")
            )
        return await sync_to_async(fetch)()

    @strawberry.field
    @permission_required("pos.view_orders")
    async def receipts(
        self,
        info: Info,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[ReceiptType]:
        def fetch():
            qs = (
                Receipt.objects
                .select_related(*RECEIPT_SELECT)
                .order_by("-created_at")
            )
            if status:
                qs = qs.filter(status=status)
            return list(qs[offset: offset + limit])
        return await sync_to_async(fetch)()

    # ── CASHIER QUEUE ────────────────────────────────────
    # Requires pos.view_cashier — only cashiers/managers see this.

    @strawberry.field
    @permission_required("pos.view_cashier")
    async def cashier_queue(
        self,
        info: Info,
        session_id: Optional[strawberry.ID] = None,
    ) -> List[ReceiptType]:
        """
        Returns all PENDING receipts ordered by submitted_at ascending
        (oldest order served first). Optionally filtered to a session.
        """
        def fetch():
            qs = (
                Receipt.objects
                .filter(status=Receipt.PENDING)
                .select_related(*RECEIPT_SELECT)
                .order_by("submitted_at")
            )
            if session_id:
                qs = qs.filter(session_id=session_id)
            return list(qs)
        return await sync_to_async(fetch)()

    @strawberry.field
    @permission_required("pos.view_cashier")
    async def open_receipts(
        self,
        info: Info,
        session_id: Optional[strawberry.ID] = None,
    ) -> List[ReceiptType]:
        """
        Returns all OPEN (partially paid) receipts for the cashier.
        """
        def fetch():
            qs = (
                Receipt.objects
                .filter(status=Receipt.OPEN)
                .select_related(*RECEIPT_SELECT)
                .order_by("submitted_at")
            )
            if session_id:
                qs = qs.filter(session_id=session_id)
            return list(qs)
        return await sync_to_async(fetch)()

    # ── CREDIT ACCOUNTS ──────────────────────────────────

    @strawberry.field
    @permission_required("pos.settle_credit")
    async def unsettled_credits(
        self,
        info: Info,
        overdue_only: bool = False,
    ) -> List[CreditAccountType]:
        """
        Returns all unsettled credit accounts.
        Pass overdue_only=true to see only those past their due date.
        Used by cashier/manager when a customer comes to settle a credit.
        """
        def fetch():
            qs = (
                CreditAccount.objects
                .filter(is_settled=False)
                .select_related(
                    "receipt",
                    "receipt__created_by",
                    "approved_by",
                    "settled_by",
                )
                .order_by("due_date")
            )
            if overdue_only:
                from django.utils import timezone
                qs = qs.filter(due_date__lt=timezone.now().date())
            return list(qs)
        return await sync_to_async(fetch)()

    @strawberry.field
    @permission_required("pos.settle_credit")
    async def credit_by_receipt(
        self,
        info: Info,
        receipt_id: strawberry.ID,
    ) -> Optional[CreditAccountType]:
        """Fetch the credit account for a specific receipt."""
        def fetch():
            return (
                CreditAccount.objects
                .filter(receipt_id=receipt_id)
                .select_related("receipt", "approved_by", "settled_by")
                .first()
            )
        return await sync_to_async(fetch)()

    # ── MENU ─────────────────────────────────────────────

    @strawberry.field
    @permission_required("pos.view_orders")
    async def menu_items(self, info: Info) -> List[MenuItemType]:
        """Available items + auto-sync inventory products."""
        await sync_to_async(sync_inventory_to_menu)()
        return await sync_to_async(get_menu_with_frequency)()

    @strawberry.field
    @permission_required("pos.view_orders")
    async def all_menu_items(self, info: Info) -> List[MenuItemType]:
        """All items including unavailable — for Menu Manager."""
        await sync_to_async(sync_inventory_to_menu)()
        def fetch():
            return list(
                MenuItem.objects
                .select_related("product")
                .order_by("-is_pinned", "name")
            )
        return await sync_to_async(fetch)()