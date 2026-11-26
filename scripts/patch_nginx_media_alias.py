#!/usr/bin/env python3
"""Point nginx /media/ at a www-readable path (Docker volume is not traversable by www-data)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

WWW_MEDIA = Path("/var/www/taragold/media")
DOCKER_MEDIA = Path("/var/lib/docker/volumes/infrastructure_media_data/_data")

FILES = [
    Path("/etc/nginx/sites-enabled/taragold-storefront"),
    Path("/etc/nginx/sites-enabled/taragold-ops"),
    Path("/etc/nginx/sites-enabled/taragold-b2b"),
    Path("/etc/nginx/sites-enabled/taragold-erp"),
]

NEW_BLOCK = """    location /media/ {
        alias /var/www/taragold/media/;
        access_log off;
        expires 7d;
        add_header Cache-Control "public";
    }"""


def sync_media() -> None:
    WWW_MEDIA.mkdir(parents=True, exist_ok=True)
    if DOCKER_MEDIA.exists():
        # Copy definitions (and any other folders) into www-readable tree.
        for child in DOCKER_MEDIA.iterdir():
            dest = WWW_MEDIA / child.name
            if child.is_dir():
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.copytree(child, dest)
            else:
                shutil.copy2(child, dest)
    subprocess.check_call(["chmod", "-R", "a+rX", str(WWW_MEDIA)])


def patch_nginx() -> None:
    import re

    pat = re.compile(r"    location /media/ \{.*?\n    \}", re.S)
    for path in FILES:
        if not path.exists():
            print("skip missing", path)
            continue
        text = path.read_text(encoding="utf-8")
        if not pat.search(text):
            print("no media block", path)
            continue
        path.write_text(pat.sub(NEW_BLOCK, text, count=1), encoding="utf-8")
        print("patched", path)
    subprocess.check_call(["nginx", "-t"])
    subprocess.check_call(["systemctl", "reload", "nginx"])
    print("nginx reloaded")


if __name__ == "__main__":
    sync_media()
    patch_nginx()
