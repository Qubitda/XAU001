#!/usr/bin/env python3
"""Minimal API smoke checks against a running Tara Gold backend."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("SMOKE_API_BASE", os.environ.get("VITE_API_BASE_URL", "http://localhost:8000")).rstrip(
    "/"
)


def get(path: str) -> tuple[int, dict | list | str]:
    req = urllib.request.Request(f"{BASE}{path}", method="GET")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("utf-8")
            try:
                return resp.status, json.loads(raw)
            except json.JSONDecodeError:
                return resp.status, raw
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, raw
    except urllib.error.URLError as exc:
        raise SystemExit(f"FAIL connect {BASE}{path}: {exc}") from exc


def main() -> None:
    checks: list[tuple[str, int, callable]] = [
        ("/health", 200, lambda b: isinstance(b, dict) and b.get("status") in ("ok", "degraded")),
        ("/api/v1/health", 200, lambda b: isinstance(b, dict) and "database" in b),
        ("/api/v1/schema/", 200, lambda b: isinstance(b, dict) and "openapi" in b),
        ("/api/v1/market/rates", 200, lambda b: isinstance(b, dict) and "data" in b),
        ("/api/v1/storefront/products", 200, lambda b: isinstance(b, dict) and "data" in b),
        ("/api/v1/session", 200, lambda b: isinstance(b, dict)),
    ]

    failed = 0
    for path, want_status, pred in checks:
        status, body = get(path)
        ok = status == want_status and pred(body)
        mark = "OK" if ok else "FAIL"
        print(f"{mark}  {status}  {path}")
        if not ok:
            failed += 1
            if isinstance(body, (dict, list)):
                print("     ", json.dumps(body)[:240])
            else:
                print("     ", str(body)[:240])

    if failed:
        raise SystemExit(f"{failed} smoke check(s) failed against {BASE}")
    print(f"All smoke checks passed against {BASE}")


if __name__ == "__main__":
    main()
