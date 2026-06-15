"""Stock locking for the K Garden single-warehouse model.

Lifecycle (one stock owner: ERPNext):
  - Sales Order submit  -> RESERVE: lock `available` qty without touching
    on-hand. A second bill cannot reserve the same units (no oversell).
  - Delivery Note submit -> DEDUCT: native ERPNext reduces on-hand and
    consumes the reservation. No code here — that is stock-standard ERPNext.
  - Sales Order cancel  -> RELEASE: any leftover reservation is freed.

Only stock items with a warehouse are reserved; non-stock items (and items
still flagged is_stock_item=0) are skipped silently, so the integration is a
no-op until a SKU is actually put under stock control.

Settings live in the single DocType "KGF Stock Settings".
"""

import frappe
from frappe import _
from frappe.utils import flt


def _settings():
    return frappe.get_cached_doc("KGF Stock Settings")


def _is_stock_item(item_code):
    return bool(frappe.get_cached_value("Item", item_code, "is_stock_item"))


def _available_to_reserve(item_code, warehouse):
    """Qty that can still be reserved = on-hand minus already-reserved.

    Uses ERPNext's canonical helper when present (v15+), else derives it
    from the Bin so the app still works on older builds.
    """
    try:
        from erpnext.stock.doctype.stock_reservation_entry.stock_reservation_entry import (
            get_available_qty_to_reserve,
        )
        return flt(get_available_qty_to_reserve(item_code, warehouse))
    except Exception:
        bin_row = frappe.db.get_value(
            "Bin", {"item_code": item_code, "warehouse": warehouse},
            ["actual_qty", "reserved_stock"], as_dict=True,
        ) or {}
        return flt(bin_row.get("actual_qty")) - flt(bin_row.get("reserved_stock"))


def set_default_warehouse(doc, method=None):
    """Stamp the shared warehouse onto any item row that lacks one."""
    s = _settings()
    if not s.enabled or not s.default_warehouse:
        return
    for row in doc.items:
        if not row.warehouse:
            row.warehouse = s.default_warehouse


def reserve_on_submit(doc, method=None):
    s = _settings()
    if not s.enabled or not s.auto_reserve:
        return

    # Idempotent: never reserve twice for the same Sales Order.
    if frappe.db.exists(
        "Stock Reservation Entry",
        {"voucher_type": "Sales Order", "voucher_no": doc.name, "docstatus": 1},
    ):
        return

    if s.block_oversell:
        _guard_oversell(doc, s)

    # Native v15+ reservation. Reserves min(available, ordered) per item; the
    # oversell guard above already ensured full availability when enabled.
    if hasattr(doc, "create_stock_reservation_entries"):
        doc.create_stock_reservation_entries(notify=False)
    else:
        frappe.log_error(
            title="KGF Stock: reservation unavailable",
            message=(
                "Sales Order has no create_stock_reservation_entries(). "
                "ERPNext < v15 — enable Stock Reservation or upgrade."
            ),
        )


def _guard_oversell(doc, s):
    for row in doc.items:
        if not _is_stock_item(row.item_code):
            continue
        warehouse = row.warehouse or s.default_warehouse
        if not warehouse:
            continue
        want = flt(row.stock_qty or row.qty)
        available = _available_to_reserve(row.item_code, warehouse)
        if want > available:
            frappe.throw(
                _("สต๊อกไม่พอ: {0} ต้องการ {1} แต่จองได้ {2} ที่คลัง {3}").format(
                    row.item_code, want, available, warehouse
                ),
                title=_("Stock not available"),
            )


def release_on_cancel(doc, method=None):
    """Free any reservation entries still open for this Sales Order.

    Native Sales Order cancel usually cancels them already; this only mops up
    leftovers (filter on docstatus=1), so it is safe to run unconditionally.
    """
    leftover = frappe.get_all(
        "Stock Reservation Entry",
        filters={"voucher_type": "Sales Order", "voucher_no": doc.name, "docstatus": 1},
        pluck="name",
    )
    for name in leftover:
        try:
            frappe.get_doc("Stock Reservation Entry", name).cancel()
        except Exception:
            frappe.log_error(
                title="KGF Stock: failed to release reservation",
                message=frappe.get_traceback(),
            )
