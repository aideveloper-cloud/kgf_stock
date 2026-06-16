frappe.pages['b2c-quote'].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'ออกใบเสนอราคา B2C',
		single_column: true,
	});
	new B2CQuote(page);
};

class B2CQuote {
	constructor(page) {
		this.page = page;
		this.rows = [];
		this.doctype = 'Quotation';
		this.render();
		this.add_row();
	}

	render() {
		const body = $(this.page.body);
		body.html(`
			<div class="b2c-wrap" style="max-width:860px;margin:0 auto;">
				<div style="display:flex;gap:8px;margin-bottom:16px;">
					<button class="btn btn-sm b2c-type" data-dt="Quotation">ใบเสนอราคา</button>
					<button class="btn btn-sm b2c-type" data-dt="Sales Order">ใบสั่งขาย (ล็อคสต๊อก)</button>
				</div>
				<div class="b2c-customer" style="max-width:420px;margin-bottom:16px;"></div>
				<div style="border:1px solid var(--border-color);border-radius:8px;overflow:hidden;">
					<table class="table" style="margin:0;font-size:13px;">
						<thead><tr>
							<th style="width:46%;">สินค้า</th>
							<th style="width:14%;text-align:right;">จำนวน</th>
							<th style="width:18%;text-align:right;">ราคา/หน่วย</th>
							<th style="width:16%;text-align:right;">รวม</th>
							<th style="width:6%;"></th>
						</tr></thead>
						<tbody class="b2c-rows"></tbody>
					</table>
					<div style="padding:8px 10px;border-top:1px solid var(--border-color);">
						<button class="btn btn-xs b2c-add"><i class="fa fa-plus"></i> เพิ่มรายการ</button>
					</div>
				</div>
				<div style="display:flex;justify-content:flex-end;margin-top:16px;">
					<div style="width:300px;">
						<div style="display:flex;justify-content:space-between;padding:4px 0;">
							<span class="text-muted">รวมเงิน</span><span class="b2c-subtotal">0.00</span>
						</div>
						<div style="display:flex;justify-content:space-between;align-items:center;padding:4px 0;">
							<span class="text-muted">ส่วนลด (บาท)</span>
							<input type="number" class="form-control b2c-disc" value="0" min="0" style="width:130px;text-align:right;height:30px;">
						</div>
						<div style="display:flex;justify-content:space-between;padding:8px 0;border-top:1px solid var(--border-color);font-weight:bold;">
							<span>ยอดสุทธิ</span><span class="b2c-net" style="font-size:18px;">0.00</span>
						</div>
					</div>
				</div>
				<div style="display:flex;justify-content:flex-end;margin-top:12px;">
					<button class="btn btn-primary btn-sm b2c-save">บันทึก</button>
				</div>
			</div>
		`);

		this.customer = frappe.ui.form.make_control({
			df: { fieldtype: 'Link', options: 'Customer', label: 'ลูกค้า', reqd: 1 },
			parent: body.find('.b2c-customer'),
			render_input: true,
		});
		this.customer.refresh();

		body.find('.b2c-add').on('click', () => this.add_row());
		body.find('.b2c-disc').on('input', () => this.recompute());
		body.find('.b2c-save').on('click', () => this.save());
		body.find('.b2c-type').on('click', (e) => this.set_type($(e.currentTarget).attr('data-dt')));
		this.set_type('Quotation');
	}

	set_type(dt) {
		this.doctype = dt;
		$(this.page.body).find('.b2c-type').each((i, el) => {
			$(el).removeClass('btn-primary').toggleClass('btn-primary', $(el).attr('data-dt') === dt);
		});
	}

	add_row() {
		const tbody = $(this.page.body).find('.b2c-rows');
		const tr = $(`<tr>
			<td class="b2c-item"></td>
			<td><input type="number" class="form-control b2c-qty" value="1" min="0" style="text-align:right;height:30px;"></td>
			<td><input type="number" class="form-control b2c-rate" value="0" min="0" style="text-align:right;height:30px;"></td>
			<td class="b2c-amt" style="text-align:right;">0.00</td>
			<td style="text-align:center;"><button class="btn btn-xs b2c-del"><i class="fa fa-trash"></i></button></td>
		</tr>`);
		tbody.append(tr);

		const itemCtrl = frappe.ui.form.make_control({
			df: { fieldtype: 'Link', options: 'Item', label: '', placeholder: 'ค้นหาสินค้า' },
			parent: tr.find('.b2c-item'),
			render_input: true,
		});
		itemCtrl.refresh();

		const row = { tr, itemCtrl };
		this.rows.push(row);

		itemCtrl.$input.on('change', () => {
			const code = itemCtrl.get_value();
			if (code) {
				frappe.db.get_value('Item', code, 'standard_rate').then((r) => {
					const rate = (r.message && r.message.standard_rate) || 0;
					if (rate) tr.find('.b2c-rate').val(rate);
					this.recompute();
				});
			}
		});
		tr.find('.b2c-qty, .b2c-rate').on('input', () => this.recompute());
		tr.find('.b2c-del').on('click', () => {
			this.rows = this.rows.filter((x) => x !== row);
			tr.remove();
			this.recompute();
		});
		this.recompute();
	}

	recompute() {
		let sub = 0;
		this.rows.forEach((row) => {
			const qty = parseFloat(row.tr.find('.b2c-qty').val()) || 0;
			const rate = parseFloat(row.tr.find('.b2c-rate').val()) || 0;
			const amt = qty * rate;
			row.tr.find('.b2c-amt').text(format_currency(amt));
		});
		this.rows.forEach((row) => {
			const qty = parseFloat(row.tr.find('.b2c-qty').val()) || 0;
			const rate = parseFloat(row.tr.find('.b2c-rate').val()) || 0;
			sub += qty * rate;
		});
		const disc = parseFloat($(this.page.body).find('.b2c-disc').val()) || 0;
		$(this.page.body).find('.b2c-subtotal').text(format_currency(sub));
		$(this.page.body).find('.b2c-net').text(format_currency(Math.max(sub - disc, 0)));
	}

	collect() {
		return this.rows
			.map((row) => ({
				item_code: row.itemCtrl.get_value(),
				qty: parseFloat(row.tr.find('.b2c-qty').val()) || 0,
				rate: parseFloat(row.tr.find('.b2c-rate').val()) || 0,
			}))
			.filter((it) => it.item_code && it.qty > 0);
	}

	save() {
		const customer = this.customer.get_value();
		const items = this.collect();
		if (!customer) {
			frappe.msgprint('กรุณาเลือกลูกค้า');
			return;
		}
		if (!items.length) {
			frappe.msgprint('กรุณาเพิ่มรายการสินค้า');
			return;
		}
		const disc = parseFloat($(this.page.body).find('.b2c-disc').val()) || 0;
		frappe.call({
			method: 'kgf_stock.stock.api.create_b2c_document',
			freeze: true,
			freeze_message: 'กำลังบันทึก...',
			args: {
				doctype: this.doctype,
				customer: customer,
				items: JSON.stringify(items),
				discount_amount: disc,
			},
			callback: (r) => {
				if (r.message) {
					frappe.show_alert({ message: 'สร้าง ' + r.message.name + ' สำเร็จ', indicator: 'green' });
					frappe.set_route('Form', r.message.doctype, r.message.name);
				}
			},
		});
	}
}
