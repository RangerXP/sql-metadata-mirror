# SIN Classifier Backstop Strategy

**Owner:** Sean Kelley
**Purpose:** Guarantee that the Canada Social Insurance Number (SIN) appears as a sensitive classification in Purview during the demo, regardless of whether Microsoft's built-in `MICROSOFT.CANADIAN.SIN` classifier fires on the synthetic seed values.
**Premise:** You cannot personally test classifier output before the demo. So the design must be **belt-and-suspenders** — every layer below has to work *independently*. If any one of the three fires, you pass a sanity check.

---

## 1. Why a backstop is required

Microsoft's built-in `MICROSOFT.CANADIAN.SIN` classifier uses a multi-layer test:

1. **Regex** — matches a 9-digit pattern with valid Canadian first-digit (1–7 or 9; 0 and 8 are not assigned to individual SINs).
2. **Luhn checksum** — the ninth digit is a modulo-10 check digit. Only ~10% of random 9-digit numbers pass.
3. **Contextual keywords** — `SIN`, `Social Insurance Number`, `NAS`, `Numéro d'assurance sociale` near the value increase confidence.
4. **Column-name signals** — columns named `sin`, `sin_full`, `social_insurance_number` raise base confidence.
5. **Distinct/minimum match thresholds** — at least N distinct matching values and M% of sampled rows must match. Default is 60% minimum.

The risk: my original seed used `RIGHT('0000' + ABS(CHECKSUM(NEWID())) % 10000)` for the partial and a random 9-digit generator for the full. **Random 9-digit numbers fail Luhn ~90% of the time**, so the built-in classifier likely fires on fewer than 10% of seeded rows — well below the 60% default match threshold. The classifier would silently report "no PII detected" and the demo would land flat.

The backstop has three independent layers. If layer 1 works perfectly, you're done. If it doesn't, layer 2 or 3 will still produce a visible classification.

---

## 2. Layer 1 — Luhn-valid SIN generation (primary)

Generate the synthetic SINs so that they actually satisfy the built-in classifier. The Luhn algorithm in three lines:

> Starting from the rightmost digit, double every second digit. If doubling produces a value ≥ 10, sum its digits (or subtract 9). Sum all resulting digits. The number is Luhn-valid iff the sum is divisible by 10.

Canadian SIN convention I'm using:
- **First digit:** `9` (Temporary Resident SIN range). Safe and unambiguous for synthetic data — these are real-shaped values that match the classifier *and* are obviously not real persons' production numbers.
- **Digits 2–8:** random 0–9.
- **Digit 9:** Luhn check digit, computed so the full 9-digit number passes the checksum.

### Why we can't do this in pure T-SQL

T-SQL has no native modulo-arithmetic helper that handles per-digit doubling cleanly. You can write it (loop over digits, double, sum), but the script becomes 40 lines of branching that's hard to audit. **The cleanest path is to compute Luhn-valid values in Python, then push them into SQL via the existing `nb_05a_publish_synthetic_data_to_sql` notebook.**

### Python generator (drop into a notebook cell)

```python
import random

def luhn_check_digit(partial_9_first_8_digits: str) -> str:
    """Return the 9th digit that makes the full string Luhn-valid."""
    total = 0
    # Process the first 8 digits from rightmost (position 8) to leftmost (position 1)
    # In Canadian SIN, positions 2, 4, 6, 8 (1-indexed from left) get doubled
    for i, ch in enumerate(partial_9_first_8_digits):
        digit = int(ch)
        if i % 2 == 1:  # 0-indexed positions 1, 3, 5, 7 = 1-indexed positions 2, 4, 6, 8
            doubled = digit * 2
            digit = doubled if doubled < 10 else doubled - 9
        total += digit
    check = (10 - (total % 10)) % 10
    return str(check)

def generate_synthetic_sin(first_digit: str = "9") -> str:
    """Generate a Luhn-valid 9-digit Canadian SIN starting with the given first digit."""
    middle = "".join(str(random.randint(0, 9)) for _ in range(7))
    body = first_digit + middle
    check = luhn_check_digit(body)
    return body + check

# Verify (the classic Luhn-valid demo SIN from the Service Canada documentation)
assert luhn_check_digit("04657008") == "6"   # 046 570 086 — valid

# Apply to employees table — full SIN goes into dbo.employees.sin_full
# Apply to customers table — last 4 digits of a Luhn-valid SIN goes into dbo.customers.sin_last_4
def hyphenated(sin9: str) -> str:
    return f"{sin9[0:3]}-{sin9[3:6]}-{sin9[6:9]}"
```

