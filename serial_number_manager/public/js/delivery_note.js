/**
 * Custom script for Delivery Note DocType - Serial Number Auto-fill Fix
 *
 * Copyright (c) 2026, ahmad mohammad and contributors
 * License: MIT
 *
 * Issue: When qty > 1 but user manually enters only 1 serial number in the field,
 * ERPNext doesn't auto-fill the remaining serials. User must clear the field for
 * auto-fill to work.
 *
 * Solution: On validate, detect this scenario and auto-clear both serial_no and
 * serial_and_batch_bundle so ERPNext's auto-fill mechanism populates the correct
 * number of serials on save.
 */

frappe.ui.form.on('Delivery Note', {
	validate: function(frm) {
		if (frm.doc.items && frm.doc.items.length > 0) {
			frm.doc.items.forEach(function(item) {
				fix_serial_number_count(item);
			});
		}
	}
});

frappe.ui.form.on('Delivery Note Item', {
	qty: function(_frm, cdt, cdn) {
		let item = locals[cdt][cdn];
		fix_serial_number_count(item);
	}
});

/**
 * Check if serial number count matches qty; clear both serial fields if mismatch.
 *
 * If serial_no has exactly 1 entry but qty > 1, clear both serial_no and
 * serial_and_batch_bundle so ERPNext can auto-fill the correct number on save.
 *
 * @param {Object} item - Delivery Note Item row
 */
function fix_serial_number_count(item) {
	if (!item.item_code) return;

	let serial_no_field = (item.serial_no || '').trim();
	if (!serial_no_field) return;

	let qty = flt(item.qty);
	if (qty <= 1) return;

	let serial_numbers = serial_no_field
		.split(/[\n,]/)
		.map(s => s.trim())
		.filter(s => s.length > 0);

	if (serial_numbers.length > 0 && serial_numbers.length < qty) {
		// Use direct synchronous assignment — frappe.model.set_value is async and
		// would not take effect before the save request is dispatched from validate.
		item.serial_no = '';
		if (item.hasOwnProperty('serial_and_batch_bundle')) {
			item.serial_and_batch_bundle = '';
		}

		frappe.show_alert({
			message: __('Serial number field cleared for item {0}. System will auto-fill {1} serial numbers.',
				[item.item_code, qty]),
			indicator: 'blue'
		}, 5);

		console.log(`Serial number auto-fix: Cleared fields for item ${item.item_code} (qty: ${qty}, had: ${serial_numbers.length})`);
	}
}
