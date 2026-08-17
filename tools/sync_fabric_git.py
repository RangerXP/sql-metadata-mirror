#!/usr/bin/env python3
"""Sync a Fabric workspace from its connected Git branch (updateFromGit).

Local notebook edits only take effect in Fabric-run jobs after they are:
  1. committed + pushed to the git remote, AND
  2. synced into the Fabric workspace via this Git integration API.

Skipping step 2 causes Fabric to silently keep executing the OLD notebook
content even though the local file (and the remote git history) already has
the fix -- there is no error, the job just runs stale code. Always run this
after pushing notebook-content.py changes and before re-running the affected
notebook's job.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request

FABRIC_RESOURCE = "https://api.fabric.microsoft.com"
FABRIC_API = f"{FABRIC_RESOURCE}/v1"


def get_token() -> str:
    az_executable = shutil.which("az") or shutil.which("az.cmd")
    if not az_executable:
        raise RuntimeError("Azure CLI executable (az or az.cmd) was not found on PATH.")
    command = [az_executable, "account", "get-access-token", "--resource", FABRIC_RESOURCE, "--query", "accessToken", "-o", "tsv"]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    token = result.stdout.strip()
    if not token:
        raise RuntimeError("Azure CLI returned an empty Fabric access token.")
    return token


def request_json(token: str, method: str, url: str, body: dict | None = None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            content = response.read()
            payload = json.loads(content) if content else None
            return response.status, dict(response.headers), payload
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Fabric API {method} {url} failed: HTTP {error.code}: {detail}") from error


def poll_operation(token: str, location: str):
    while True:
        status, headers, payload = request_json(token, "GET", location)
        state = (payload or {}).get("status")
        print(f"sync operation status={state}")
        if state in {"Succeeded", "Failed"}:
            return state, payload
        time.sleep(5)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace-id", required=True)
    args = parser.parse_args()

    token = get_token()
    status_url = f"{FABRIC_API}/workspaces/{args.workspace_id}/git/status"
    _, _, status_payload = request_json(token, "GET", status_url)
    remote_hash = (status_payload or {}).get("remoteCommitHash")
    workspace_head = (status_payload or {}).get("workspaceHead")
    changes = (status_payload or {}).get("changes", [])
    print(f"remoteCommitHash={remote_hash}")
    print(f"workspaceHead={workspace_head}")
    print(f"pending changes: {len(changes)}")

    if remote_hash == workspace_head and not changes:
        print("Workspace already in sync with git remote; nothing to update.")
        return 0

    update_url = f"{FABRIC_API}/workspaces/{args.workspace_id}/git/updateFromGit"
    body = {
        "remoteCommitHash": remote_hash,
        "workspaceHead": workspace_head,
        "options": {"allowOverrideItems": True},
        "conflictResolution": {
            "conflictResolutionType": "Workspace",
            "conflictResolutionPolicy": "PreferRemote",
        },
    }
    status, headers, payload = request_json(token, "POST", update_url, body)
    print(f"updateFromGit submitted: HTTP {status}")

    if status == 200:
        print("Sync completed synchronously.")
        return 0

    location = headers.get("Location") or headers.get("location")
    if not location:
        print("No Location header returned for polling; assuming synchronous completion.")
        return 0

    state, result_payload = poll_operation(token, location)
    if state != "Succeeded":
        print(f"Sync failed: {json.dumps(result_payload)}")
        return 1

    print("Fabric workspace synced from git.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
