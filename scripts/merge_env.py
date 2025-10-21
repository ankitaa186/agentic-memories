#!/usr/bin/env python3
"""Merge environment variables from GitHub environment and optional local .env file.

The script reads variable names from ``env.example`` (or a provided template) and
collects values from the current process environment first. If a local ``.env``
file exists it is loaded afterwards so that it can override any values sourced
from GitHub-hosted environment variables.

The resulting merged environment is written to the chosen output file. When the
``GITHUB_ENV`` environment variable is available (inside GitHub Actions) the
script also appends the merged key/value pairs to it so that subsequent steps
receive the same values automatically.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


def parse_env_file(path: Path) -> Dict[str, str]:
    """Parse a simple ``KEY=VALUE`` env file into a dictionary."""
    values: Dict[str, str] = {}
    if not path.exists():
        return values

    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def ensure_output_directory(path: Path) -> None:
    if not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)


def build_order(template: Dict[str, str], extra: Iterable[str]) -> List[str]:
    ordered_keys = list(template.keys())
    for key in extra:
        if key not in ordered_keys:
            ordered_keys.append(key)
    return ordered_keys


def emit_env_file(path: Path, data: Dict[str, str], order: Iterable[str]) -> None:
    ensure_output_directory(path)
    lines: List[str] = []
    for key in order:
        value = data.get(key)
        if value is None:
            continue
        # Escape newlines to keep the file single-line per entry.
        safe_value = value.replace("\n", "\\n")
        lines.append(f"{key}={safe_value}")
    path.write_text("\n".join(lines) + ("\n" if lines else ""))


def append_to_github_env(data: Dict[str, str], order: Iterable[str]) -> None:
    github_env_path = os.environ.get("GITHUB_ENV")
    if not github_env_path:
        return

    with open(github_env_path, "a", encoding="utf-8") as handle:
        for key in order:
            value = data.get(key)
            if value is None:
                continue
            safe_value = value.replace("\n", "\\n")
            handle.write(f"{key}={safe_value}\n")


def merge_environment(
    template_vars: Dict[str, str],
    github_env: Dict[str, str],
    local_env: Dict[str, str],
) -> Tuple[Dict[str, str], List[str]]:
    merged: Dict[str, str] = {}

    # Start with values provided by GitHub (already available in the process environment).
    for key in template_vars.keys():
        if key in github_env and github_env[key] != "":
            merged[key] = github_env[key]

    # Apply overrides from the local .env if it exists.
    for key, value in local_env.items():
        if value != "":
            merged[key] = value

    order = build_order(template_vars, local_env.keys())
    return merged, order


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge GitHub and local environment files")
    parser.add_argument(
        "--env-example",
        default="env.example",
        type=Path,
        help="Path to the template environment file used to determine keys",
    )
    parser.add_argument(
        "--local-env",
        default=Path(".env"),
        type=Path,
        help="Optional local .env file that can override GitHub-provided values",
    )
    parser.add_argument(
        "--output",
        default=Path(".env.ci"),
        type=Path,
        help="Destination file for the merged environment",
    )
    args = parser.parse_args()

    template_values = parse_env_file(args.env_example)
    github_env_values = {key: os.environ.get(key, "") for key in template_values.keys()}
    local_env_values = parse_env_file(args.local_env)

    merged_env, order = merge_environment(template_values, github_env_values, local_env_values)

    emit_env_file(args.output, merged_env, order)
    append_to_github_env(merged_env, order)

    # Log the keys that were exported without revealing the values.
    if merged_env:
        exported = ", ".join(key for key in order if key in merged_env)
        print(f"Merged environment variables: {exported}")
    else:
        print("No environment variables were merged.")


if __name__ == "__main__":
    main()
