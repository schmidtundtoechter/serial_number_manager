Serial Number Manager – Simplified Test Plan (Manager View)
What was implemented (1-minute overview)

The feature does two things:

Automatically shows serial numbers on customer documents

Serial numbers appear in Delivery Notes & Sales Invoices

They are visible in the PDF sent to customers

Fixes a known ERPNext bug

When quantity > 1 and only one serial number is entered, the system now:

Clears the wrong input

Auto-fills correct serial numbers

Shows a clear info message to the user

Pre-Conditions (Important)

Before testing, make sure:

Item is a Stock Item

Item has “Has Serial No” enabled

Serial numbers exist in stock

Test 1 – Delivery Note shows Serial Numbers

Goal: Serial numbers appear automatically after submit.

Steps

Create Sales Order (qty > 1 for a serialized item)

Create Delivery Note from it

Pick serial numbers via Pick Serial / Batch No

Submit the Delivery Note

Open item → check Description

Open Print / PDF

Expected

Serial numbers appear in:

Item description

Delivery Note PDF

Test 2 – Sales Invoice inherits Serial Numbers

Goal: Serial numbers flow correctly from DN → SI.

Steps

Create Sales Invoice from submitted Delivery Note

Submit the Sales Invoice

Check item description

Open PDF

Open a Serial No record

Expected

Same serial numbers visible on SI & PDF

Serial No record shows:

Sales Invoice link

Sales Invoice date

Test 3 – Bug Fix (Qty > 1, wrong serial input)

Goal: ERPNext bug is handled automatically.

Steps

Create Delivery Note

Set quantity = 5

Manually type only ONE serial number

Click Save

Expected

Blue info message appears

Serial field is auto-cleared

System auto-fills correct serials

Document submits without error

Test 4 – Full Business Flow (Real Scenario)

Goal: Ensure nothing breaks in real usage.

Steps

Create Sales Order with:

One serialized item

One normal item

Create & submit Delivery Note

Create & submit Sales Invoice

Check both PDFs

Expected

Serialized item → shows serial numbers

Normal item → unchanged

End-to-end flow works

Test 5 – Amendment Safety

Goal: No duplicate serial numbers.

Steps

Open a submitted Delivery Note

Click Amend

Submit amended version

Check item description

Expected

Serial numbers appear only once

No duplication

Final Acceptance Criteria (✔ Checklist)

✔ Serial numbers appear on Delivery Notes
✔ Serial numbers appear on Sales Invoices
✔ Serial numbers visible in PDFs
✔ Serial No records updated correctly
✔ ERPNext serial bug is fixed
✔ No duplication on amendment
✔ Non-serialized items unaffected