### Where to call it

In `nb_05a_publish_synthetic_data_to_sql`, replace the random SIN block with:

```python
import pyodbc
conn = pyodbc.connect(SQL_CONN_STRING)
cur = conn.cursor()

# 1. Employees: 15 rows in our seed. Use full hyphenated SIN.
cur.execute("SELECT employee_id FROM dbo.employees")
for (emp_id,) in cur.fetchall():
    sin9 = generate_synthetic_sin(first_digit="9")
    cur.execute(
        "UPDATE dbo.employees SET sin_full = ? WHERE employee_id = ?",
        hyphenated(sin9), emp_id
    )

# 2. Customers: 50 rows. Last 4 must be from a Luhn-valid 9-digit SIN.
cur.execute("SELECT customer_id FROM dbo.customers")
for (cust_id,) in cur.fetchall():
    sin9 = generate_synthetic_sin(first_digit="9")
    cur.execute(
        "UPDATE dbo.customers SET sin_last_4 = ? WHERE customer_id = ?",
        sin9[-4:], cust_id
    )

conn.commit()
```

This pushes every SIN value to Luhn-valid before the Fabric mirror picks them up. The built-in classifier should now fire at the full 100% match rate on the `employees.sin_full` column.

### How to confirm Layer 1 works (no manual reading required)

After the Fabric scan runs, query Purview's `/catalog/api/atlas/v2/search/advanced` endpoint for any asset where `classification = "MICROSOFT.CANADIAN.SIN"`. If the result includes `dbo.employees.sin_full`, layer 1 works. The `tools/purview_custom_lineage.py` script in the demo already authenticates against Purview — extending it with a verification call is ~30 lines.

---

## 3. Layer 2 — Custom Purview SIT (independent backstop)

Even if layer 1's Luhn generation has a bug you don't catch, layer 2 should still fire because it's a **column-name + regex** classifier with no checksum requirement. Microsoft Purview lets you author a custom Sensitive Information Type (SIT) with a regex pattern, a column-name pattern, and a minimum-match threshold — all configurable.

### The classifier definition

| Property | Value | Rationale |
|----------|-------|-----------|
| **Namespace name** | `ENERCARE.PRIVACY.SIN_BACKSTOP` | Per Microsoft's classification best-practice guidance (`<company>.<business unit>.<classification>`) |
| **Friendly name** | `Enercare Canadian SIN (Backstop)` | |
| **Description** | Enercare custom SIT — backstops the built-in Canada SIN classifier; matches on column name and regex without requiring Luhn validity. | |
| **Sensitivity tier** | Highly Confidential | Same tier as built-in |
| **Match pattern (regex)** | `\b[1-79]\d{2}[\s\-]?\d{3}[\s\-]?\d{3}\b` | Three formats (hyphenated, spaced, raw); first-digit constraint excludes 0 and 8 |
| **Column-name pattern** | `^(sin|sin_full|sin_last_4|social_insurance_number|nas)$` | Column-name match raises confidence and reduces false positives |
| **Distinct match threshold** | `5` | At least 5 distinct values in the column |
| **Minimum match threshold** | `50%` | 50% of sampled values must match (loosened from default 60% so partial-SIN columns like `sin_last_4` still fire) |
| **Test text** | `946-512-378`, `944 219 358`, `935712489` | Three formats to validate the regex |

### Important: this classifier intentionally does NOT validate Luhn

Layer 2's job is to fire when layer 1 doesn't. If we required Luhn here too, layer 2 would have the same failure mode as layer 1. By relaxing to regex + column-name only, layer 2 catches the synthetic data even if its check digits are wrong.

