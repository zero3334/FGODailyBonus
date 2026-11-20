"""Trigger one FGO workflow daily between 07:00 and 08:00 Shanghai time."""
import datetime as dt
import json
import os
from pathlib import Path
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

ZONE = ZoneInfo("Asia/Shanghai")
STATE = Path("/data/state.json")


def save(state):
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state), encoding="utf-8")
    os.replace(tmp, STATE)


def dispatch():
    token = os.environ["GH_TOKEN"].strip()
    repo = os.environ.get("GH_REPO", "zero3334/FGODailyBonus")
    if not token or token == "replace-with-new-token" or len(repo.split("/")) != 2:
        raise ValueError("Set a valid GH_TOKEN and GH_REPO")
    workflow = urllib.parse.quote(os.environ.get("GH_WORKFLOW", "run.yml"), safe="")
    url = f"https://api.github.com/repos/{repo}/actions/workflows/{workflow}/dispatches"
    payload = json.dumps({"ref": os.environ.get("GH_REF", "master")}).encode()
    req = urllib.request.Request(url, data=payload, method="POST", headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
        "User-Agent": "fgo-daily-dispatch",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    with urllib.request.urlopen(req, timeout=20) as response:
        if response.status != 204:
            raise RuntimeError(f"Unexpected status: {response.status}")


def run():
    if not os.environ.get("GH_TOKEN"):
        raise ValueError("GH_TOKEN is required")
    while True:
        now = dt.datetime.now(ZONE)
        day = now.date().isoformat()
        state = json.loads(STATE.read_text()) if STATE.exists() else {}
        if state.get("date") != day:
            minute = 420 + secrets.randbelow(60)
            state = {"date": day, "minute": minute, "attempted": False}
            save(state)
            print(f"{day}: scheduled at {minute // 60:02d}:{minute % 60:02d} Shanghai", flush=True)
        start = dt.datetime.combine(now.date(), dt.time.min, tzinfo=ZONE)
        target = start + dt.timedelta(minutes=state["minute"])
        end = start + dt.timedelta(hours=8)
        if not state["attempted"] and target <= now < end:
            # Persist before sending: on restart or uncertain network failure, never retry blindly.
            state["attempted"] = True
            save(state)
            try:
                dispatch()
                print(f"{day}: GitHub accepted dispatch (204)", flush=True)
            except urllib.error.HTTPError as exc:
                print(f"{day}: GitHub rejected dispatch (HTTP {exc.code})", flush=True)
            except Exception as exc:
                print(f"{day}: dispatch failed ({type(exc).__name__}: {exc})", flush=True)
        elif not state["attempted"] and now >= end:
            state["attempted"] = True
            save(state)
            print(f"{day}: missed window; skipping", flush=True)
        time.sleep(30)


if __name__ == "__main__":
    run()
