"""Populate the GitHub Actions environment from env.example values.

This script ensures that required secrets are present while filling in
sensible defaults for optional values defined in ``env.example``. It is
intended to run inside CI prior to executing tests or other commands.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, List, Tuple

EXAMPLE_PATH = Path("env.example")


def iter_env_pairs(lines: Iterable[str]) -> Iterable[Tuple[str, str]]:
    """Yield ``(key, value)`` pairs from lines of an env-style file."""
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        yield key, value


def determine_provider(pairs: List[Tuple[str, str]]) -> str:
    """Return the effective LLM provider based on env vars or defaults."""
    default_provider = "openai"
    for key, default in pairs:
        if key == "LLM_PROVIDER":
            default_provider = default or default_provider
            break
    provider = os.getenv("LLM_PROVIDER") or default_provider
    return provider.strip().lower()


def main() -> None:
    if not EXAMPLE_PATH.exists():
        raise SystemExit("env.example is missing; unable to synchronize environment values.")

    github_env = os.environ.get("GITHUB_ENV")
    if not github_env:
        raise SystemExit("GITHUB_ENV environment variable is not set; are you running inside GitHub Actions?")

    with EXAMPLE_PATH.open("r", encoding="utf-8") as example_file:
        pairs = list(iter_env_pairs(example_file))

    provider = determine_provider(pairs)

    missing_required: list[str] = []
    missing_optional: list[str] = []
    exported: list[str] = []

    with open(github_env, "a", encoding="utf-8") as target:
        for key, default in pairs:
            current = os.getenv(key)
            placeholder = "REPLACE" in default.upper()

            required = False
            if key == "OPENAI_API_KEY":
                required = provider == "openai"
            elif key == "XAI_API_KEY":
                required = provider in {"xai", "grok"}

            if not current:
                if placeholder:
                    if required:
                        missing_required.append(key)
                    else:
                        missing_optional.append(key)
                    continue
                current = default

            exported.append(key)
            target.write(f"{key}={current}\n")

    if missing_optional:
        for key in missing_optional:
            print(f"::warning::Optional secret '{key}' is not set; the default placeholder from env.example is skipped.")

    if missing_required:
        missing = ", ".join(missing_required)
        message = (
            "The following required secrets are missing: "
            f"{missing}.\n"
            "Define them in GitHub Secrets or repository variables so CI can run."
        )
        raise SystemExit(message)

    print(f"Exported {len(exported)} variables from env.example into the job environment.")


if __name__ == "__main__":
    main()
