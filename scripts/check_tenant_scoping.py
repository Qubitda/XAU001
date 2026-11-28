"""Static guard: detect ad-hoc .filter(organization=...) or .filter(branch=...) in files using TenantContext."""
from __future__ import annotations

import re
import sys
from pathlib import Path

BACKEND_APPS = Path(__file__).resolve().parents[1] / "apps" / "backend" / "apps"
ALLOWLIST = {
    "organizations/selectors.py",
    "organizations/api.py",  # OPS / org management views
}

PATTERNS = (
    re.compile(r"\.filter\([^)]*\borganization\s*=\s*ctx\.organization"),
    re.compile(r"\.filter\([^)]*\bbranch\s*=\s*ctx\.branch"),
)


def main() -> int:
    violations: list[str] = []
    for py_file in sorted(BACKEND_APPS.rglob("*.py")):
        rel = py_file.relative_to(BACKEND_APPS).as_posix()
        if "/tests/" in rel or "/migrations/" in rel or rel in ALLOWLIST:
            continue
        text = py_file.read_text(encoding="utf-8")
        if "ctx.organization" not in text and "ctx.is_ops" not in text:
            continue
        for idx, line in enumerate(text.splitlines(), start=1):
            for pat in PATTERNS:
                if pat.search(line):
                    violations.append(f"{rel}:{idx}: {line.strip()}")
    if violations:
        print("Ad-hoc tenant scoping detected (use scope_queryset_to_organization / scope_queryset_to_branch):")
        for v in violations:
            print(" ", v)
        return 1
    print("OK: No ad-hoc ctx.organization/ctx.branch queryset filters found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
