# Student Email Address Update

## Project Scope

The purpose of this tool is to bulk update student email addresses between two library management systems: **ILLiad** & **Alma**.

The tool will:

1. Look up an Alma user profile by unique identifier
2. Retrieve the preferred email address from the contact information section of that profile
3. Update the associated ILLiad patron profile with the retrieved email address

## Systems Involved

| System | Role |
|--------|------|
| **Alma** | Source of truth for student email addresses |
| **ILLiad** | Target system to be updated |

## Patron Matching

The patron identifier is the same in both Alma and ILLiad — no ID translation or mapping is required. The tool will use a single identifier to look up the user in Alma and match them directly in ILLiad.

## Processing Rules

- **Scope:** All patrons that exist in both systems will be processed — regardless of active or expired status
- **Failed records:** Any patron record that fails to update will be logged for manual review in ILLiad
- **Execution:** The tool runs on a schedule (automated, not on-demand)

## Institution

Bronx Community College (BCC), CUNY
Author: Tokunbo Adeshina Jr.
