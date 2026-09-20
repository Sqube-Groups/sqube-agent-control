#!/usr/bin/env python3
"""
Optional manual probe for NVIDIA Integrate chat completions (vision).

NOT part of sqube-guard policy or unit tests. Requires: pip install requests
(or: pip install -e ".[probes]")
"""

from __future__ import annotations

import argparse
import json
import os
import sys

DEFAULT_INVOKE_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
DEFAULT_MODEL = "moonshotai/kimi-k3"
DEFAULT_IMAGE_URL = (
    "https://assets.ngc.nvidia.com/products/api-catalog/phi-3-5-vision/example1b.jpg"
)
DEFAULT_PROMPT = "What is in this image?"


def _normalize_env_value(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1].strip()
    return value


def _api_key() -> str:
    raw = os.environ.get("NVIDIA_API_KEY") or os.environ.get("NVAPI_API_KEY")
    key = _normalize_env_value(raw) if raw else ""
    if not key:
        print(
            "Set NVIDIA_API_KEY or NVAPI_API_KEY (see .env.example).",
            file=sys.stderr,
        )
        sys.exit(1)
    return key


def _build_messages(prompt: str, image_url: str | None) -> list[dict]:
    if image_url:
        content: list[dict] | str = [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": image_url}},
        ]
    else:
        content = prompt
    return [{"role": "user", "content": content}]


def _run_stream(response) -> int:
    for line in response.iter_lines():
        if line:
            print(line.decode("utf-8"))
    return response.status_code


def _run_json(response) -> int:
    try:
        body = response.json()
    except json.JSONDecodeError:
        print(response.text, file=sys.stderr)
        return response.status_code
    print(json.dumps(body, indent=2))
    return response.status_code


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Probe NVIDIA Integrate chat completions (optional; not ExecutionGuard)."
    )
    parser.add_argument(
        "--stream",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use SSE streaming (default: on)",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument(
        "--image-url",
        default=DEFAULT_IMAGE_URL,
        help="Vision image URL; use --no-image-url for text-only",
    )
    parser.add_argument(
        "--no-image-url",
        action="store_true",
        help="Text-only request (omit image)",
    )
    parser.add_argument("--invoke-url", default=DEFAULT_INVOKE_URL)
    parser.add_argument("--max-tokens", type=int, default=16384)
    parser.add_argument("--temperature", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--reasoning-effort", default="max")
    args = parser.parse_args()

    try:
        import requests
    except ImportError:
        print(
            "Missing dependency: pip install requests  (or pip install -e '.[probes]')",
            file=sys.stderr,
        )
        sys.exit(1)

    stream = args.stream
    image_url = None if args.no_image_url else args.image_url

    headers = {
        "Authorization": f"Bearer {_api_key()}",
        "Accept": "text/event-stream" if stream else "application/json",
    }
    payload = {
        "messages": _build_messages(args.prompt, image_url),
        "model": args.model,
        "max_tokens": args.max_tokens,
        "seed": args.seed,
        "stream": stream,
        "temperature": args.temperature,
        "reasoning_effort": args.reasoning_effort,
    }

    response = requests.post(
        args.invoke_url,
        headers=headers,
        json=payload,
        stream=stream,
        timeout=300,
    )

    if stream:
        status = _run_stream(response)
    else:
        status = _run_json(response)

    if status >= 400:
        sys.exit(1 if status < 500 else 2)


if __name__ == "__main__":
    main()
