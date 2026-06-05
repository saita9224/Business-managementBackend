# POS/queries.py

from decimal import Decimal
from typing import List, Optional

import strawberry
from strawberry.types import Info
from asgiref.sync import sync_to_async

from employees.decorators import permission_required

from .models import POSSession, Receipt, MenuItem, MenuCategory, CreditAccount
from .services import ensure_default_menu_categories, get_menu_with_frequency
from .types import (
    POSSessionType,
    ReceiptType,
    MenuItemType,
    CreditAccountType,
    UnpricedProductType,
    MenuCategoryType,
)

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

    # ── CASHIER QUEUE ─────────────────────────────────────

    @strawberry.field
    @permission_required("pos.view_cashier")
    async def cashier_queue(
        self,
        info: Info,
        session_id: Optional[strawberry.ID] = None,
    ) -> List[ReceiptType]:
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

    # ── CREDIT ACCOUNTS ───────────────────────────────────

    @strawberry.field
    @permission_required("pos.settle_credit")
    async def unsettled_credits(
        self,
        info: Info,
        overdue_only: bool = False,
    ) -> List[CreditAccountType]:
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
        """
        All available menu items ordered by pin status then frequency.
        Only returns items with price > 0 so zero-priced inventory
        items don't appear on the waiter's menu until priced.
        """
        return await sync_to_async(get_menu_with_frequency)()

    @strawberry.field
    @permission_required("pos.view_orders")
    async def all_menu_items(self, info: Info) -> List[MenuItemType]:
        """
        All menu items including unavailable ones — for the Menu Manager.
        Includes zero-priced items so staff can see and price them.
        """
        def fetch():
            return list(
                MenuItem.objects
                .select_related("product")
                .order_by("-is_pinned", "name")
            )
        return await sync_to_async(fetch)()

    # ── MENU CATEGORIES ───────────────────────────────────

    @strawberry.field
    @permission_required("pos.view_orders")
    async def menu_categories(self, info: Info) -> List[MenuCategoryType]:
        """
        Returns the fixed set of menu categories defined on MenuItem.
        Used by the Menu Manager to render the category picker without
        hardcoding choices on the frontend. The counts reflect currently
        available, priced items only — same population as menu_items.
        """
        def fetch():
            from django.db.models import Count

            ensure_default_menu_categories()
            rows = (
                MenuItem.objects
                .filter(is_available=True, price__gt=Decimal("0.00"))
                .values("category")
                .annotate(count=Count("id"))
            )
            counts = {row["category"]: row["count"] for row in rows}
            categories = list(MenuCategory.objects.all())
            known = {category.key for category in categories}

            for key in sorted(set(counts) - known):
                label = " ".join(
                    part.capitalize() for part in key.replace("-", " ").split()
                )
                categories.append(MenuCategory.objects.create(key=key, label=label))

            return [
                MenuCategoryType(
                    key=category.key,
                    label=category.label,
                    count=counts.get(category.key, 0),
                )
                for category in sorted(categories, key=lambda item: item.label.lower())
            ]

        return await sync_to_async(fetch)()

    # ── UNPRICED INVENTORY ITEMS ──────────────────────────

    @strawberry.field
    @permission_required("pos.manage_menu")
    async def unpriced_inventory_items(
        self, info: Info
    ) -> List[UnpricedProductType]:
        """
        Returns inventory products with auto_deduct_on_sale=True that
        either have no MenuItem yet, or have a MenuItem with price=0.
        Shown in Menu Manager so staff can set prices before items
        appear on the waiter's menu.
        """
        def fetch():
            from inventory.models import Product as InvProduct

            no_menu = list(
                InvProduct.objects
                .filter(auto_deduct_on_sale=True, menu_item__isnull=True)
                .values("id", "name", "unit")
            )

            zero_price = list(
                InvProduct.objects
                .filter(
                    auto_deduct_on_sale=True,
                    menu_item__price=Decimal("0.00"),
                )
                .values("id", "name", "unit")
            )

            seen, results = set(), []
            for p in no_menu + zero_price:
                if p["id"] not in seen:
                    seen.add(p["id"])
                    results.append(p)
            return results

        products = await sync_to_async(fetch)()

        return [
            UnpricedProductType(
                product_id=str(p["id"]),
                product_name=p["name"],
                unit=p["unit"] or "",
            )
            for p in products
        ]
