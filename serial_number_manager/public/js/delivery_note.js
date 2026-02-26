/**
 * Custom script for Delivery Note DocType - Serial Number Auto-fill Fix
 *
 * Copyright (c) 2026, ahmad mohammad and contributors
 * License: MIT
 *
 * Issue: ERPNext's serial picker popup does not always appear. When the user
 * enters items manually, ERPNext auto-assigns only 1 serial regardless of qty.
 * The document cannot be submitted with the wrong count.
 *
 * Solution (client-side, for serial_no text-field case):
 *   On validate, detect when the serial_no text field has content but the count
 *   is less than qty. Clear both serial fields via frappe.model.set_value so
 *   the change is properly tracked and sent to the server.
 *
 * The server-side validate hook (delivery_note.py) handles the bundle-only
 * case (when serial_no is empty but the bundle has the wrong count).
 */

frappe.ui.form.on('Delivery Note', {
	validate: function(frm) {
		// Diagnostic: visible in browser console (F12 → Console tab)
		console.log('serial_number_manager: validate fired on Delivery Note');

		if (!frm.doc.items || !frm.doc.items.length) return;

		frm.doc.items.forEach(function(item) {
			fix_serial_number_count(item);
		});
	}
});

/**
 * Detect serial_no text-field mismatch and clear fields via Frappe's model API
 * so the change is properly tracked as dirty and sent to the server on save.
 *
 * Only handles the case where serial_no has text content with the wrong count.
 * The bundle-only case (serial_no empty, bundle has wrong count) is handled
 * by the server-side validate hook in delivery_note.py.
 *
 * @param {Object} item - Delivery Note Item row
 * @returns {boolean}   - true if fields were cleared
 */
function fix_serial_number_count(item) {
	if (!item.item_code) return false;

	let qty = flt(item.qty);
	if (qty <= 1) return false;

	let serial_no_field = (item.serial_no || '').trim();

	// Only act when the serial_no text field has content
	if (!serial_no_field) return false;

	let serial_numbers = serial_no_field
		.split(/[\n,]/)
		.map(s => s.trim())
		.filter(s => s.length > 0);

	console.log(
		`serial_number_manager: item=${item.item_code} qty=${qty} ` +
		`serial_count=${serial_numbers.length} bundle=${item.serial_and_batch_bundle || 'none'}`
	);

	// Already correct — nothing to do
	if (serial_numbers.length >= qty) return false;

	// Use frappe.model.set_value so the change is properly marked dirty
	// and included in the save payload sent to the server
	frappe.model.set_value(item.doctype, item.name, 'serial_no', '');
	frappe.model.set_value(item.doctype, item.name, 'serial_and_batch_bundle', '');

	frappe.show_alert({
		message: __('Serial number field cleared for item {0}. System will auto-fill {1} serial numbers.',
			[item.item_code, qty]),
		indicator: 'blue'
	}, 6);

	console.log(`serial_number_manager: cleared serial fields for ${item.item_code}`);
	return true;
}
