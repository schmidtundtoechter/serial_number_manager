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
 * Solution: Before save, detect this scenario and auto-clear the serial_no field
 * to allow ERPNext's auto-fill mechanism to populate correct number of serials.
 */

frappe.ui.form.on('Delivery Note', {
	before_save: function(frm) {
		// Process each item before save
		if (frm.doc.items && frm.doc.items.length > 0) {
			frm.doc.items.forEach(function(item) {
				fix_serial_number_count(item);
			});
		}
	}
});

frappe.ui.form.on('Delivery Note Item', {
	qty: function(frm, cdt, cdn) {
		// Also check when qty changes
		let item = locals[cdt][cdn];
		fix_serial_number_count(item);
	},

	serial_no: function(frm, cdt, cdn) {
		// Check when serial_no field is manually edited
		let item = locals[cdt][cdn];
		fix_serial_number_count(item);
	}
});

/**
 * Check if serial number count matches qty, clear if mismatch.
 *
 * Logic (synchronous - no async DB call needed):
 * - If serial_no has content, item is serialized (ERPNext only fills this for serialized items)
 * - AND qty > 1
 * - AND exactly 1 serial is entered but qty > 1
 * - THEN clear serial_no field to trigger ERPNext's auto-fill on save
 *
 * @param {Object} item - Delivery Note Item row
 */
function fix_serial_number_count(item) {
	// Only process if item has item_code
	if (!item.item_code) {
		return;
	}

	let serial_no_field = (item.serial_no || '').trim();

	// If serial_no is empty, no action needed
	// (item is not serialized, or user hasn't entered anything yet)
	if (!serial_no_field) {
		return;
	}

	let qty = flt(item.qty);

	// If qty is 1 or less, no mismatch possible
	if (qty <= 1) {
		return;
	}

	// Count serial numbers (split by newline or comma)
	let serial_numbers = serial_no_field
		.split(/[\n,]/)
		.map(s => s.trim())
		.filter(s => s.length > 0);

	let serial_count = serial_numbers.length;

	// If exactly 1 serial entered but qty > 1, clear the field to allow auto-fill
	if (serial_count === 1) {
		frappe.model.set_value(item.doctype, item.name, 'serial_no', '');

		frappe.show_alert({
			message: __('Serial number field cleared for item {0}. System will auto-fill {1} serial numbers.',
				[item.item_code, qty]),
			indicator: 'blue'
		}, 5);

		console.log(`Serial number auto-fix: Cleared field for item ${item.item_code} (qty: ${qty}, had: ${serial_count})`);
	}
}
