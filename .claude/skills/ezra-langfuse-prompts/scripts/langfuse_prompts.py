#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any


def main() -> int:
    parser = argparse.ArgumentParser(description="List and create Langfuse prompts.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List prompts in Langfuse.")
    list_parser.add_argument("--name", help="Filter by prompt name.")
    list_parser.add_argument("--label", help="Filter by label.")
    list_parser.add_argument("--tag", help="Filter by tag.")
    list_parser.add_argument(
        "--limit", type=int, default=20, help="Maximum prompts to list."
    )
    list_parser.add_argument(
        "--page", type=int, default=1, help="Results page to fetch."
    )

    get_parser = subparsers.add_parser("get", help="Fetch a prompt by name.")
    get_parser.add_argument("--name", required=True, help="Prompt name.")
    get_parser.add_argument("--version", type=int, help="Specific prompt version.")
    get_parser.add_argument("--label", help="Fetch by label instead of version.")
    get_parser.add_argument(
        "--type",
        choices=("text", "chat"),
        default="text",
        help="Prompt type when fetching by fallback path.",
    )

    upsert_parser = subparsers.add_parser(
        "upsert",
        help="Create a Langfuse prompt. If the name exists, Langfuse creates a new version.",
    )
    upsert_parser.add_argument("--name", required=True, help="Prompt name.")
    upsert_parser.add_argument(
        "--type",
        choices=("text", "chat"),
        required=True,
        help="Prompt type.",
    )
    upsert_parser.add_argument(
        "--prompt",
        help="Prompt content for text prompts, or JSON string for chat prompts.",
    )
    upsert_parser.add_argument(
        "--prompt-file",
        help="Path to a file containing prompt content. Use plain text for text prompts or JSON for chat prompts.",
    )
    upsert_parser.add_argument(
        "--label",
        action="append",
        dest="labels",
        default=[],
        help="Label to apply to the created version. May be repeated.",
    )
    upsert_parser.add_argument(
        "--tag",
        action="append",
        dest="tags",
        default=[],
        help="Tag to attach at the prompt level. May be repeated.",
    )
    upsert_parser.add_argument(
        "--config",
        help="Optional JSON object for Langfuse prompt config.",
    )
    upsert_parser.add_argument(
        "--config-file",
        help="Path to a JSON file containing prompt config.",
    )
    upsert_parser.add_argument(
        "--commit-message",
        help="Optional commit-style description of the prompt change.",
    )

    args = parser.parse_args()
    client = create_client()

    if args.command == "list":
        return list_prompts(client, args)
    if args.command == "get":
        return get_prompt(client, args)
    if args.command == "upsert":
        return upsert_prompt(client, args)

    parser.error(f"Unsupported command: {args.command}")
    return 2


def create_client() -> Any:
    required_env = ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_HOST")
    missing = [key for key in required_env if not os.environ.get(key)]
    if missing:
        joined = ", ".join(missing)
        raise SystemExit(f"Missing required Langfuse env vars: {joined}")

    from langfuse import Langfuse

    return Langfuse(
        public_key=os.environ["LANGFUSE_PUBLIC_KEY"],
        secret_key=os.environ["LANGFUSE_SECRET_KEY"],
        host=os.environ["LANGFUSE_HOST"],
    )


def list_prompts(client: Any, args: argparse.Namespace) -> int:
    response = client.api.prompts.list(
        name=args.name,
        label=args.label,
        tag=args.tag,
        page=args.page,
        limit=args.limit,
    )

    serialized = []
    for item in response.data:
        serialized.append(
            {
                "name": item.name,
                "version": item.version,
                "labels": list(item.labels or []),
                "tags": list(item.tags or []),
                "type": item.type,
                "updated_at": item.updated_at.isoformat() if item.updated_at else None,
            }
        )

    print(json.dumps({"items": serialized, "total_items": len(serialized)}, indent=2))
    return 0


def get_prompt(client: Any, args: argparse.Namespace) -> int:
    prompt = client.get_prompt(
        args.name,
        version=args.version,
        label=args.label,
        type=args.type,
    )
    print(json.dumps(serialize_prompt(prompt), indent=2))
    return 0


def upsert_prompt(client: Any, args: argparse.Namespace) -> int:
    prompt_payload = load_prompt_payload(args)
    config = load_json_payload(args.config, args.config_file)
    existed = prompt_exists(client, args.name)

    created = client.create_prompt(
        name=args.name,
        prompt=prompt_payload,
        labels=args.labels,
        tags=args.tags or None,
        type=args.type,
        config=config,
        commit_message=args.commit_message,
    )

    payload = serialize_prompt(created)
    payload["operation"] = "created_new_version" if existed else "created"
    print(json.dumps(payload, indent=2))
    return 0


def prompt_exists(client: Any, name: str) -> bool:
    from langfuse.api import NotFoundError

    try:
        client.get_prompt(name)
    except NotFoundError:
        return False
    return True


def load_prompt_payload(args: argparse.Namespace) -> Any:
    raw_payload = read_payload(args.prompt, args.prompt_file)
    if args.type == "text":
        return raw_payload

    try:
        parsed = json.loads(raw_payload)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Chat prompt payload must be valid JSON: {exc}") from exc

    if not isinstance(parsed, list):
        raise SystemExit("Chat prompt payload must be a JSON list of chat messages.")
    return parsed


def load_json_payload(raw_value: str | None, file_path: str | None) -> Any | None:
    if raw_value is None and file_path is None:
        return None

    raw_payload = read_payload(raw_value, file_path)
    try:
        return json.loads(raw_payload)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Config payload must be valid JSON: {exc}") from exc


def read_payload(inline_value: str | None, file_path: str | None) -> str:
    if inline_value and file_path:
        raise SystemExit("Use either the inline argument or --*-file, not both.")
    if file_path:
        return Path(file_path).read_text()
    if inline_value is None:
        raise SystemExit("Prompt content is required. Use --prompt or --prompt-file.")
    return inline_value


def serialize_prompt(prompt: Any) -> dict[str, Any]:
    content = getattr(prompt, "prompt", None)
    return {
        "name": getattr(prompt, "name", None),
        "version": getattr(prompt, "version", None),
        "labels": list(getattr(prompt, "labels", []) or []),
        "tags": list(getattr(prompt, "tags", []) or []),
        "type": getattr(prompt, "type", None),
        "config": getattr(prompt, "config", None),
        "prompt": content,
    }


if __name__ == "__main__":
    raise SystemExit(main())
