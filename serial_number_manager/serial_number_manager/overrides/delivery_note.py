"""
Delivery Note: Serial number management hooks.

1. fix_serial_count_on_validate  — Server-side safety net (validate event).
   Detects when a Serial and Batch Bundle has the wrong number of serial
   entries vs the item qty, clears the bad bundle so ERPNext can auto-assign
   the correct count on the same save.

2. add_serials_to_description_before_submit — Appends serial numbers to item
   descriptions before DN submission so they appear in the PDF.

Copyright (c) 2026, ahmad mohammad and contributors
License: MIT
"""

import frappe
from frappe.utils import cint
from serial_number_manager.serial_number_manager.utils.serial_helpers import (
	get_serial_numbers_from_bundle,
	has_serial_numbers_in_description,
	append_serial_numbers_to_description
)


def fix_serial_count_on_validate(doc, method=None):
	"""
	Hook: Delivery Note.validate

	Detects a mismatch between assigned serial numbers and item qty, then
	clears the bad data so ERPNext can auto-assign the correct count.

	Handles both ERPNext serial modes:

	  Mode A — Bundle system (use_serial_batch_fields = 0, ERPNext v15 default):
	    Serial numbers live in a Serial and Batch Bundle document linked via
	    serial_and_batch_bundle. We count the bundle's entries and delete the
	    orphaned bundle document if the count is wrong.

	  Mode B — Legacy text-field system (use_serial_batch_fields = 1):
	    Serial numbers live directly in the serial_no text field; no bundle
	    document exists. We just count newline-separated entries in serial_no.

	Only runs on draft documents (docstatus = 0).
	"""
	if doc.docstatus != 0:
		return

	for item in doc.items:
		item_qty = cint(item.qty)
		if item_qty <= 0:
			continue

		# ------------------------------------------------------------------
		# Mode A: Bundle system — serial_and_batch_bundle is set
		# ------------------------------------------------------------------
		if item.get("serial_and_batch_bundle"):
			entries = frappe.get_all(
				"Serial and Batch Entry",
				filters={
					"parent": item.serial_and_batch_bundle,
					"serial_no": ["!=", ""]
				},
				fields=["name"]
			)
			serial_count = len(entries)

			if serial_count == item_qty:
				continue  # Correct count — nothing to fix

			frappe.logger().info(
				f"DN {doc.name}, Item {item.item_code}: bundle has {serial_count} "
				f"serial(s) but qty = {item_qty}. Clearing."
			)

			bundle_name = item.serial_and_batch_bundle
			item.serial_and_batch_bundle = None
			item.serial_no = ""

			# Delete the now-orphaned draft bundle document
			try:
				if frappe.db.exists("Serial and Batch Bundle", bundle_name):
					frappe.delete_doc(
						"Serial and Batch Bundle",
						bundle_name,
						force=True,
						ignore_permissions=True
					)
			except Exception as e:
				frappe.logger().warning(
					f"DN {doc.name}: could not delete orphaned bundle {bundle_name}: {e}"
				)

			frappe.msgprint(
				frappe._("Serial numbers auto-cleared for {0} (bundle had {1}, qty = {2}). "
					"ERPNext will now auto-assign the correct serial numbers.").format(
					item.item_code, serial_count, item_qty
				),
				alert=True,
				indicator="blue"
			)

		# ------------------------------------------------------------------
		# Mode B: Legacy text-field system — serial_no has content, no bundle
		# ------------------------------------------------------------------
		elif item.get("serial_no"):
			serial_nos = [
				s.strip()
				for s in (item.serial_no or "").strip().split("\n")
				if s.strip()
			]
			serial_count = len(serial_nos)

			if serial_count == item_qty:
				continue  # Correct count — nothing to fix

			frappe.logger().info(
				f"DN {doc.name}, Item {item.item_code}: serial_no field has "
				f"{serial_count} serial(s) but qty = {item_qty}. Clearing."
			)

			item.serial_no = ""

			frappe.msgprint(
				frappe._("Serial numbers auto-cleared for {0} (had {1}, qty = {2}). "
					"ERPNext will now auto-assign the correct serial numbers.").format(
					item.item_code, serial_count, item_qty
				),
				alert=True,
				indicator="blue"
			)


def _get_serial_numbers_for_item(item):
	"""
	Extract serial numbers for a DN item regardless of which ERPNext mode is used.

	Mode A (bundle system): reads from Serial and Batch Bundle entries.
	Mode B (legacy text-field): reads directly from the serial_no text field.

	Returns a sorted list of serial number strings, or an empty list.
	"""
	# Mode A: bundle system
	if item.get("serial_and_batch_bundle"):
		return get_serial_numbers_from_bundle(item.serial_and_batch_bundle)

	# Mode B: legacy text-field system
	if item.get("serial_no"):
		return sorted([
			s.strip()
			for s in (item.serial_no or "").strip().split("\n")
			if s.strip()
		])

	return []


def add_serials_to_description_before_submit(doc, method=None):
	"""
	Hook: Delivery Note.before_submit

	Appends serial numbers to each serialized item's description so they appear
	on the submitted DN document and in its PDF.

	Works in both ERPNext serial modes:
	  Mode A — Bundle system (serial_and_batch_bundle is set)
	  Mode B — Legacy text-field system (serial_no has content)
	"""
	if not doc.items:
		return

	modified_count = 0

	for item in doc.items:
		serial_numbers = _get_serial_numbers_for_item(item)

		if not serial_numbers:
			continue

		# Prevent duplicates on re-submit / amendment
		if has_serial_numbers_in_description(item.description):
			frappe.logger().debug(
				f"Delivery Note {doc.name}, Item {item.item_code}: "
				f"Serial numbers already in description, skipping"
			)
			continue

		item.description = append_serial_numbers_to_description(
			item.description,
			serial_numbers
		)
		modified_count += 1

		frappe.logger().info(
			f"Delivery Note {doc.name}, Item {item.item_code}: "
			f"Added {len(serial_numbers)} serial numbers to description"
		)

	if modified_count > 0:
		frappe.logger().info(
			f"Delivery Note {doc.name}: Added serial numbers to {modified_count} item(s)"
		)
