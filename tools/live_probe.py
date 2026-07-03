#!/usr/bin/env python3
"""Live characterization of the Ambient API through the `ambient` CLI.

Measures, with real calls: model readiness, per-model latency, audit quality
(does it find planted bugs?), structured-output reliability, stall/partial rate
(Ambient's serving is known-flaky), map-reduce at scale, and actual $ cost.

Run:  AMB=/path/to/bin/ambient python3 tools/live_probe.py
Bounded spend (~a few $). Writes a JSON report to stdout + a summary at the end.
"""
import json
import os
import subprocess
import sys
import time

AMB = os.environ.get("AMB", "ambient")
HOME = os.path.expanduser("~")
USAGE = os.path.join(HOME, ".config/ambient/usage.jsonl")
START = time.time()
R = {"models": {}, "audits": [], "notes": []}


def run(args, timeout=360, stdin=None):
    t = time.time()
    try:
        p = subprocess.run([AMB, *args], capture_output=True, text=True,
                           timeout=timeout, input=stdin)
        return {"secs": round(time.time() - t, 1), "code": p.returncode,
                "out": p.stdout, "err": p.stderr}
    except subprocess.TimeoutExpired:
        return {"secs": timeout, "code": -1, "out": "", "err": "CLIENT-TIMEOUT"}


def signals(err):
    e = err.lower()
    return {
        "stall": "stall" in e or "went silent" in e or "wedged" in e,
        "partial": "partial" in e or "salvag" in e or "truncated" in e,
        "cached": "served from cache" in e,
        "mapreduce": "chunks" in e,
        "no_workers": "no workers" in e or "429" in e,
    }


BUGS = "def divide(a, b):\n    return a / b\n\ndef fetch(d, k):\n    return d[k]\n"
BUG_KEYS = ("zero", "division", "keyerror", "key error", "unhandled")


def log(msg):
    print(f"[probe {int(time.time()-START)}s] {msg}", file=sys.stderr, flush=True)


# ---------------------------------------------------------------- 1. readiness
log("readiness sweep…")
mres = run(["models", "--json"], timeout=60)
try:
    catalog = json.loads(mres["out"])
except Exception:
    catalog = []
ready = [m for m in catalog if m.get("ready")]
R["catalog_size"] = len(catalog)
R["ready_ids"] = [m["id"] for m in ready]
log(f"{len(ready)}/{len(catalog)} models READY: {R['ready_ids']}")

# tiny latency probe per READY model
for m in ready:
    mid = m["id"]
    a = run(["ask", "-m", mid, "Reply with exactly: OK"], timeout=120)
    ok = a["out"].strip().endswith("OK")
    R["models"][mid] = {
        "ready": True, "name": m.get("name"),
        "ctx": m.get("context_length"), "price": m.get("pricing"),
        "features": m.get("features"),
        "tiny_ask_secs": a["secs"], "tiny_ask_ok": ok, "tiny_ask_code": a["code"],
    }
    log(f"  {mid}: tiny ask {a['secs']}s ok={ok}")

# write fixtures
with open("/tmp/_probe_bugs.py", "w") as fh:
    fh.write(BUGS)
big = "/tmp/_probe_big.py"
with open(big, "w") as fh:
    fh.write(BUGS)
    for i in range(3500):
        fh.write(f"def fn_{i}(x):\n    y = x + {i}\n    return y * 2\n\n")
BIG_CHARS = os.path.getsize(big)

# --------------------------------------------------- 2. per-model audit quality
for m in ready:
    mid = m["id"]
    runs = []
    for i in range(3):  # 3 repeats → reliability + variance
        a = run(["audit", "/tmp/_probe_bugs.py", "-m", mid, "--json", "--yes"],
                timeout=240)
        sig = signals(a["err"])
        findings, valid = [], False
        try:
            d = json.loads(a["out"])
            findings = d.get("findings", [])
            valid = True
        except Exception:
            pass
        caught = any(k in json.dumps(findings).lower() for k in BUG_KEYS)
        runs.append({"secs": a["secs"], "code": a["code"], "valid_json": valid,
                     "n_findings": len(findings), "caught_bug": caught, **sig})
        log(f"  {mid} audit#{i+1}: {a['secs']}s valid={valid} "
            f"findings={len(findings)} caught={caught} stall={sig['stall']}")
    R["models"][mid]["audit_runs"] = runs
    R["models"][mid]["audit_success_rate"] = round(
        sum(1 for r in runs if r["valid_json"] and r["caught_bug"]) / len(runs), 2)
    R["models"][mid]["valid_json_rate"] = round(
        sum(1 for r in runs if r["valid_json"]) / len(runs), 2)
    R["models"][mid]["stall_rate"] = round(
        sum(1 for r in runs if r["stall"]) / len(runs), 2)

# ------------------------------------------------------- 3. scale (map-reduce)
if ready:
    mid = ready[0]["id"]
    log(f"scale: {BIG_CHARS} chars on {mid} (map-reduce)…")
    a = run(["audit", big, "-m", mid, "--json", "--yes"], timeout=600)
    sig = signals(a["err"])
    valid = False
    try:
        json.loads(a["out"])
        valid = True
    except Exception:
        pass
    R["scale"] = {"model": mid, "chars": BIG_CHARS, "secs": a["secs"],
                  "code": a["code"], "valid_json": valid, "mapreduce": sig["mapreduce"],
                  "partial": sig["partial"]}
    log(f"  scale: {a['secs']}s valid={valid} mapreduce={sig['mapreduce']}")
    # cache re-run (should be faster / served from cache)
    a2 = run(["audit", big, "-m", mid, "--json", "--yes"], timeout=600)
    R["scale"]["rerun_secs"] = a2["secs"]
    R["scale"]["rerun_cached"] = signals(a2["err"])["cached"]
    log(f"  cache re-run: {a2['secs']}s cached={R['scale']['rerun_cached']}")

# ------------------------------------------------------------- 4. consensus
if len(ready) >= 2:
    ids = f"{ready[0]['id']},{ready[1]['id']}"
    log(f"consensus: {ids}…")
    a = run(["audit", "/tmp/_probe_bugs.py", "--consensus", ids, "--yes"], timeout=300)
    R["consensus"] = {"models": ids, "secs": a["secs"], "code": a["code"],
                      "ran": "consensus audit across" in a["out"].lower()}
    log(f"  consensus: {a['secs']}s ran={R['consensus']['ran']}")

# ------------------------------------------------------------------ 5. cost
price = {m["id"]: (m.get("pricing") or {}) for m in catalog}
spent = 0.0
calls = 0
try:
    with open(USAGE) as fh:
        for line in fh:
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if rec.get("ts", 0) >= int(START):
                calls += 1
                p = price.get(rec.get("model"), {})
                try:
                    spent += (rec.get("in", 0) * float(p.get("input", 0))
                              + rec.get("out", 0) * float(p.get("output", 0))) / 1e6
                except (TypeError, ValueError):
                    pass
except FileNotFoundError:
    pass
R["cost"] = {"calls_billed": calls, "est_usd": round(spent, 4),
             "wall_secs": round(time.time() - START)}

print(json.dumps(R, indent=2))
log(f"DONE. {calls} billed calls, est ${spent:.4f}, {int(time.time()-START)}s wall")
