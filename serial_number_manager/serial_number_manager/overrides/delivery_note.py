"""
Delivery Note: Add serial numbers to item descriptions on submit.

When a Delivery Note is submitted with serialized items, this module appends
the serial numbers to each item's description field in the format:

S/N:
SERIAL01
SERIAL02
SERIAL03

This ensures serial numbers appear on delivery documents and PDFs.

Copyright (c) 2026, ahmad mohammad and contributors
License: MIT
"""

import frappe
from serial_number_manager.serial_number_manager.utils.serial_helpers import (
	get_serial_numbers_from_bundle,
	has_serial_numbers_in_description,
	append_serial_numbers_to_description
)


def add_serials_to_description_before_submit(doc, method=None):
	"""
	Hook: Delivery Note.before_submit

	Appends serial numbers to item descriptions before DN submission is finalized.
	Only processes items with serial_and_batch_bundle set.

	The function:
	1. Loops through all items in the Delivery Note
	2. Checks if item has a serial_and_batch_bundle
	3. Retrieves serial numbers from the bundle
	4. Checks if serial numbers already exist in description (prevent duplicates)
	5. Appends serial numbers to the item description in HTML format

	Args:
		doc (Document): Delivery Note document object
		method (str, optional): Hook method name (not used)

	Returns:
		None: Modifies doc.items[].description in place

	Example workflow:
		1. User creates Delivery Note with serialized item (qty=3)
		2. User assigns 3 serial numbers via serial_and_batch_bundle
		3. User submits Delivery Note
		4. This hook triggers on_submit
		5. Serial numbers are appended to item description
		6. PDF generated shows serial numbers in item description
	"""
	if not doc.items:
		return

	# Track if any descriptions were modified
	modified_count = 0

	for item in doc.items:
		# Only process items with serial numbers
		if not item.serial_and_batch_bundle:
			continue

		# Get serial numbers from bundle
		serial_numbers = get_serial_numbers_from_bundle(item.serial_and_batch_bundle)

		if not serial_numbers:
			# Log warning if bundle exists but has no serial numbers
			frappe.logger().warning(
				f"Delivery Note {doc.name}, Item {item.item_code}: "
				f"Serial bundle {item.serial_and_batch_bundle} has no serial numbers"
			)
			continue

		# Check if description already has serial numbers (prevent duplicates)
		if has_serial_numbers_in_description(item.description):
			frappe.logger().debug(
				f"Delivery Note {doc.name}, Item {item.item_code}: "
				f"Serial numbers already in description, skipping"
			)
			continue

		# Append serial numbers to description
		original_description = item.description
		item.description = append_serial_numbers_to_description(
			item.description,
			serial_numbers
		)

		modified_count += 1

		frappe.logger().info(
			f"Delivery Note {doc.name}, Item {item.item_code}: "
			f"Added {len(serial_numbers)} serial numbers to description"
		)

	# Log summary if any modifications were made
	if modified_count > 0:
		frappe.logger().info(
			f"Delivery Note {doc.name}: Added serial numbers to {modified_count} item(s)"
		)
