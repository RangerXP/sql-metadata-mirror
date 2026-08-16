#!/usr/bin/env python3
"""Read active Delta row counts from OneLake transaction logs."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import urllib.parse
import urllib.error
import urllib.request

STORAGE_RESOURCE = "https://storage.azure.com/"
ONELAKE = "https://onelake.dfs.fabric.microsoft.com"


def token() -> str:
    az = shutil.which("az") or shutil.which("az.cmd")
    if not az:
        raise RuntimeError("Azure CLI was not found.")
    result = subprocess.run(
        [az, "account", "get-access-token", "--resource", STORAGE_RESOURCE, "--query", "accessToken", "-o", "tsv"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def get_json(url: str, access_token: str) -> dict:
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {access_token}"})
    with urllib.request.urlopen(request, timeout=90) as response:
        return json.loads(response.read())


def get_text(url: str, access_token: str) -> str:
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {access_token}"})
    with urllib.request.urlopen(request, timeout=90) as response:
        return response.read().decode("utf-8")


def active_count(workspace: str, item: str, table: str, access_token: str) -> dict:
    relative_log = f"{item}/Tables/{table}/_delta_log"
    list_url = (
        f"{ONELAKE}/{workspace}/{relative_log}"
        "?resource=filesystem&recursive=true"
    )
    paths = get_json(list_url, access_token).get("paths", [])
    logs = sorted(path["name"] for path in paths if path["name"].endswith(".json"))
    active: dict[str, dict] = {}
    for path in logs:
        file_url = f"{ONELAKE}/{workspace}/{urllib.parse.quote(path, safe='/')}"
        for line in get_text(file_url, access_token).splitlines():
            action = json.loads(line)
            if "add" in action:
                active[action["add"]["path"]] = action["add"]
            elif "remove" in action:
                active.pop(action["remove"]["path"], None)
    rows = 0
    for add in active.values():
        stats = json.loads(add.get("stats") or "{}")
        rows += int(stats.get("numRecords") or 0)
    return {"table": table, "rows": rows, "activeFiles": len(active), "logVersions": len(logs)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace-id", required=True)
    parser.add_argument("--item-id", required=True)
    parser.add_argument("tables", nargs="+")
    args = parser.parse_args()
    access_token = token()
    results = []
    for table in args.tables:
        try:
            results.append(active_count(args.workspace_id, args.item_id, table, access_token))
        except urllib.error.HTTPError as error:
            results.append({"table": table, "error": f"HTTP {error.code}: {error.reason}"})
        except Exception as error:
            results.append({"table": table, "error": str(error)})
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
