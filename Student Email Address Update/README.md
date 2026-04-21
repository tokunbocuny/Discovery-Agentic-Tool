# Student Email Address Update

## Project Scope

The purpose of this tool is to bulk update student email addresses between two library management systems: **ILLiad** & **Alma**.

The tool will:

1. Read all patron usernames from an ILLiad user export CSV
2. For each patron, look up their corresponding Alma account by the shared unique identifier
3. Retrieve the preferred email address from the Alma contact information section
4. Write all original ILLiad columns plus a new **Alma Email** column to an output CSV
5. The output CSV is used to bulk import updated email addresses into ILLiad

## Systems Involved

| System | Role |
|--------|------|
| **Alma** | Source of truth for student email addresses |
| **ILLiad** | Target system to be updated |

## Patron Matching

The patron identifier is the same in both Alma and ILLiad — no ID translation or mapping is required. The tool will use a single identifier to look up the user in Alma and match them directly in ILLiad.

## ILLiad Export (Required Before Each Run)

Before the sync runs, an ILLiad patron export must be placed in the project folder as `illiad_users.csv`.

**How to export from ILLiad Staff Client:**
1. Go to **Reports** → **User Reports** → **Export Users**
2. Save the file as `illiad_users.csv`
3. Place it in the `Student Email Address Update/` folder

The CSV must contain a username column. Both `Username` and `User Name` (with a space) are accepted. All other columns are ignored.

A custom file path can also be passed at runtime:
```bash
python3 email_sync.py /path/to/custom_export.csv
```

## Output Files

| File | Location | Description |
|------|----------|-------------|
| `email_update_<timestamp>.csv` | `output/` | Original ILLiad export + new `Alma Email` column for bulk import |
| `failed_updates_<timestamp>.csv` | `logs/` | Patrons where Alma lookup failed — for manual review |
| `sync_<timestamp>.log` | `logs/` | Full run log |

## Processing Rules

- **Scope:** All patrons in the ILLiad export are processed — active and expired
- **Failed records:** Any patron with no Alma email found is logged for manual review
- **Execution:** Runs on a schedule; output CSV is used to bulk import emails into ILLiad

## Institution

Bronx Community College (BCC), CUNY
Author: Tokunbo Adeshina Jr.
