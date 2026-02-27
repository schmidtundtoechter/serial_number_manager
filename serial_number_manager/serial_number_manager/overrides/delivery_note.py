"""
Delivery Note: Serial number management hooks.

1. fix_serial_count_on_validate  — validate event (draft only).
   Detects wrong serial count vs item qty and auto-assigns the correct
   serial numbers from the warehouse in the same save. The user can
   review and override before submitting.

2. add_serials_to_description_on_update  — on_update event (draft only).
   After every save, writes the current serial numbers into the item
   description so they are visible and editable before submission.
   Uses frappe.db.set_value to avoid triggering a recursive save.

3. add_serials_to_description_before_submit  — before_submit event.
   Safety net only. Adds S/N to description if somehow not already there.
   Has duplicate-check so it never runs twice.

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


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_serial_numbers_for_item(item):
	"""
	Return the serial numbers currently assigned to a DN item.

	Mode A — bundle system: reads from Serial and Batch Bundle entries.
	Mode B — legacy text-field: reads directly from serial_no.

	Returns a sorted list of strings, or an empty list.
	"""
	if item.get("serial_and_batch_bundle"):
		return get_serial_numbers_from_bundle(item.serial_and_batch_bundle)

	if item.get("serial_no"):
		return sorted([
			s.strip()
			for s in (item.serial_no or "").strip().split("\n")
			if s.strip()
		])

	return []


def _auto_assign_serials(item, doc):
	"""
	Query available serial numbers from the warehouse and assign them to
	item.serial_no (Mode B / legacy text-field mode only).

	Returns True and fills item.serial_no if enough serials are available.
	Returns False if stock is insufficient (item.serial_no is left empty).
	"""
	warehouse = item.get("warehouse") or doc.get("set_warehouse")
	if not warehouse:
		return False

	item_qty = cint(item.qty)
	available = frappe.get_all(
		"Serial No",
		filters={
			"item_code": item.item_code,
			"warehouse": warehouse,
			"status": "Active"
		},
		fields=["name"],
		limit=item_qty,
		order_by="creation asc"  # oldest first (FIFO)
	)

	if len(available) >= item_qty:
		item.serial_no = "\n".join([s.name for s in available[:item_qty]])
		return True

	return False


# ---------------------------------------------------------------------------
# Hook 1: validate — fix serial count, auto-assign if needed
# ---------------------------------------------------------------------------

def fix_serial_count_on_validate(doc, method=None):
	"""
	Hook: Delivery Note.validate  (draft only)

	Detects a mismatch between the number of assigned serial numbers and the
	item quantity, then auto-assigns the correct serials from the warehouse in
	the same save — so the user can review and change them before submitting.

	Mode A — Bundle system (serial_and_batch_bundle is set):
	  Counts bundle entries; if wrong, deletes the bad bundle and clears both
	  fields. ERPNext will re-create the bundle on submit.

	Mode B — Legacy text-field (use_serial_batch_fields = 1):
	  Counts newline-separated entries in serial_no; if wrong, queries the
	  warehouse for available serial numbers and assigns them directly.
	"""
	if doc.docstatus != 0:
		return

	for item in doc.items:
		item_qty = cint(item.qty)
		if item_qty <= 0:
			continue

		# ── Mode A: Bundle system ──────────────────────────────────────────
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
				frappe._("Serial bundle cleared for {0} (had {1}, qty = {2}). "
					"Assign serial numbers before submitting.").format(
					item.item_code, serial_count, item_qty
				),
				alert=True,
				indicator="blue"
			)

		# ── Mode B: Legacy text-field system ──────────────────────────────
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
				f"DN {doc.name}, Item {item.item_code}: serial_no has {serial_count} "
				f"serial(s) but qty = {item_qty}. Auto-assigning."
			)

			assigned = _auto_assign_serials(item, doc)

			if assigned:
				assigned_list = [s.strip() for s in item.serial_no.split("\n") if s.strip()]
				frappe.msgprint(
					frappe._("Auto-assigned {0} serial number(s) for {1}: {2}").format(
						item_qty,
						item.item_code,
						", ".join(assigned_list)
					),
					alert=True,
					indicator="blue"
				)
				frappe.logger().info(
					f"DN {doc.name}, Item {item.item_code}: auto-assigned {item_qty} serial(s)"
				)
			else:
				item.serial_no = ""
				frappe.msgprint(
					frappe._("Not enough serial numbers in stock for {0} "
						"(need {1}). Please assign manually.").format(
						item.item_code, item_qty
					),
					alert=True,
					indicator="orange"
				)


# ---------------------------------------------------------------------------
# Hook 2: on_update — write S/N into description after every save
# ---------------------------------------------------------------------------

def add_serials_to_description_on_update(doc, method=None):
	"""
	Hook: Delivery Note.on_update  (draft only)

	After every save, checks each item for assigned serial numbers and appends
	them to the item description so the user can see them before submitting.

	Uses frappe.db.set_value to update only the description column directly —
	this avoids triggering another save/validate cycle (no recursion).
	"""
	if doc.docstatus != 0:
		return

	for item in doc.items:
		serial_numbers = _get_serial_numbers_for_item(item)

		if not serial_numbers:
			continue

		if has_serial_numbers_in_description(item.description):
			continue  # Already shows S/N — skip

		new_description = append_serial_numbers_to_description(
			item.description,
			serial_numbers
		)

		frappe.db.set_value(
			"Delivery Note Item",
			item.name,
			"description",
			new_description
		)

		frappe.logger().info(
			f"DN {doc.name}, Item {item.item_code}: "
			f"Added {len(serial_numbers)} serial(s) to description on save"
		)


# ---------------------------------------------------------------------------
# Hook 3: before_submit — safety net only (duplicate-safe)
# ---------------------------------------------------------------------------

def add_serials_to_description_before_submit(doc, method=None):
	"""
	Hook: Delivery Note.before_submit  — safety net only.

	Adds S/N to item description if it is somehow not already there.
	The duplicate check (has_serial_numbers_in_description) ensures this
	never runs twice or overwrites what on_update already wrote.
	"""
	if not doc.items:
		return

	modified_count = 0

	for item in doc.items:
		serial_numbers = _get_serial_numbers_for_item(item)

		if not serial_numbers:
			continue

		if has_serial_numbers_in_description(item.description):
			continue  # Already there — nothing to do

		item.description = append_serial_numbers_to_description(
			item.description,
			serial_numbers
		)
		modified_count += 1

		frappe.logger().info(
			f"DN {doc.name}, Item {item.item_code}: "
			f"Safety net added {len(serial_numbers)} serial(s) to description on submit"
		)

	if modified_count > 0:
		frappe.logger().info(
			f"DN {doc.name}: safety net added serial descriptions for {modified_count} item(s)"
		)


# ---------------------------------------------------------------------------
# Hook 4: on_submit — reliable fallback after bundle is fully committed
# ---------------------------------------------------------------------------

def add_serials_to_description_on_submit(doc, method=None):
	"""
	Hook: Delivery Note.on_submit

	Runs after the DN is submitted and all Serial and Batch Bundles are fully
	committed to the database. This is the most reliable point to read bundle
	entries, since the bundle is now in its final submitted state.

	Uses frappe.db.set_value to update descriptions directly — this avoids
	triggering another save cycle while ensuring the printed DN is correct.

	This complements before_submit: if before_submit already added serial
	numbers (duplicate check via has_serial_numbers_in_description), this hook
	is a no-op. It only acts when before_submit missed them.
	"""
	if not doc.items:
		return

	modified_count = 0

	for item in doc.items:
		serial_numbers = _get_serial_numbers_for_item(item)

		if not serial_numbers:
			continue

		if has_serial_numbers_in_description(item.description):
			continue  # Already there — nothing to do

		new_description = append_serial_numbers_to_description(
			item.description,
			serial_numbers
		)

		frappe.db.set_value(
			"Delivery Note Item",
			item.name,
			"description",
			new_description
		)

		frappe.logger().info(
			f"DN {doc.name}, Item {item.item_code}: "
			f"on_submit added {len(serial_numbers)} serial(s) to description"
		)
		modified_count += 1

	if modified_count > 0:
		frappe.logger().info(
			f"DN {doc.name}: on_submit added serial descriptions for {modified_count} item(s)"
		)
