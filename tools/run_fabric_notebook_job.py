#!/usr/bin/env python3
"""Submit and observe one Fabric notebook job without claiming Spark-session control.

The Fabric Job Instance API only ever reports a generic terminal failure message
(e.g. "System cancelled the Spark session due to statement execution failures") --
it does not expose which cell failed or why. This tool cannot manufacture cell-level
detail that Fabric doesn't publish over REST, but it does everything that IS
possible with the public API:

  - correlates the job to its Livy session (sparkApplicationId, cancellationReason)
    so the operator has the exact IDs needed to open Monitor Hub and see the real
    per-cell traceback in the portal;
  - supports resuming/attaching to an already-submitted job (--job-id) so a local
    terminal/session interruption never loses track of an in-flight Fabric run;
  - uses generous, notebook-appropriate default timeouts (the merged 10-notebook
    structure runs longer than the old per-stage notebooks did);
  - tolerates transient polling failures instead of aborting monitoring on one
    network blip;
  - appends a durable JSON-line record per invocation (--json-log) so results
    survive even if the interactive session itself has trouble.
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
TERMINAL_STATES = {"Completed", "Failed", "Cancelled", "Deduped"}
ACTIVE_STATES = {"NotStarted", "InProgress"}
MAX_POLL_ERRORS = 5


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


def find_livy_session(token: str, workspace_id: str, item_id: str, job_id: str) -> dict | None:
    """Best-effort correlation of a job instance to its Livy session.

    This is the richest failure context the public Fabric API exposes (Spark
    application ID + cancellation reason). It never includes per-cell detail --
    that only exists in the Monitor Hub UI -- but it gives the operator the exact
    IDs needed to find that run in the portal quickly.
    """
    url = f"{FABRIC_API}/workspaces/{workspace_id}/notebooks/{item_id}/livySessions"
    try:
        _, _, payload = request_json(token, "GET", url)
    except RuntimeError:
        return None
    for session in (payload or {}).get("value", []):
        if session.get("jobInstanceId") == job_id:
            return session
    return None


def append_json_log(path: str, record: dict) -> None:
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")


def poll_job(token: str, args: argparse.Namespace, item_id: str, job_id: str, submitted: float) -> int:
    job_url = f"{FABRIC_API}/workspaces/{args.workspace_id}/items/{item_id}/jobs/instances/{job_id}"
    execution_started: float | None = None
    last_status = None
    consecutive_poll_errors = 0

    while True:
        try:
            _, _, job = request_json(token, "GET", job_url)
            consecutive_poll_errors = 0
        except RuntimeError as poll_error:
            consecutive_poll_errors += 1
            print(f"{args.notebook} job={job_id} poll error ({consecutive_poll_errors}/{MAX_POLL_ERRORS}): {poll_error}", flush=True)
            if consecutive_poll_errors >= MAX_POLL_ERRORS:
                raise RuntimeError(
                    f"Polling failed {MAX_POLL_ERRORS} times in a row; job {job_id} remains "
                    f"Fabric-managed. Resume with: --job-id {job_id}"
                ) from poll_error
            time.sleep(args.poll_seconds)
            continue

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
            if status != "Completed":
                livy = find_livy_session(token, args.workspace_id, item_id, job_id)
                if livy:
                    evidence["livySession"] = {
                        "sparkApplicationId": livy.get("sparkApplicationId"),
                        "livyId": livy.get("livyId"),
                        "cancellationReason": livy.get("cancellationReason"),
                    }
                evidence["monitorHubHint"] = (
                    "Fabric's REST API does not expose per-cell error detail. Open Monitor Hub "
                    f"in the Fabric portal for workspace {args.workspace_id}, item {item_id}, "
                    f"job {job_id} to see which cell failed and its full traceback."
                )
            print(json.dumps(evidence, indent=2))
            if args.json_log:
                append_json_log(args.json_log, evidence)
            return 0 if status == "Completed" else 1

        now = time.monotonic()
        if status == "InProgress" and execution_started is None:
            execution_started = now

        if execution_started is None and now - submitted > args.startup_timeout * 60:
            raise RuntimeError(
                f"Startup exceeded {args.startup_timeout} minutes; job {job_id} remains "
                f"Fabric-managed. Resume with: --job-id {job_id}"
            )

        if execution_started is not None and now - execution_started > args.execution_timeout * 60:
            raise RuntimeError(
                f"Execution exceeded {args.execution_timeout} minutes; job {job_id} remains "
                f"Fabric-managed. Resume with: --job-id {job_id}"
            )

        # Poll at the requested cadence for the first --fast-poll-seconds (Spark cold start
        # is typically ~3 minutes and status rarely changes faster than that); slow down to
        # --post-startup-poll-seconds afterward to reduce API call volume while waiting out
        # the remaining execution time.
        elapsed = now - submitted
        sleep_for = args.poll_seconds if elapsed < args.fast_poll_seconds else args.post_startup_poll_seconds
        time.sleep(sleep_for)


def run(args: argparse.Namespace) -> int:
    token = get_token()
    item_id = resolve_notebook(token, args.workspace_id, args.notebook)

    if args.job_id:
        print(f"{args.notebook} resuming monitoring of job={args.job_id}", flush=True)
        return poll_job(token, args, item_id, args.job_id, time.monotonic())

    active = [job for job in list_jobs(token, args.workspace_id, item_id) if job.get("status") in ACTIVE_STATES]
    if active:
        active_ids = ", ".join(str(job.get("id")) for job in active)
        raise RuntimeError(
            f"Refusing duplicate submission; active job(s): {active_ids}. "
            f"Resume with: --job-id {active[0].get('id')}"
        )

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

    print(f"{args.notebook} submitted job={job_id}", flush=True)
    return poll_job(token, args, item_id, job_id, time.monotonic())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace-id", required=True)
    parser.add_argument("--notebook", required=True)
    parser.add_argument("--startup-timeout", type=float, default=10.0, help="Minutes to wait for the Spark session to start (default 10).")
    parser.add_argument("--execution-timeout", type=float, default=30.0, help="Minutes to wait after execution starts (default 30 -- these are merged, multi-cell notebooks).")
    parser.add_argument("--poll-seconds", type=float, default=15.0, help="Poll interval for the first --fast-poll-seconds of the run (default 15).")
    parser.add_argument("--fast-poll-seconds", type=float, default=150.0, help="How long (seconds) to use --poll-seconds before slowing down (default 150 = 2.5 min, roughly Spark cold-start time).")
    parser.add_argument("--post-startup-poll-seconds", type=float, default=30.0, help="Poll interval after --fast-poll-seconds has elapsed (default 30).")
    parser.add_argument("--job-id", default=None, help="Attach to and monitor an already-submitted job instead of submitting a new one.")
    parser.add_argument("--json-log", default=None, help="Append a JSON-line evidence record to this file on terminal status.")
    return parser.parse_args()


if __name__ == "__main__":
    try:
        raise SystemExit(run(parse_args()))
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(2)
