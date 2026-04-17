"""
Smoke and rate-limit tests for Section 04 advanced security stack.

Run after starting the app:
    python app.py
    python test_advanced.py
    python test_advanced.py --test rate-limit
"""
from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request


BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")


def request_json(path: str, method: str = "GET", data: dict | None = None, headers=None):
    request = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=json.dumps(data).encode() if data is not None else None,
        headers=headers or {},
        method=method,
    )
    try:
        with urllib.request.urlopen(request) as response:
            payload = response.read()
            return response.status, json.loads(payload) if payload else {}
    except urllib.error.HTTPError as exc:
        payload = exc.read()
        return exc.code, json.loads(payload) if payload else {}


def get_token(username: str = "student", password: str = "demo123") -> str:
    status, body = request_json(
        "/auth/token",
        method="POST",
        data={"username": username, "password": password},
        headers={"Content-Type": "application/json"},
    )
    if status != 200:
        raise RuntimeError(f"Token request failed: {status} {body}")
    return body["access_token"]


def run_smoke():
    token = get_token()
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }

    status, ask_body = request_json(
        "/ask",
        method="POST",
        data={"question": "what is docker?"},
        headers=headers,
    )
    print(f"/ask       -> {status}: {ask_body}")

    status, usage_body = request_json("/me/usage", headers={"Authorization": f"Bearer {token}"})
    print(f"/me/usage  -> {status}: {usage_body}")


def run_rate_limit():
    token = get_token()
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }

    for index in range(1, 15):
        status, body = request_json(
            "/ask",
            method="POST",
            data={"question": f"rate limit test #{index}"},
            headers=headers,
        )
        print(f"Request {index:02d} -> {status}")
        if status == 429:
            print(body)
            break


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", choices=["smoke", "rate-limit", "all"], default="all")
    args = parser.parse_args()

    if args.test in {"smoke", "all"}:
        print("== Advanced security smoke test ==")
        run_smoke()

    if args.test in {"rate-limit", "all"}:
        print("\n== Advanced security rate-limit test ==")
        run_rate_limit()


if __name__ == "__main__":
    main()
