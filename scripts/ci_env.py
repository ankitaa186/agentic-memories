#!/usr/bin/env python3
"""Fetch GitHub environment variables and secrets for CI builds.

This script fetches all variables from a GitHub environment and exports them
to GITHUB_ENV for use in subsequent workflow steps. Secrets must still be
passed explicitly (GitHub security requirement), but variables are fetched
dynamically, eliminating duplication.

Usage in GitHub Actions:
    - name: Load environment variables
      env:
        GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        # Secrets must be explicit (GitHub security)
        GROK_API_KEY: ${{ secrets.GROK_API_KEY }}
        ...
      run: python scripts/ci_env.py --env prod
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def run_gh(args: list[str]) -> tuple[int, str, str]:
    """Run a gh CLI command and return (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            ["gh"] + args,
            capture_output=True,
            text=True,
        )
        return result.returncode, result.stdout, result.stderr
    except FileNotFoundError:
        print("Error: GitHub CLI (gh) not found", file=sys.stderr)
        sys.exit(1)


def get_repo() -> str:
    """Get the current repository in owner/repo format."""
    # In GitHub Actions, use GITHUB_REPOSITORY env var
    repo = os.environ.get("GITHUB_REPOSITORY")
    if repo:
        return repo

    # Fallback to gh CLI
    code, stdout, _ = run_gh(
        ["repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"]
    )
    if code != 0:
        print("Error: Could not determine repository", file=sys.stderr)
        sys.exit(1)
    return stdout.strip()


def fetch_environment_variables(repo: str, env_name: str) -> dict[str, str]:
    """Fetch all variables from a GitHub environment."""
    code, stdout, stderr = run_gh(
        [
            "api",
            f"repos/{repo}/environments/{env_name}/variables?per_page=100",
            "--jq",
            ".variables // []",
        ]
    )

    if code != 0:
        if "Not Found" in stderr:
            print(f"Warning: Environment '{env_name}' not found", file=sys.stderr)
            return {}
        print(f"Error fetching variables: {stderr}", file=sys.stderr)
        return {}

    try:
        variables = json.loads(stdout) if stdout.strip() else []
        return {v["name"]: v["value"] for v in variables}
    except json.JSONDecodeError:
        return {}


def export_to_github_env(variables: dict[str, str]) -> None:
    """Export variables to GITHUB_ENV for subsequent steps."""
    github_env_path = os.environ.get("GITHUB_ENV")
    if not github_env_path:
        print(
            "Warning: GITHUB_ENV not set (not running in GitHub Actions?)",
            file=sys.stderr,
        )
        # Print for debugging when run locally
        for key, value in variables.items():
            print(f"  {key}={value[:20]}..." if len(value) > 20 else f"  {key}={value}")
        return

    with open(github_env_path, "a", encoding="utf-8") as f:
        for key, value in variables.items():
            # Handle multiline values with heredoc syntax
            if "\n" in value:
                import uuid

                delimiter = f"EOF_{uuid.uuid4().hex[:8]}"
                f.write(f"{key}<<{delimiter}\n{value}\n{delimiter}\n")
            else:
                f.write(f"{key}={value}\n")

    print(f"Exported {len(variables)} variables to GITHUB_ENV")


def create_env_file(variables: dict[str, str], output_path: Path) -> None:
    """Create .env file from variables."""
    # Also include any secrets passed via environment
    env_example = Path("env.example")
    if env_example.exists():
        # Read expected keys from env.example
        expected_keys = set()
        for line in env_example.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key = line.split("=", 1)[0].strip()
                expected_keys.add(key)

        # Collect all values (variables from GitHub + secrets from env)
        all_values = {}
        for key in expected_keys:
            # First check if it's in fetched variables
            if key in variables:
                all_values[key] = variables[key]
            # Then check current environment (for secrets passed explicitly)
            elif key in os.environ and os.environ[key]:
                all_values[key] = os.environ[key]

        # Write to output file
        lines = [f"{k}={v}" for k, v in sorted(all_values.items())]
        output_path.write_text("\n".join(lines) + "\n")
        print(f"Created {output_path} with {len(all_values)} values")
    else:
        print(f"Warning: {env_example} not found", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch GitHub environment variables for CI"
    )
    parser.add_argument(
        "--env", required=True, help="GitHub environment name (dev, prod, staging)"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(".env.ci"),
        help="Output .env file path (default: .env.ci)",
    )
    parser.add_argument(
        "--export",
        action="store_true",
        help="Also export to GITHUB_ENV for subsequent steps",
    )
    args = parser.parse_args()

    repo = get_repo()
    print(f"Fetching variables from {repo} environment '{args.env}'...")

    variables = fetch_environment_variables(repo, args.env)
    print(f"Found {len(variables)} variables")

    # Create .env file
    create_env_file(variables, args.output)

    # Optionally export to GITHUB_ENV
    if args.export:
        export_to_github_env(variables)


if __name__ == "__main__":
    main()
