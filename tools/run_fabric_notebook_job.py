#!/usr/bin/env python3
"""Run one Fabric notebook job with separate startup and execution deadlines."""

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
TERMINAL_STATES = {"Completed", "Failed", "Cancelled", "Deduped"}
ACTIVE_STATES = {"NotStarted", "InProgress"}


def get_token() -> str:
    az_executable = shutil.which("az") or shutil.which("az.cmd")
    if not az_executable:
        raise RuntimeError("Azure CLI executable (az or az.cmd) was not found on PATH.")
    command = [
        az_executable,
        "account",
        "get-access-token",
        "--resource",
        FABRIC_RESOURCE,
        "--query",
        "accessToken",
        "-o",
        "tsv",
    ]
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
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            content = response.read()
            payload = json.loads(content) if content else None
            return response.status, dict(response.headers), payload
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Fabric API {method} {url} failed: HTTP {error.code}: {detail}") from error


def resolve_notebook(token: str, workspace_id: str, display_name: str) -> str:
    url = f"{FABRIC_API}/workspaces/{workspace_id}/items"
    _, _, payload = request_json(token, "GET", url)
    matches = [
        item
        for item in payload.get("value", [])
        if item.get("type") == "Notebook" and item.get("displayName") == display_name
    ]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one notebook named {display_name!r}; found {len(matches)}.")
    return matches[0]["id"]


def list_jobs(token: str, workspace_id: str, item_id: str) -> list[dict]:
    url = (
        f"{FABRIC_API}/workspaces/{workspace_id}/items/{item_id}/jobs/instances"
        "?jobType=RunNotebook"
    )
    _, _, payload = request_json(token, "GET", url)
    return payload.get("value", [])


def cancel_job(token: str, workspace_id: str, item_id: str, job_id: str) -> None:
    url = f"{FABRIC_API}/workspaces/{workspace_id}/items/{item_id}/jobs/instances/{job_id}/cancel"
    request_json(token, "POST", url, {})


def run(args: argparse.Namespace) -> int:
    token = get_token()
    item_id = resolve_notebook(token, args.workspace_id, args.notebook)
    active = [job for job in list_jobs(token, args.workspace_id, item_id) if job.get("status") in ACTIVE_STATES]
    if active:
        active_ids = ", ".join(str(job.get("id")) for job in active)
        raise RuntimeError(f"Refusing duplicate submission; active job(s): {active_ids}")

    submit_url = (
        f"{FABRIC_API}/workspaces/{args.workspace_id}/items/{item_id}/jobs/instances"
        "?jobType=RunNotebook"
    )
    _, headers, payload = request_json(token, "POST", submit_url, {})
    location = headers.get("Location") or headers.get("location")
    job_id = (payload or {}).get("id") or (payload or {}).get("jobInstanceId")
    if not job_id and location:
        job_id = location.rstrip("/").rsplit("/", 1)[-1]
    if not job_id:
        raise RuntimeError("Fabric accepted the run but returned no job identifier.")

    job_url = f"{FABRIC_API}/workspaces/{args.workspace_id}/items/{item_id}/jobs/instances/{job_id}"
    submitted = time.monotonic()
    execution_started: float | None = None
    last_status = None

    while True:
        _, _, job = request_json(token, "GET", job_url)
        status = str(job.get("status"))
        if status != last_status:
            print(f"{args.notebook} job={job_id} status={status}", flush=True)
            last_status = status

        if status in TERMINAL_STATES:
            evidence = {
                "notebook": args.notebook,
                "itemId": item_id,
                "jobId": job_id,
                "status": status,
                "startTimeUtc": job.get("startTimeUtc"),
                "endTimeUtc": job.get("endTimeUtc"),
                "failureReason": job.get("failureReason"),
            }
            print(json.dumps(evidence, indent=2))
            return 0 if status == "Completed" else 1

        now = time.monotonic()
        if status == "InProgress" and execution_started is None:
            execution_started = now

        if execution_started is None and now - submitted > args.startup_timeout * 60:
            cancel_job(token, args.workspace_id, item_id, job_id)
            raise RuntimeError(
                f"Startup exceeded {args.startup_timeout} minutes; cancellation requested for {job_id}."
            )

        if execution_started is not None and now - execution_started > args.execution_timeout * 60:
            cancel_job(token, args.workspace_id, item_id, job_id)
            raise RuntimeError(
                f"Execution exceeded {args.execution_timeout} minutes; cancellation requested for {job_id}."
            )

        time.sleep(args.poll_seconds)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace-id", required=True)
    parser.add_argument("--notebook", required=True)
    parser.add_argument("--startup-timeout", type=float, default=5.0)
    parser.add_argument("--execution-timeout", type=float, default=4.0)
    parser.add_argument("--poll-seconds", type=float, default=15.0)
    return parser.parse_args()


if __name__ == "__main__":
    try:
        raise SystemExit(run(parse_args()))
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(2)
