"""Cross-platform Celery launcher from monorepo root (worker/beat)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps" / "backend"


def _python_bin() -> str:
    if os.name == "nt":
        candidate = BACKEND / ".venv" / "Scripts" / "python.exe"
    else:
        candidate = BACKEND / ".venv" / "bin" / "python"
    if candidate.exists():
        return str(candidate)
    return sys.executable


def _celery_bin() -> list[str]:
    # Prefer `python -m celery` so Windows console encoding / entrypoint quirks don't swallow errors.
    return [_python_bin(), "-m", "celery"]


def main() -> int:
    if not BACKEND.is_dir():
        print(f"Backend not found: {BACKEND}", file=sys.stderr)
        return 1
    os.chdir(BACKEND)
    # Load root .env lightly for local Redis/Postgres
    env_path = ROOT / ".env"
    env = os.environ.copy()
    if env_path.exists():
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            env.setdefault(key, val)
    # Local docker-compose Redis host remap
    if env.get("REDIS_URL", "").startswith("redis://redis:"):
        env["REDIS_URL"] = env["REDIS_URL"].replace("redis://redis:", "redis://127.0.0.1:", 1)
    for key in ("CELERY_BROKER_URL", "CELERY_RESULT_BACKEND"):
        if env.get(key, "").startswith("redis://redis:"):
            env[key] = env[key].replace("redis://redis:", "redis://127.0.0.1:", 1)
    if env.get("POSTGRES_HOST") == "db":
        env["POSTGRES_HOST"] = "127.0.0.1"
    if env.get("DATABASE_URL", "").find("@db:") >= 0:
        env["DATABASE_URL"] = env["DATABASE_URL"].replace("@db:", "@127.0.0.1:")

    args = list(sys.argv[1:])
    # Windows: prefork pool is unsupported; prefer threads (more reliable than solo under some hosts).
    if os.name == "nt" and args and args[0] == "worker" and "--pool" not in args and "-P" not in args:
        args.extend(["--pool=threads"])
    # Celery 5 / kombu Redis transport needs Redis 5+ (Lua). Fail fast on ancient Windows Redis 3.x.
    try:
        import redis as redis_lib
        from urllib.parse import urlparse

        broker = env.get("CELERY_BROKER_URL") or env.get("REDIS_URL") or "redis://127.0.0.1:6379/0"
        parsed = urlparse(broker)
        if parsed.scheme.startswith("redis"):
            client = redis_lib.Redis(
                host=parsed.hostname or "127.0.0.1",
                port=parsed.port or 6379,
                db=int((parsed.path or "/0").lstrip("/") or "0"),
                password=parsed.password,
                socket_connect_timeout=2,
            )
            ver = client.info("server").get("redis_version", "0")
            major = int(str(ver).split(".", 1)[0])
            if major < 5:
                print(
                    f"ERROR: Celery requires Redis 5+ (found {ver} at {parsed.hostname}:{parsed.port or 6379}).\n"
                    "Fix options:\n"
                    "  1) Run Redis 7 via Docker Compose (`infrastructure/docker-compose.yml` redis service)\n"
                    "  2) Or run jobs without a worker: "
                    "apps/backend/.venv/Scripts/python manage.py run_scheduled_jobs",
                    flush=True,
                )
                return 2
    except Exception as exc:
        print(f"WARNING: could not verify Redis version ({exc})", flush=True)

    cmd = [*_celery_bin(), "-A", "config", *args]
    print("Running:", " ".join(cmd), flush=True)
    return subprocess.call(cmd, env=env)



if __name__ == "__main__":
    raise SystemExit(main())