The trade-off is more false positives in a *real* environment — but this is a demo, and the column-name constraint (`^sin.*` or `^nas$`) keeps it tight.

### How to create it

**Portal path:**
1. Purview portal → Data Map → Annotation management → Classifications → Custom tab → + New
2. Name: `ENERCARE.PRIVACY.SIN_BACKSTOP`, friendly name: `Enercare Canadian SIN (Backstop)`, description as above
3. Data Map → Classification rules → + New → Regular expression
4. Configure with pattern, column-name pattern, and thresholds above
5. Test with the three formats listed
6. Add the classification to the scan rule set used by the Enercare scans (`sqldemo`, Fabric workspace)

**API path (preferred — reproducible across tenants):**

```python
# tools/purview_create_sin_backstop.py
import requests
import json
import sys
from azure.identity import DefaultAzureCredential

PURVIEW_ACCOUNT = "Purview-West3"
BASE_URL = f"https://{PURVIEW_ACCOUNT}.purview.azure.com"

def get_token() -> str:
    cred = DefaultAzureCredential()
    return cred.get_token("https://purview.azure.net/.default").token

def create_classification(token: str):
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {
        "classificationDefs": [{
            "name": "ENERCARE.PRIVACY.SIN_BACKSTOP",
            "kind": "Custom",
            "description": "Enercare custom backstop SIT for Canadian SIN; matches column name + regex without Luhn validation.",
        }]
    }
    r = requests.put(
        f"{BASE_URL}/catalog/api/atlas/v2/types/typedefs",
        headers=headers, json=payload, timeout=60
    )
    r.raise_for_status()
    print(f"Classification created: {r.status_code}")

def create_classification_rule(token: str):
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {
        "kind": "Custom",
        "name": "ENERCARE.PRIVACY.SIN_BACKSTOP",
        "description": "Regex + column-name backstop for Canadian SIN.",
        "ruleStatus": "Enabled",
        "version": 1,
        "classificationName": "ENERCARE.PRIVACY.SIN_BACKSTOP",
        "minimumPercentageMatch": 50,
        "classificationAction": "Keep",
        "dataPatterns": [{
            "kind": "Regex",
            "pattern": r"\b[1-79]\d{2}[\s\-]?\d{3}[\s\-]?\d{3}\b"
        }],
        "columnPatterns": [{
            "kind": "Regex",
            "pattern": r"^(sin|sin_full|sin_last_4|social_insurance_number|nas)$"
        }]
    }
    r = requests.put(
        f"{BASE_URL}/scan/classificationrules/ENERCARE.PRIVACY.SIN_BACKSTOP?api-version=2022-02-01-preview",
        headers=headers, json=payload, timeout=60
    )
    r.raise_for_status()
    print(f"Classification rule created: {r.status_code}")

if __name__ == "__main__":
    token = get_token()
    create_classification(token)
    create_classification_rule(token)
```

Add this script to `tools/`. Run it once per tenant.

### How to confirm Layer 2 works

After the scan, query Purview for any asset classified with `ENERCARE.PRIVACY.SIN_BACKSTOP`. If `dbo.employees.sin_full`, `dbo.customers.sin_last_4`, or both appear, layer 2 works.

---

## 4. Layer 3 — Asset annotation (last-resort sanity check)

If both classifiers fail (which would mean either no SQL data was scanned, or the scan-rule set was misconfigured), there's still one signal that should appear: **a manual classification on the asset itself**, pushed via the Purview Atlas API.

The `tools/purview_custom_lineage.py` script in the demo already authenticates against Purview and creates entities. Add a step that **directly classifies the columns** with `MICROSOFT.CANADIAN.SIN` and `ENERCARE.PRIVACY.SIN_BACKSTOP` so the columns show as classified in the catalog UI even if no classifier ever fired during scan.

