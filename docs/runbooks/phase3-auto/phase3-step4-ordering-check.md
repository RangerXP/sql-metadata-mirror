# Phase 3 Step 4 Ordering Check

## Required token order

1. Account Status
2. Service History
3. Billing Status
4. Support Call History
5. Decision SLA

## Draft stage config

- all_found: True
- ascending: True
- indexes: 791, 840, 4301, 5091, 6100

## Published stage config

- all_found: True
- ascending: True
- indexes: 791, 840, 4301, 5091, 6100

## Result

- pass: True
- note: This is a token-order guard and should be paired with runtime prompt checks in Fabric.
