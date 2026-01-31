# pos/query.py

from typing import List, Optional

import strawberry
from strawberry.types import Info
from asgiref.sync import sync_to_async

from employees.decorators import permission_required

from .models import POSSession, Receipt
from .types import (
    POSSessionType,
    ReceiptType,
)


# ======================================================
# POS QUERIES
# ======================================================

@strawberry.type
class POSQuery:

    # -------------------------------
    # ACTIVE SESSION (SELF)
    # -------------------------------

    @strawberry.field
    @permission_required("pos.view_orders")
    async def active_pos_session(
        self,
        info: Info,
    ) -> Optional[POSSessionType]:
        """
        Returns the currently active POS session
        for the logged-in employee.
        """

        user = info.context.user

        def fetch():
            return (
                POSSession.objects
                .filter(employee=user, is_active=True)
                .select_related("employee")
                .first()
            )

        return await sync_to_async(fetch)()


    # -------------------------------
    # POS SESSIONS (MANAGEMENT)
    # -------------------------------

    @strawberry.field
    @permission_required("pos.view_orders")
    async def pos_sessions(
        self,
        info: Info,
        employee_id: Optional[int] = None,
        active_only: bool = False,
    ) -> List[POSSessionType]:
        """
        List POS sessions (manager view).
        """

        def fetch():
            qs = (
                POSSession.objects
                .select_related("employee")
                .order_by("-opened_at")
            )

            if employee_id:
                qs = qs.filter(employee_id=employee_id)

            if active_only:
                qs = qs.filter(is_active=True)

            return list(qs)

        return await sync_to_async(fetch)()


    # -------------------------------
    # SINGLE RECEIPT
    # -------------------------------

    @strawberry.field
    @permission_required("pos.view_orders")
    async def receipt(
        self,
        info: Info,
        receipt_id: strawberry.ID,
    ) -> ReceiptType:
        """
        Fetch a single receipt by ID.
        """

        def fetch():
            return (
                Receipt.objects
                .select_related("session", "created_by")
                .get(pk=receipt_id)
            )

        return await sync_to_async(fetch)()


    @strawberry.field
    @permission_required("pos.view_orders")
    async def receipt_by_number(
        self,
        info: Info,
        receipt_number: str,
    ) -> ReceiptType:
        """
        Fetch a receipt by receipt number.
        """

        def fetch():
            return (
                Receipt.objects
                .select_related("session", "created_by")
                .get(receipt_number=receipt_number)
            )

        return await sync_to_async(fetch)()


    # -------------------------------
    # RECEIPTS BY SESSION
    # -------------------------------

    @strawberry.field
    @permission_required("pos.view_orders")
    async def receipts_by_session(
        self,
        info: Info,
        session_id: strawberry.ID,
    ) -> List[ReceiptType]:
        """
        All receipts under a POS session.
        """

        def fetch():
            return list(
                Receipt.objects
                .filter(session_id=session_id)
                .select_related("session", "created_by")
                .order_by("-created_at")
            )

        return await sync_to_async(fetch)()


    # -------------------------------
    # GENERAL RECEIPT LISTING
    # -------------------------------

    @strawberry.field
    @permission_required("pos.view_orders")
    async def receipts(
        self,
        info: Info,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[ReceiptType]:
        """
        General receipt listing with filters.
        """

        def fetch():
            qs = (
                Receipt.objects
                .select_related("session", "created_by")
                .order_by("-created_at")
            )

            if status:
                qs = qs.filter(status=status)

            return list(qs[offset : offset + limit])

        return await sync_to_async(fetch)()