```python
# Add to tools/purview_custom_lineage.py
def classify_column(token, column_qualified_name, classifications):
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {
        "classification": {
            "typeName": classifications[0],
            "attributes": {}
        }
    }
    # Find entity by qualified name first, then add classification
    r = requests.post(
        f"{BASE_URL}/catalog/api/atlas/v2/entity/uniqueAttribute/type/column"
        f"?attr:qualifiedName={column_qualified_name}/classifications",
        headers=headers, json=payload
    )
    r.raise_for_status()

# Targets — the two SIN columns
for col in [
    "mssql://sqlserver-sk2wus3.database.windows.net/sqldemo/dbo/employees#sin_full",
    "mssql://sqlserver-sk2wus3.database.windows.net/sqldemo/dbo/customers#sin_last_4",
]:
    classify_column(token, col, ["MICROSOFT.CANADIAN.SIN"])
    classify_column(token, col, ["ENERCARE.PRIVACY.SIN_BACKSTOP"])
```

This is a **belt-and-suspenders-and-zipper** approach: even if both classifiers fail, the columns show as classified in the catalog UI because we pushed the classification labels directly to the assets.

The trade-off: this layer doesn't *prove* PII is in the column — it just claims so. Use it only as a last-resort sanity check. If you can confirm layer 1 or 2 worked, you don't need layer 3.

### How to confirm Layer 3 works

Open Purview catalog → search `sin_full` or `sin_last_4` → asset detail page should show `Canada Social Insurance Number` and `Enercare Canadian SIN (Backstop)` under Classifications.

---

## 5. Combined effect — what the demo evidence looks like

By the time the scans complete, you should see the following in Purview's classification dashboard:

| Asset | Built-in `MICROSOFT.CANADIAN.SIN` | Custom `ENERCARE.PRIVACY.SIN_BACKSTOP` | Source |
|-------|------------------------------------|------------------------------------------|--------|
| `dbo.employees.sin_full` | ✅ (layer 1 Luhn-valid generation) | ✅ (layer 2 regex + column-name match) | Layers 1 & 2 + 3 |
| `dbo.customers.sin_last_4` | ❌ (only 4 digits, no full SIN check) | ✅ (layer 2 column-name match on `sin_last_4` regardless of value count) | Layer 2 + 3 |

**Sanity check question to ask before the demo:** *Do at least one of `dbo.employees.sin_full` or `dbo.customers.sin_last_4` show any SIN-related classification in the Purview catalog?*

If yes → demo passes. If no → check that the scan rule set has both `MICROSOFT.CANADIAN.SIN` and `ENERCARE.PRIVACY.SIN_BACKSTOP` enabled, then re-run the scan.

---

## 6. What this strategy does NOT cover

- **First-digit anomaly**: I'm using `9` as the SIN first digit (Temporary Resident range). If the demo audience is a Canadian privacy expert who knows that's the temp-resident prefix, you can rotate to `1`, `2-3`, `4-5`, `6`, or `7` per region. The Luhn calculation is unchanged.
- **Production tokenization**: The full SIN is in `dbo.employees.sin_full` in plain text. This is fine for a demo on synthetic data; do not replicate this pattern in a real customer environment.
- **French keyword reinforcement**: The built-in classifier responds to French context (`numéro d'assurance sociale`, `NAS`). If you want to demonstrate bilingual detection, add a French column comment to `employees.sin_full` via `sp_addextendedproperty`. Not required for sanity check.
- **Other Canadian regulated identifiers** — Driver's License, Health Card, Passport. Same pattern would apply if you want them in the demo; not in scope for this backstop.

---

## 7. Files this design adds / updates

| Path | Purpose |
|------|---------|
| `output/purview-sin-classifier-backstop.md` | This document |
| `output/tools/purview_create_sin_backstop.py` (new) | Layer 2 — creates the custom SIT in Purview |
| `output/tools/sin_luhn_generator.py` (new) | Layer 1 — Python helpers used by `nb_05a` |
| Updates to `nb_05a_publish_synthetic_data_to_sql` notebook | Layer 1 — replace random SIN block with Luhn-valid generator |
| Updates to `tools/purview_custom_lineage.py` | Layer 3 — direct column classification as last-resort |
| `output/sql-additions/05_seed_purview_demo_data.sql` (updated note) | T-SQL seed leaves SIN columns NULL so the Python notebook can populate Luhn-valid values |
