"""Whitelisted entry points for B2C billing and fulfilment.

These are the integration surface for the future Store app / custom POS UI.
Any caller (desk UI, REST, Store app) goes through the SAME Sales Order ->
Delivery Note flow, so the stock rules in reservation.py apply uniformly.

    open_b2c_bill(...)  -> create + submit Sales Order  => stock RESERVED
    ship_bill(...)      -> create + submit Delivery Note => stock DEDUCTED

Both are idempotent via an external reference key so a retry never creates a
duplicate bill or double-cuts stock.
"""

import json

import frappe
from frappe import _
from frappe.utils import nowdate


def _loads(value):
    return json.loads(value) if isinstance(value, str) else value


@frappe.whitelist()
def open_b2c_bill(customer, items, external_ref=None, company=None, delivery_date=None):
    """Open a B2C bill = submit a Sales Order, which reserves stock.

    items: list of {item_code, qty, rate?, warehouse?}
    external_ref: caller's own id; reused -> returns the existing order
                  instead of creating a duplicate (idempotency).
    """
    items = _loads(items)
    if not items:
        frappe.throw(_("No items supplied"))

    if external_ref:
        existing = frappe.db.get_value(
            "Sales Order", {"po_no": external_ref, "docstatus": ["<", 2]}, "name"
        )
        if existing:
            return {"sales_order": existing, "duplicate": True}

    so = frappe.new_doc("Sales Order")
    so.customer = customer
    so.company = company or frappe.defaults.get_user_default("Company")
    so.transaction_date = nowdate()
    so.delivery_date = delivery_date or nowdate()
    if external_ref:
        so.po_no = external_ref
    for it in items:
        so.append("items", {
            "item_code": it["item_code"],
            "qty": it["qty"],
            "rate": it.get("rate"),
            "warehouse": it.get("warehouse"),
            "delivery_date": delivery_date or nowdate(),
        })
    so.flags.ignore_permissions = True
    so.insert()
    so.submit()  # -> reserve_on_submit hook locks the stock
    return {"sales_order": so.name, "duplicate": False}


@frappe.whitelist()
def ship_bill(sales_order):
    """Confirm/ship a bill = create + submit a Delivery Note, deducting stock.

    Idempotent: if the order is already fully delivered there is nothing left
    to ship and the existing delivery note(s) are returned.
    """
    from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note

    so = frappe.get_doc("Sales Order", sales_order)
    if so.docstatus != 1:
        frappe.throw(_("Sales Order {0} is not submitted").format(sales_order))
    if so.per_delivered and so.per_delivered >= 100:
        existing = frappe.get_all(
            "Delivery Note Item",
            filters={"against_sales_order": sales_order, "docstatus": 1},
            distinct=True, pluck="parent",
        )
        return {"delivery_notes": existing, "already_delivered": True}

    dn = make_delivery_note(sales_order)
    dn.flags.ignore_permissions = True
    dn.insert()
    dn.submit()  # native: reduces on-hand and consumes the reservation
    return {"delivery_notes": [dn.name], "already_delivered": False}
