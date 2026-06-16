# KGF Stock — ล็อคสต๊อกตอนเปิดบิล, ตัดตอนส่งของ

สต๊อกมีเจ้าของเดียวคือ ERPNext ทุกช่องทาง (B2C, B2B, Store app ในอนาคต)
ผ่านโมเดลเดียวกัน:

```
เปิดบิล (Sales Order submit)   ──► RESERVE  ล็อค available ไม่แตะ on-hand
"เปิด PO" / ส่งของ (Delivery Note) ──► DEDUCT  ตัด on-hand จริง + ปลด reservation
ยกเลิกบิล (Sales Order cancel)  ──► RELEASE  คืน available อัตโนมัติ
```

- ใช้ **Stock Reservation** ของ ERPNext v15+ (native) — ไม่มี stock count ที่อื่น
- ตัด ณ **Delivery Note** (ส่งของ) · **คลังเดียวรวม** (ตั้งใน KGF Stock Settings)
- กัน oversell: ถ้า available < จำนวนที่ขอ → บล็อกการ submit Sales Order

## ตั้งค่า (KGF Stock Settings — single DocType)

ค้นหา "KGF Stock Settings" ใน ERPNext แล้วตั้ง:

| ฟิลด์ | ค่า |
|---|---|
| Enable stock locking | ✅ |
| Default Warehouse | คลังหลักที่ใช้ตัด (เช่น Stores - KGF) |
| Reserve stock on Sales Order submit | ✅ |
| Block oversell | ✅ |

## Precondition (สำคัญ — ไม่ทำ = ระบบเงียบ ไม่ล็อกอะไร)

สินค้าที่ pull มาจาก FlowAccount เป็น `is_stock_item = 0` ทั้งหมด การ reserve ใช้ได้
เฉพาะ stock item เท่านั้น ดังนั้นต้อง:

1. เปิด `is_stock_item = 1` เฉพาะ SKU ที่จะคุมสต๊อกจริง
2. นับสต๊อกจริง → ทำ **Stock Reconciliation** หนึ่งครั้งใส่ยอดตั้งต้น
3. ตั้ง Default Warehouse ใน settings

จนกว่าจะทำครบ ระบบจะไม่ error แต่จะ "ไม่ล็อก" สินค้า non-stock (no-op โดยตั้งใจ)

## API สำหรับ Store app / custom UI (idempotent)

```python
# เปิดบิล B2C -> ล็อคสต๊อก
kgf_stock.stock.api.open_b2c_bill(
    customer="ลูกค้า ก",
    items=[{"item_code": "EF5V190DGY-3", "qty": 5, "rate": 1490}],
    external_ref="STORE-0001",   # ยิงซ้ำด้วย ref เดิม -> คืน order เดิม ไม่สร้างซ้ำ
)

# ส่งของ -> ตัดสต๊อกจริง
kgf_stock.stock.api.ship_bill(sales_order="SAL-ORD-2026-00001")
```

เรียกผ่าน REST: `POST /api/method/kgf_stock.stock.api.open_b2c_bill`

## ทดสอบบน UAT (ลำดับ)

1. สร้าง Warehouse + ตั้งใน settings
2. เลือก Item 1 ตัว → เปิด is_stock_item → Stock Reconciliation ใส่ยอด 10
3. เปิดบิล qty 3 (Sales Order submit) → เช็ค: Stock Reservation Entry เกิด 1 รายการ, available เหลือ 7, on-hand ยัง 10
4. เปิดบิลอีกใบ qty 8 → ต้องโดน **บล็อก** (available 7 < 8)
5. ส่งของใบแรก (Delivery Note) → on-hand เหลือ 7, reservation ถูก consume
6. ยกเลิก Sales Order ที่ยังไม่ส่ง → available คืนกลับ

## หน้า UI ออกใบเสนอราคา B2C

custom desk page ที่ `/app/b2c-quote` — UI เราออกเอง (ไม่ใช่ฟอร์มมาตรฐาน):
- เลือก **ใบเสนอราคา** (Quotation, ไม่ล็อคสต๊อก) หรือ **ใบสั่งขาย** (Sales Order, ล็อคสต๊อกผ่าน kgf_stock)
- ค้นหาลูกค้า/สินค้าจากของจริงใน ERPNext (autocomplete), ดึงราคามาตรฐานอัตโนมัติ
- เพิ่ม/ลบรายการ, คำนวณยอดสด, ใส่ส่วนลด (บาท)
- บันทึก → สร้างเอกสารผ่าน `kgf_stock.stock.api.create_b2c_document` แล้วเปิดเอกสารที่สร้าง
- ใบเสนอราคา B2C ตั้ง `flowaccount_entity = "ERPNext Only"` ให้อัตโนมัติ (ไม่ push เข้า FlowAccount)

## โครงสร้างไฟล์
```
kgf_stock/
  hooks.py                         # ผูก event ของ Sales Order
  stock/
    reservation.py                 # reserve/guard/release (hooks)
    api.py                         # open_b2c_bill, ship_bill (whitelisted)
  kgf_stock/doctype/kgf_stock_settings/   # single DocType ตั้งค่า
```
