app_name = "kgf_stock"
app_title = "KGF Stock"
app_publisher = "K Garden"
app_description = "Stock reservation on Sales Order, deduction on Delivery Note"
app_email = "ai.developer@kgarden.local"
app_license = "MIT"

# Stock model:
#   open bill (B2C / B2B / Store app) -> Sales Order submit -> RESERVE (lock available)
#   confirm/ship  ("เปิด PO")          -> Delivery Note submit -> DEDUCT on-hand (native)
# A single shared warehouse; default comes from KGF Stock Settings.
doc_events = {
    "Sales Order": {
        "validate": "kgf_stock.stock.reservation.set_default_warehouse",
        "on_submit": "kgf_stock.stock.reservation.reserve_on_submit",
        "on_cancel": "kgf_stock.stock.reservation.release_on_cancel",
    },
}
