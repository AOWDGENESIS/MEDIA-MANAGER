"""Bounded localhost health check for the installed launcher (stdlib only).

The previous batch file launched up to 61 separate PowerShell processes.
Use the bundled Python interpreter once per startup phase instead; do not
open a browser, touch media, or depend on system Python or Internet.
"""
from __future__ import annotations

import json
import sys
import time
from urllib.request import ProxyHandler, Request, build_opener


HEALTH_URL = "http://127.0.0.1:8420/health"


def wait_for_core(attempts: int) -> bool:
    if attempts < 1 or attempts > 60:
        raise ValueError("health attempts must be between 1 and 60")
    opener = build_opener(ProxyHandler({}))
    for number in range(attempts):
        try:
            request = Request(HEALTH_URL, headers={"Accept": "application/json"})
            with opener.open(request, timeout=1) as response:
                if response.status == 200:
                    body = json.load(response)
                    if (body.get("status") == "ok"
                            and body.get("app") == "GENESIS Media Manager"):
                        return True
        except (OSError, ValueError, TimeoutError):
            pass
        if number + 1 < attempts:
            time.sleep(1)
    return False


if __name__ == "__main__":
    try:
        count = int(sys.argv[1]) if len(sys.argv) == 2 else 0
        sys.exit(0 if wait_for_core(count) else 1)
    except (ValueError, IndexError):
        sys.exit(2)
