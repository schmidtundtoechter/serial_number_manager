"""
Shared utility functions for serial number management.

These functions are used by both Delivery Note and Sales Invoice handlers
to extract, format, and append serial numbers to item descriptions.

Copyright (c) 2026, ahmad mohammad and contributors
License: MIT
"""

import frappe
from frappe.utils import cstr
from bs4 import BeautifulSoup


def get_serial_numbers_from_bundle(bundle_id):
	"""
	Retrieve serial numbers from a Serial and Batch Bundle.

	Uses ERPNext's built-in function to get serial numbers from the bundle doctype.
	Returns a sorted list of serial number strings.

	Args:
		bundle_id (str): Name of the Serial and Batch Bundle document

	Returns:
		list: List of serial number strings, sorted alphabetically

	Example:
		>>> get_serial_numbers_from_bundle("SABB-00001")
		['SN-001', 'SN-002', 'SN-003']
	"""
	if not bundle_id:
		return []

	try:
		# Use ERPNext's built-in function to get serial numbers from bundle
		from erpnext.stock.serial_batch_bundle import get_serial_nos

		serial_numbers = get_serial_nos(bundle_id)
		return sorted(serial_numbers) if serial_numbers else []

	except Exception as e:
		frappe.log_error(
			f"Failed to get serial numbers from bundle {bundle_id}: {str(e)}",
			"Serial Number Retrieval Failed"
		)
		return []


def has_serial_numbers_in_description(description):
	"""
	Check if description already contains a serial number section.

	Looks for the "S/N:" marker in the description text to prevent
	duplicate serial number additions.

	Args:
		description (str): HTML description text to check

	Returns:
		bool: True if "S/N:" marker exists in the description

	Example:
		>>> has_serial_numbers_in_description("<p>Item description</p><p>S/N:</p>")
		True
		>>> has_serial_numbers_in_description("<p>Item description</p>")
		False
	"""
	if not description:
		return False

	# Convert HTML to plain text for checking
	from frappe.utils import strip_html
	plain_text = strip_html(cstr(description))

	# Check for both "S/N:" and "S/N :" variants
	return "S/N:" in plain_text or "S/N :" in plain_text


def append_serial_numbers_to_description(description, serial_numbers):
	"""
	Append serial numbers to item description in a structured HTML format.

	Formats serial numbers as:
		[Existing description]

		S/N:
		SERIAL01
		SERIAL02
		SERIAL03

	Args:
		description (str): Current HTML description
		serial_numbers (list): List of serial number strings

	Returns:
		str: Updated HTML description with serial numbers appended

	Example:
		>>> desc = "<p>Laptop Computer</p>"
		>>> serials = ["SN-001", "SN-002"]
		>>> result = append_serial_numbers_to_description(desc, serials)
		>>> "S/N:" in result
		True
	"""
	if not serial_numbers:
		return description

	# Build serial number section HTML
	serial_section = "<p><strong>S/N:</strong></p>"
	for serial in serial_numbers:
		# Escape HTML to prevent injection
		safe_serial = frappe.utils.escape_html(cstr(serial))
		serial_section += f"<p>{safe_serial}</p>"

	# Parse existing description
	description = cstr(description).strip()

	# If description is empty, return just the serial section
	if not description:
		return serial_section

	# Use BeautifulSoup to safely manipulate HTML
	soup = BeautifulSoup(description, 'html.parser')

	# Find or create a wrapper div for the content
	wrapper_div = soup.find('div')
	if not wrapper_div:
		# Create a div to wrap all content
		wrapper_div = soup.new_tag('div')
		# Move all existing content into the div
		for element in list(soup.children):
			wrapper_div.append(element.extract())
		soup.append(wrapper_div)

	# Add a blank line separator
	blank_p = soup.new_tag('p')
	wrapper_div.append(blank_p)

	# Parse and append the serial section
	serial_soup = BeautifulSoup(serial_section, 'html.parser')
	for element in serial_soup.children:
		wrapper_div.append(element)

	return str(soup)


def format_serial_numbers_for_display(serial_numbers):
	"""
	Format serial numbers for plain text display.

	This is a helper function that can be used for logging or
	non-HTML contexts.

	Args:
		serial_numbers (list): List of serial number strings

	Returns:
		str: Formatted string with serial numbers

	Example:
		>>> format_serial_numbers_for_display(['SN-001', 'SN-002'])
		'S/N:\\nSN-001\\nSN-002'
	"""
	if not serial_numbers:
		return ""

	return "S/N:\n" + "\n".join(serial_numbers)
