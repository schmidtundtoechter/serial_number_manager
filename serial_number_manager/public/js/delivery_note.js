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
 * Logic:
 * - If item has serial numbers enabled (has_serial_no)
 * - AND qty > 1
 * - AND serial_no field has content
 * - AND count of serials != qty
 * - THEN clear serial_no field to trigger auto-fill
 *
 * @param {Object} item - Delivery Note Item row
 */
function fix_serial_number_count(item) {
	// Only process if item has item_code
	if (!item.item_code) {
		return;
	}

	// Check if item has serial numbers enabled
	frappe.db.get_value('Item', item.item_code, 'has_serial_no', function(r) {
		if (!r || !r.has_serial_no) {
			return;
		}

		// Check qty and serial_no field
		let qty = flt(item.qty);
		let serial_no_field = (item.serial_no || '').trim();

		// If qty is 1 or less, or serial_no is empty, no action needed
		if (qty <= 1 || !serial_no_field) {
			return;
		}

		// Count serial numbers (split by newline or comma)
		let serial_numbers = serial_no_field
			.split(/[\n,]/)
			.map(s => s.trim())
			.filter(s => s.length > 0);

		let serial_count = serial_numbers.length;

		// If count doesn't match qty and only 1 serial is present, clear the field
		if (serial_count !== qty && serial_count === 1) {
			// Clear the field to allow auto-fill
			frappe.model.set_value(item.doctype, item.name, 'serial_no', '');

			// Show friendly message to user
			frappe.show_alert({
				message: __('Serial number field cleared for item {0}. System will auto-fill {1} serial numbers.',
					[item.item_code, qty]),
				indicator: 'blue'
			}, 5);

			console.log(`Serial number auto-fix: Cleared field for item ${item.item_code} (qty: ${qty}, had: ${serial_count})`);
		}
	});
}
