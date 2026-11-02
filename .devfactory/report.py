"""Build report.json at the end of the `agent` job (Dev Factory). Standard library only, trusted step.

It runs NOTHING written by the agent: the tests already ran as the isolated user (run_tests.sh), and their JUnit
file, the reviewer's verdicts and the agent CLI's JSON result are read here as data (bounded by collect.sh). The
control plane validates every field again against its contract and the run.

    report.py --patch PATCH --out REPORT      # env: KEY, ROLE, BASE, RUNNER_TEMP
"""
import argparse
import hashlib
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

MODEL = "claude-sonnet-5-5"


def tests(junit: str) -> tuple[int, int]:
    try:
        root = ET.parse(junit).getroot()
    except (ET.ParseError, FileNotFoundError):
        return 0, 1           # no readable result: counted as a failure
    suites = [root] if root.tag == "testsuite" else list(root)
    total = sum(int(s.get("tests", 0)) for s in suites)
    failed = sum(int(s.get("failures", 0)) + int(s.get("errors", 0)) for s in suites)
    skipped = sum(int(s.get("skipped", 0)) for s in suites)
    return max(0, total - failed - skipped), failed


def verdicts(role: str, path: str) -> list[dict]:
    if role != "reviewer" or not os.path.exists(path):
        return []
    try:
        raw = json.load(open(path, encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return [{"criterion": "verdicts file", "status": "fail"}]
    return [{"criterion": str(v.get("criterion", ""))[:300], "status": v["status"]}
            for v in (raw[:50] if isinstance(raw, list) else [])
            if isinstance(v, dict) and v.get("status") in ("pass", "fail")]


def usage(path: str) -> tuple[dict | None, int]:
    """`claude -p --output-format json` result (one object, or a list ending with a `result` message)."""
    try:
        data = json.load(open(path, encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return None, 0
    messages = data if isinstance(data, list) else [data]
    result = next((m for m in reversed(messages) if isinstance(m, dict) and m.get("type") == "result"), None)
    if not result or not isinstance(result.get("usage"), dict):
        return None, 0
    u = result["usage"]
    keys = ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")
    return {"model": MODEL, **{k: int(u.get(k) or 0) for k in keys}}, int(result.get("num_turns") or 0)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--patch", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    env = os.environ
    tmp = env.get("RUNNER_TEMP", "/tmp")
    data = open(args.patch, "rb").read()
    files = sorted(set(re.findall(r"(?m)^diff --git a/\S+ b/(\S+)$", data.decode("utf-8", "replace"))))[:50]
    passed, failed = tests(os.path.join(tmp, "junit.xml"))
    used, turns = usage(os.path.join(tmp, "execution.json"))
    report = {"key": env["KEY"], "role": env["ROLE"], "base": env["BASE"],
              "patch_sha256": hashlib.sha256(data).hexdigest(), "patch_bytes": len(data), "files": files,
              "tests_passed": passed, "tests_failed": failed,
              "verdicts": verdicts(env["ROLE"], os.path.join(tmp, "verdicts.json")), "turns": turns, "usage": used}
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
