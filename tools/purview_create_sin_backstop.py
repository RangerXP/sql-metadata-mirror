"""
Purview SIN Backstop Classifier — Layer 2 of the SIN classifier backstop strategy.

Creates a custom Sensitive Information Type (SIT) in Purview-West3 that fires
on column-name + regex match, without requiring a Luhn checksum. This guarantees
SIN columns appear classified in Purview even when the synthetic seed values
fail to satisfy Microsoft's built-in MICROSOFT.CANADIAN.SIN classifier.

Run once per tenant after the Purview account is provisioned.

See docs/purview-sin-classifier-backstop.md for the full strategy.
"""

import sys
import requests
from azure.identity import DefaultAzureCredential

PURVIEW_ACCOUNT = "Purview-West3"
BASE_URL = f"https://{PURVIEW_ACCOUNT}.purview.azure.com"

CLASSIFICATION_NAME = "ENERCARE.PRIVACY.SIN_BACKSTOP"
FRIENDLY_NAME = "Enercare Canadian SIN (Backstop)"
DESCRIPTION = (
    "Enercare custom backstop classifier for Canadian Social Insurance Numbers. "
    "Matches on column-name and regex patterns without requiring Luhn validation. "
    "Fires when the built-in MICROSOFT.CANADIAN.SIN classifier does not — for "
    "example on partial SIN columns (last 4 digits) or when synthetic seed values "
    "fail the Luhn checksum."
)


def get_token() -> str:
    """Acquire a Purview data-plane access token via the default credential chain."""
    cred = DefaultAzureCredential()
    return cred.get_token("https://purview.azure.net/.default").token


def create_classification(token: str) -> None:
    """Define the custom classification (the label, separate from the rule)."""
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {
        "classificationDefs": [
            {
                "name": CLASSIFICATION_NAME,
                "kind": "Custom",
                "description": DESCRIPTION,
            }
        ]
    }
    r = requests.put(
        f"{BASE_URL}/catalog/api/atlas/v2/types/typedefs",
        headers=headers,
        json=payload,
        timeout=60,
    )
    if r.status_code in (200, 201, 204, 409):
        print(f"Classification create: {r.status_code} {r.reason}")
    else:
        r.raise_for_status()


def create_classification_rule(token: str) -> None:
    """Define the rule (regex + column-name pattern + thresholds) that drives the label."""
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {
        "kind": "Custom",
        "name": CLASSIFICATION_NAME,
        "description": "Regex + column-name backstop for Canadian SIN, no Luhn check.",
        "ruleStatus": "Enabled",
        "version": 1,
        "classificationName": CLASSIFICATION_NAME,
        "minimumPercentageMatch": 50,
        "classificationAction": "Keep",
        "dataPatterns": [
            {
                "kind": "Regex",
                "pattern": r"\b[1-79]\d{2}[\s\-]?\d{3}[\s\-]?\d{3}\b",
            }
        ],
        "columnPatterns": [
            {
                "kind": "Regex",
                "pattern": r"^(sin|sin_full|sin_last_4|social_insurance_number|nas)$",
            }
        ],
    }
    api_version = "2022-02-01-preview"
    r = requests.put(
        f"{BASE_URL}/scan/classificationrules/{CLASSIFICATION_NAME}?api-version={api_version}",
        headers=headers,
        json=payload,
        timeout=60,
    )
    if r.status_code in (200, 201, 204):
        print(f"Classification rule create: {r.status_code} {r.reason}")
    else:
        print(f"Rule create returned {r.status_code}: {r.text}")
        r.raise_for_status()


def verify(token: str) -> None:
    """Read back the classification rule to confirm it landed."""
    headers = {"Authorization": f"Bearer {token}"}
    api_version = "2022-02-01-preview"
    r = requests.get(
        f"{BASE_URL}/scan/classificationrules/{CLASSIFICATION_NAME}?api-version={api_version}",
        headers=headers,
        timeout=60,
    )
    if r.status_code == 200:
        print(f"\nVerification — classification rule is present:")
        body = r.json()
        print(f"  name: {body.get('name')}")
        print(f"  status: {body.get('ruleStatus')}")
        print(f"  min match %: {body.get('minimumPercentageMatch')}")
    else:
        print(f"Verification GET returned {r.status_code}: {r.text}")


if __name__ == "__main__":
    token = get_token()
    print(f"Creating {CLASSIFICATION_NAME} in {PURVIEW_ACCOUNT}...")
    create_classification(token)
    create_classification_rule(token)
    verify(token)
    print(
        "\nNext step: in Purview portal, edit the scan rule set used by the "
        "Enercare scans and enable this classification in the active rule set. "
        "Then re-run the SQL and Fabric scans."
    )
