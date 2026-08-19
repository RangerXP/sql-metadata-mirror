#!/usr/bin/env python3
"""Refresh the shared Purview token cache that notebooks read before falling
back to in-runtime token acquisition (TokenLibrary/AzureCliCredential).

Why this exists: Fabric's managed Spark runtime has no 'az' CLI on PATH, so
AzureCliCredential can never succeed unattended, and mssparkutils.credentials
.getToken() can intermittently (or, in this workspace, persistently) fail
with Spark_System_TM_INTERNAL_ERROR for the Purview resource specifically --
confirmed live 2026-08-19 across both unattended and interactive runs, and
across a Fabric service restart, so it's a platform-side issue, not fixable
from notebook code.

This script runs OUTSIDE Fabric (locally, with 'az login' already done) and
writes a fresh Purview-scoped token directly into the shared cache file each
notebook already reads first (Files/purview_publish/.purview_token_cache.json
in lh_metadata), using the OneLake DFS REST API
(PUT ?resource=file -> PATCH ?action=append -> PATCH ?action=flush).
Matches the exact JSON shape _read_shared_purview_token_cache() expects:
{"access_token": ..., "expires_on": <unix epoch float>}.

This exact fix was applied once before (see
docs/runbooks/notebook-validation/05_publish_governance_domains.md) as a
one-off terminal action; this script makes it repeatable.

Usage:
    python tools/refresh_purview_token_cache.py --workspace-id <id> --lakehouse-id <id>
"""

from __future__ import annotations

import argparse
import base64
import json
import shutil
import subprocess
import time
import urllib.error
import urllib.request

STORAGE_RESOURCE = "https://storage.azure.com/"
PURVIEW_RESOURCE = "https://purview.azure.net"
ONELAKE = "https://onelake.dfs.fabric.microsoft.com"
CACHE_RELATIVE_PATH = "Files/purview_publish/.purview_token_cache.json"


def _az_path() -> str:
    az = shutil.which("az") or shutil.which("az.cmd")
    if not az:
        raise RuntimeError("Azure CLI was not found on PATH. Run this script locally, not inside Fabric.")
    return az


def _get_access_token(resource: str) -> str:
    result = subprocess.run(
        [_az_path(), "account", "get-access-token", "--resource", resource, "--query", "accessToken", "-o", "tsv"],
        check=True,
        capture_output=True,
        text=True,
    )
    token = result.stdout.strip()
    if not token:
        raise RuntimeError(f"Azure CLI returned an empty access token for resource={resource}.")
    return token


def _decode_jwt_expiry(token: str) -> float:
    payload = token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    claims = json.loads(base64.urlsafe_b64decode(payload.encode("utf-8")).decode("utf-8"))
    exp = float(claims.get("exp", 0))
    if exp <= 0:
        raise RuntimeError("Could not determine token expiry from JWT 'exp' claim.")
    return exp


def _dfs_request(method: str, url: str, storage_token: str, body: bytes = b"") -> None:
    request = urllib.request.Request(
        url,
        data=body if method in ("PUT", "PATCH") else None,
        method=method,
        headers={"Authorization": f"Bearer {storage_token}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {url} -> HTTP {exc.code}: {detail}") from exc


def write_shared_cache(workspace_id: str, lakehouse_id: str, purview_token: str, expires_on: float) -> None:
    storage_token = _get_access_token(STORAGE_RESOURCE)
    payload = json.dumps({"access_token": purview_token, "expires_on": expires_on}).encode("utf-8")
    base_url = f"{ONELAKE}/{workspace_id}/{lakehouse_id}/{CACHE_RELATIVE_PATH}"

    _dfs_request("PUT", f"{base_url}?resource=file", storage_token)
    _dfs_request("PATCH", f"{base_url}?action=append&position=0", storage_token, body=payload)
    _dfs_request("PATCH", f"{base_url}?action=flush&position={len(payload)}", storage_token)


def verify_shared_cache(workspace_id: str, lakehouse_id: str) -> dict:
    storage_token = _get_access_token(STORAGE_RESOURCE)
    base_url = f"{ONELAKE}/{workspace_id}/{lakehouse_id}/{CACHE_RELATIVE_PATH}"
    request = urllib.request.Request(base_url, headers={"Authorization": f"Bearer {storage_token}"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--workspace-id", required=True)
    parser.add_argument("--lakehouse-id", required=True, help="lh_metadata's item GUID, e.g. 824f4a52-baa0-4c3f-88dc-203c1d85c89a")
    args = parser.parse_args()

    print("Acquiring Purview-scoped token via az CLI...")
    purview_token = _get_access_token(PURVIEW_RESOURCE)
    expires_on = _decode_jwt_expiry(purview_token)
    minutes_left = round((expires_on - time.time()) / 60, 1)
    print(f"Token acquired, expires in {minutes_left} minutes.")

    print(f"Writing shared token cache to {CACHE_RELATIVE_PATH} in lakehouse {args.lakehouse_id}...")
    write_shared_cache(args.workspace_id, args.lakehouse_id, purview_token, expires_on)
    print("Shared token cache written.")

    cached = verify_shared_cache(args.workspace_id, args.lakehouse_id)
    cached_minutes_left = round((float(cached.get("expires_on", 0)) - time.time()) / 60, 1)
    print(f"Verified via read-back: cached token expires in {cached_minutes_left} minutes.")
    print("Notebooks reading the shared cache (before ever reaching TokenLibrary/AzureCliCredential) will now use this token.")


if __name__ == "__main__":
    main()
