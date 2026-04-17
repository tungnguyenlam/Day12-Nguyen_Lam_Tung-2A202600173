"""
Simple test script for Section 04 basic API key authentication.

Run after starting the app:
    AGENT_API_KEY=my-secret-key python app.py
    python test_auth.py
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request


BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
API_KEY = os.getenv("AGENT_API_KEY", "my-secret-key")


def post_json(path: str, data: dict, headers: dict[str, str] | None = None):
    request = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=json.dumps(data).encode(),
        headers={"Content-Type": "application/json", **(headers or {})},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"{}")


def main():
    print("== Section 04 Basic Auth Test ==")

    status, body = post_json("/ask", {"question": "hello without key"})
    print(f"No key       -> {status}: {body}")

    status, body = post_json(
        "/ask",
        {"question": "hello wrong key"},
        {"X-API-Key": "wrong-key"},
    )
    print(f"Wrong key    -> {status}: {body}")

    status, body = post_json(
        "/ask",
        {"question": "hello valid key"},
        {"X-API-Key": API_KEY},
    )
    print(f"Valid key    -> {status}: {body}")


if __name__ == "__main__":
    main()
