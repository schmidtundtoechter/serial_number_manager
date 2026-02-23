"""
Sales Invoice: Copy serial numbers from linked Delivery Note and update Serial No doctype.

When a Sales Invoice is submitted:
1. Gets serial numbers from linked Delivery Note items
2. Adds them to Sales Invoice item descriptions
3. Updates Serial No doctype with SI submission date and link

This ensures proper tracking and PDF documentation of serial numbers.

Copyright (c) 2026, ahmad mohammad and contributors
License: MIT
"""

import frappe
from frappe.utils import today
from serial_number_manager.serial_number_manager.utils.serial_helpers import (
	get_serial_numbers_from_bundle,
	has_serial_numbers_in_description,
	append_serial_numbers_to_description
)


def add_serials_from_dn_on_submit(doc, method=None):
	"""
	Hook: Sales Invoice.before_submit

	For each SI item linked to a DN:
	1. Get serial numbers from DN item's bundle
	2. Add to SI item description (if not already there)
	3. Update Serial No doctype records

	Args:
		doc (Document): Sales Invoice document object
		method (str, optional): Hook method name (not used)

	Returns:
		None: Modifies doc.items[].description in place

	Example workflow:
		1. User creates Sales Invoice from Delivery Note
		2. SI item has dn_detail link to DN item
		3. User submits Sales Invoice
		4. This hook triggers before_submit
		5. Serial numbers are copied from DN to SI description
		6. Serial No records are updated with SI reference
		7. PDF generated shows serial numbers
	"""
	if not doc.items:
		return

	# Track modifications
	modified_count = 0

	for item in doc.items:
		# Find the linked Delivery Note item.
		# Two paths depending on how the SI was created:
		# - From Delivery Note: item.dn_detail is set directly
		# - From Sales Order: only item.so_detail is set; find DN item via SO item reference
		dn_item = None

		if item.dn_detail:
			dn_item = frappe.db.get_value(
				"Delivery Note Item",
				item.dn_detail,
				["parent", "serial_and_batch_bundle"],
				as_dict=True
			)
		elif item.so_detail:
			# SI was created from SO: look up submitted DN items via the shared so_detail reference
			candidates = frappe.db.get_all(
				"Delivery Note Item",
				filters={"so_detail": item.so_detail},
				fields=["name", "parent", "serial_and_batch_bundle"],
				limit=5
			)
			for candidate in candidates:
				if frappe.db.get_value("Delivery Note", candidate.parent, "docstatus") == 1:
					dn_item = candidate
					break

		if not dn_item:
			if item.dn_detail or item.so_detail:
				frappe.logger().warning(
					f"Sales Invoice {doc.name}, Item {item.item_code}: "
					f"No submitted Delivery Note item found (dn_detail={item.dn_detail}, so_detail={item.so_detail})"
				)
			continue

		if not dn_item.serial_and_batch_bundle:
			# Item is not serialized or has no serial numbers
			continue

		# Get serial numbers from DN bundle
		serial_numbers = get_serial_numbers_from_bundle(dn_item.serial_and_batch_bundle)

		if not serial_numbers:
			frappe.logger().warning(
				f"Sales Invoice {doc.name}, Item {item.item_code}: "
				f"DN bundle {dn_item.serial_and_batch_bundle} has no serial numbers"
			)
			continue

		# Add to description if not already there
		if not has_serial_numbers_in_description(item.description):
			item.description = append_serial_numbers_to_description(
				item.description,
				serial_numbers
			)
			modified_count += 1

			frappe.logger().info(
				f"Sales Invoice {doc.name}, Item {item.item_code}: "
				f"Added {len(serial_numbers)} serial numbers to description"
			)

		# Update Serial No doctype records with SI information
		update_serial_no_records(
			serial_numbers,
			doc.name,
			doc.posting_date or today()
		)

	# Log summary
	if modified_count > 0:
		frappe.logger().info(
			f"Sales Invoice {doc.name}: Added serial numbers to {modified_count} item(s)"
		)


def update_serial_no_records(serial_numbers, sales_invoice, submission_date):
	"""
	Update Serial No doctype with Sales Invoice details.

	Updates each serial number's record with:
	- custom_sales_invoice_date: Date of SI submission
	- custom_sales_invoice: Link to Sales Invoice

	Note: This requires custom fields to be added to Serial No doctype via fixtures.

	Args:
		serial_numbers (list): List of serial number strings
		sales_invoice (str): Sales Invoice name
		submission_date (date): Date of SI submission

	Returns:
		None: Updates database directly

	Example:
		>>> update_serial_no_records(['SN-001', 'SN-002'], 'SI-00001', '2026-02-22')
		# Updates Serial No records SN-001 and SN-002 with SI reference
	"""
	if not serial_numbers:
		return

	# Check if custom fields exist on Serial No doctype
	has_si_date_field = frappe.db.exists(
		"Custom Field",
		"Serial No-custom_sales_invoice_date"
	)
	has_si_link_field = frappe.db.exists(
		"Custom Field",
		"Serial No-custom_sales_invoice"
	)

	if not has_si_date_field or not has_si_link_field:
		frappe.log_error(
			f"Custom fields missing on Serial No doctype for tracking Sales Invoice.\n"
			f"Expected fields: custom_sales_invoice_date, custom_sales_invoice\n"
			f"Sales Invoice: {sales_invoice}\n"
			f"Serial Numbers: {', '.join(serial_numbers)}",
			"Serial No Update Failed"
		)
		return

	# Bulk update for performance
	updated_count = 0
	failed_serials = []

	for serial_no in serial_numbers:
		try:
			# Check if Serial No exists
			if not frappe.db.exists("Serial No", serial_no):
				frappe.logger().warning(
					f"Serial No {serial_no} does not exist in database, skipping update"
				)
				failed_serials.append(serial_no)
				continue

			# Update via db_set to avoid triggering validation
			frappe.db.set_value(
				"Serial No",
				serial_no,
				{
					"custom_sales_invoice_date": submission_date,
					"custom_sales_invoice": sales_invoice
				},
				update_modified=True
			)

			updated_count += 1

		except Exception as e:
			frappe.logger().error(
				f"Failed to update Serial No {serial_no} with SI {sales_invoice}: {str(e)}"
			)
			failed_serials.append(serial_no)

	# Log summary
	if updated_count > 0:
		frappe.logger().info(
			f"Updated {updated_count} serial number(s) with SI {sales_invoice}"
		)

	if failed_serials:
		frappe.log_error(
			f"Failed to update {len(failed_serials)} serial number(s) for SI {sales_invoice}:\n"
			f"{', '.join(failed_serials)}",
			"Serial No Update Partial Failure"
		)
