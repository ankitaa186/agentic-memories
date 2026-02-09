#!/usr/bin/env python3
"""Manage GitHub environment variables and secrets interactively.

This script provides an interactive menu to read, write, diff, and update
GitHub environment variables and secrets from your local .env file.

Usage:
    python scripts/github_env.py              # Interactive mode
    python scripts/github_env.py --env dev    # Start with specific environment
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ANSI colors
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"


def parse_env_file_with_sections(
    path: Path, include_placeholders: bool = False
) -> Tuple[Dict[str, str], Dict[str, str], Optional[Dict[str, str]]]:
    """Parse a .env file and separate into secrets and variables based on section headers.

    Expects .env to have sections like:
    # ============================================================================
    # SECRETS (GitHub Secrets - sensitive values)
    # ============================================================================
    KEY=value

    # ============================================================================
    # VARIABLES (GitHub Variables - non-sensitive configuration)
    # ============================================================================
    KEY=value

    Args:
        path: Path to the .env file
        include_placeholders: If True, returns a third dict with placeholder keys
            and their section type ('secret' or 'variable'). This is used to
            prevent accidental deletion of GitHub keys that have placeholder
            values in the local .env file.

    Returns:
        Tuple of (secrets_dict, variables_dict, placeholder_keys_dict or None)
        placeholder_keys_dict maps key names to their section type ('secret' or 'variable')
    """
    secrets: Dict[str, str] = {}
    variables: Dict[str, str] = {}
    placeholder_keys: Dict[str, str] = {}  # key -> section type

    if not path.exists():
        return secrets, variables, (placeholder_keys if include_placeholders else None)

    current_section = None  # None, 'secrets', or 'variables'

    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()

        # Check for section headers
        line_upper = line.upper()
        if "SECRETS" in line_upper and line.startswith("#"):
            current_section = "secrets"
            continue
        elif "VARIABLES" in line_upper and line.startswith("#"):
            current_section = "variables"
            continue

        # Skip empty lines and comments
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()

        # Track placeholder values separately (for deletion protection)
        if not value or value == "REPLACE_ME":
            if include_placeholders:
                section_type = "secret" if current_section == "secrets" else "variable"
                placeholder_keys[key] = section_type
            continue

        # Add to appropriate dict based on current section
        if current_section == "secrets":
            secrets[key] = value
        elif current_section == "variables":
            variables[key] = value
        else:
            # Default to variables if no section header found yet
            variables[key] = value

    return secrets, variables, (placeholder_keys if include_placeholders else None)


def clear_screen():
    """Clear the terminal screen."""
    print("\033[2J\033[H", end="")


def print_header(title: str, subtitle: str = ""):
    """Print a styled header."""
    print(f"\n{BOLD}{MAGENTA}{'═' * 60}{RESET}")
    print(f"{BOLD}{MAGENTA}  {title}{RESET}")
    if subtitle:
        print(f"{DIM}  {subtitle}{RESET}")
    print(f"{BOLD}{MAGENTA}{'═' * 60}{RESET}\n")


def print_menu(options: List[Tuple[str, str]], selected: int = -1):
    """Print a menu with options."""
    for i, (key, desc) in enumerate(options):
        if i == selected:
            print(f"  {CYAN}▶ [{key}]{RESET} {BOLD}{desc}{RESET}")
        else:
            print(f"    {YELLOW}[{key}]{RESET} {desc}")
    print()


def run_gh(args: List[str], capture: bool = True) -> Tuple[int, str, str]:
    """Run a gh CLI command and return (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            ["gh"] + args,
            capture_output=capture,
            text=True,
        )
        return result.returncode, result.stdout, result.stderr
    except FileNotFoundError:
        print(f"{RED}Error: GitHub CLI (gh) not found. Install it first:{RESET}")
        print("  brew install gh  # macOS")
        print("  https://cli.github.com/  # other platforms")
        sys.exit(1)


def get_repo() -> str:
    """Get the current repository in owner/repo format."""
    code, stdout, _ = run_gh(
        ["repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"]
    )
    if code != 0:
        print(f"{RED}Error: Not in a GitHub repository or not authenticated.{RESET}")
        print("Run: gh auth login")
        sys.exit(1)
    return stdout.strip()


def get_github_variables(repo: str, env_name: str) -> Dict[str, str]:
    """Get all variables from GitHub environment."""
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
            return {}
        return {}

    try:
        variables = json.loads(stdout) if stdout.strip() else []
        return {v["name"]: v["value"] for v in variables}
    except json.JSONDecodeError:
        return {}


def get_github_secrets(repo: str, env_name: str) -> List[str]:
    """Get list of secret names from GitHub environment (values are not accessible)."""
    code, stdout, stderr = run_gh(
        [
            "api",
            f"repos/{repo}/environments/{env_name}/secrets?per_page=100",
            "--jq",
            ".secrets // []",
        ]
    )

    if code != 0:
        if "Not Found" in stderr:
            return []
        return []

    try:
        secrets = json.loads(stdout) if stdout.strip() else []
        return [s["name"] for s in secrets]
    except json.JSONDecodeError:
        return []


def ensure_environment_exists(repo: str, env_name: str) -> bool:
    """Ensure the GitHub environment exists, create if not."""
    code, _, _ = run_gh(["api", f"repos/{repo}/environments/{env_name}"])

    if code != 0:
        print(f"{YELLOW}Environment '{env_name}' does not exist. Creating...{RESET}")
        code, _, stderr = run_gh(
            ["api", f"repos/{repo}/environments/{env_name}", "-X", "PUT"]
        )
        if code != 0:
            print(f"{RED}Failed to create environment: {stderr}{RESET}")
            return False
        print(f"{GREEN}Environment '{env_name}' created.{RESET}")

    return True


def set_secret(repo: str, env_name: str, name: str, value: str) -> bool:
    """Set a secret in GitHub environment."""
    code, _, stderr = run_gh(
        ["secret", "set", name, "--env", env_name, "--body", value]
    )
    return code == 0


def set_variable(
    repo: str, env_name: str, name: str, value: str, exists: bool = False
) -> Tuple[bool, str]:
    """Set a variable in GitHub environment. Returns (success, error_message)."""
    if exists:
        code, _, stderr = run_gh(
            [
                "api",
                f"repos/{repo}/environments/{env_name}/variables/{name}",
                "-X",
                "PATCH",
                "-f",
                f"value={value}",
            ]
        )
    else:
        code, _, stderr = run_gh(
            [
                "api",
                f"repos/{repo}/environments/{env_name}/variables",
                "-X",
                "POST",
                "-f",
                f"name={name}",
                "-f",
                f"value={value}",
            ]
        )
    return code == 0, stderr.strip() if stderr else ""


def delete_variable(repo: str, env_name: str, name: str) -> Tuple[bool, str]:
    """Delete a variable from GitHub environment. Returns (success, error_message)."""
    code, _, stderr = run_gh(
        [
            "api",
            f"repos/{repo}/environments/{env_name}/variables/{name}",
            "-X",
            "DELETE",
        ]
    )
    return code == 0, stderr.strip() if stderr else ""


def delete_secret(repo: str, env_name: str, name: str) -> Tuple[bool, str]:
    """Delete a secret from GitHub environment. Returns (success, error_message)."""
    code, _, stderr = run_gh(["secret", "delete", name, "--env", env_name])
    return code == 0, stderr.strip() if stderr else ""


def mask_value(value: str) -> str:
    """Mask a secret value for display."""
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}...{value[-4:]}"


def confirm(prompt: str, default: bool = False) -> bool:
    """Ask user for confirmation."""
    suffix = "[Y/n]" if default else "[y/N]"
    while True:
        response = input(f"{prompt} {suffix}: ").strip().lower()
        if response == "":
            return default
        if response in ("y", "yes"):
            return True
        if response in ("n", "no"):
            return False
        print(f"{YELLOW}Please enter 'y' or 'n'{RESET}")


def prompt_choice(prompt: str, choices: List[str], default: str = None) -> str:
    """Prompt user to select from choices."""
    print(f"{prompt}")
    for i, choice in enumerate(choices, 1):
        marker = f"{CYAN}*{RESET}" if choice == default else " "
        print(f"  {marker} {YELLOW}[{i}]{RESET} {choice}")

    while True:
        hint = f" (default: {default})" if default else ""
        response = input(f"\nEnter choice{hint}: ").strip()

        if response == "" and default:
            return default

        try:
            idx = int(response) - 1
            if 0 <= idx < len(choices):
                return choices[idx]
        except ValueError:
            if response in choices:
                return response

        print(f"{YELLOW}Invalid choice. Try again.{RESET}")


def prompt_environment(current: str = "dev") -> str:
    """Prompt user to select or enter environment name."""
    print(f"\n{BOLD}Select GitHub Environment:{RESET}")
    print(f"  {YELLOW}[1]{RESET} dev {DIM}(development){RESET}")
    print(f"  {YELLOW}[2]{RESET} prod {DIM}(production){RESET}")
    print(f"  {YELLOW}[3]{RESET} staging")
    print(f"  {YELLOW}[4]{RESET} Enter custom name")

    while True:
        response = input(f"\nChoice (current: {CYAN}{current}{RESET}): ").strip()

        if response == "":
            return current
        if response == "1":
            return "dev"
        if response == "2":
            return "prod"
        if response == "3":
            return "staging"
        if response == "4":
            custom = input("Enter environment name: ").strip()
            if custom:
                return custom
            print(f"{YELLOW}Environment name cannot be empty.{RESET}")
        else:
            print(f"{YELLOW}Invalid choice. Try 1-4.{RESET}")


def cmd_read(repo: str, env_name: str, env_file: Path = None) -> None:
    """Read and display current GitHub environment configuration."""
    print_header("GitHub Environment", f"{repo} → {env_name}")

    print(f"{DIM}Fetching from GitHub...{RESET}\n")

    variables = get_github_variables(repo, env_name)
    secrets = get_github_secrets(repo, env_name)

    # Get local counts for comparison
    if env_file is None:
        env_file = Path(".env")
    local_secrets, local_variables, _ = parse_env_file_with_sections(env_file)

    # Show comparison counts
    print(
        f"{BOLD}Local .env:{RESET}  {len(local_secrets)} secrets, {len(local_variables)} variables"
    )
    print(
        f"{BOLD}GitHub:    {RESET}  {len(secrets)} secrets, {len(variables)} variables"
    )
    print()

    if not variables and not secrets:
        print(
            f"{YELLOW}No variables or secrets found in environment '{env_name}'.{RESET}"
        )
        print(f"{DIM}Use 'Write to GitHub' to set up the environment.{RESET}")
        return

    # Display secrets
    print(f"{BOLD}SECRETS ({len(secrets)}):{RESET}")
    if secrets:
        for name in sorted(secrets):
            print(f"  {GREEN}✓{RESET} {name} = {YELLOW}[HIDDEN]{RESET}")
    else:
        print(f"  {DIM}(none){RESET}")

    # Display variables
    print(f"\n{BOLD}VARIABLES ({len(variables)}):{RESET}")
    if variables:
        for name in sorted(variables.keys()):
            print(f"  {GREEN}✓{RESET} {name} = {CYAN}{variables[name]}{RESET}")
    else:
        print(f"  {DIM}(none){RESET}")


def cmd_diff(repo: str, env_name: str, env_file: Path) -> Dict[str, any]:
    """Show differences between local .env and GitHub."""
    print_header("Diff: Local .env vs GitHub", f"{repo} → {env_name}")

    print(f"{DIM}Comparing...{RESET}\n")

    local_secrets, local_variables, _ = parse_env_file_with_sections(env_file)
    gh_variables = get_github_variables(repo, env_name)
    gh_secrets = get_github_secrets(repo, env_name)

    # Show counts
    print(
        f"{BOLD}Local .env:{RESET}  {len(local_secrets)} secrets, {len(local_variables)} variables"
    )
    print(
        f"{BOLD}GitHub:    {RESET}  {len(gh_secrets)} secrets, {len(gh_variables)} variables"
    )
    print()

    diff = {
        "new_secrets": [],
        "new_variables": [],
        "changed_variables": [],
        "unchanged_secrets": [],
        "unchanged_variables": [],
        "missing_local": [],
    }

    # Check local secrets against GitHub
    for key, value in local_secrets.items():
        if key not in gh_secrets:
            diff["new_secrets"].append((key, value))
            print(f"  {GREEN}+ [SECRET]{RESET} {key}")
        else:
            diff["unchanged_secrets"].append(key)
            print(f"  {DIM}= [SECRET]{RESET} {key} {DIM}(exists in GitHub){RESET}")

    # Check local variables against GitHub
    for key, value in local_variables.items():
        if key not in gh_variables:
            diff["new_variables"].append((key, value))
            print(f"  {GREEN}+ [VAR]{RESET} {key} = {CYAN}{value}{RESET}")
        elif gh_variables[key] != value:
            diff["changed_variables"].append((key, value, gh_variables[key]))
            print(f"  {YELLOW}~ [VAR]{RESET} {key}")
            print(f"           GitHub: {RED}{gh_variables[key]}{RESET}")
            print(f"           Local:  {GREEN}{value}{RESET}")
        else:
            diff["unchanged_variables"].append(key)
            print(f"  {DIM}= [VAR]{RESET} {key} {DIM}(matches GitHub){RESET}")

    # Check for items in GitHub but not local
    all_local_keys = set(local_secrets.keys()) | set(local_variables.keys())
    for key in gh_variables:
        if key not in all_local_keys:
            diff["missing_local"].append(("var", key, gh_variables[key]))
            print(
                f"  {RED}- [VAR]{RESET} {key} {DIM}(in GitHub, not in local .env){RESET}"
            )

    for key in gh_secrets:
        if key not in all_local_keys:
            diff["missing_local"].append(("secret", key, None))
            print(
                f"  {RED}- [SECRET]{RESET} {key} {DIM}(in GitHub, not in local .env){RESET}"
            )

    # Summary
    total_changes = (
        len(diff["new_secrets"])
        + len(diff["new_variables"])
        + len(diff["changed_variables"])
    )
    total_unchanged = len(diff["unchanged_secrets"]) + len(diff["unchanged_variables"])

    print(f"\n{BOLD}{'─' * 40}{RESET}")
    print(f"{BOLD}Summary:{RESET}")
    print(
        f"  {GREEN}+ New:{RESET}       {len(diff['new_secrets'])} secrets, {len(diff['new_variables'])} variables"
    )
    print(f"  {YELLOW}~ Changed:{RESET}   {len(diff['changed_variables'])} variables")
    print(f"  {RED}- Removed:{RESET}   {len(diff['missing_local'])} items")
    print(f"  {DIM}= Unchanged: {total_unchanged} items{RESET}")

    if total_changes == 0:
        print(f"\n{GREEN}✓ Local .env matches GitHub.{RESET}")

    return diff


def cmd_write(repo: str, env_name: str, env_file: Path) -> None:
    """Write all variables/secrets from .env to GitHub."""
    print_header("Write to GitHub", f"{repo} → {env_name}")

    secrets, variables, _ = parse_env_file_with_sections(env_file)

    if not secrets and not variables:
        print(f"{RED}Error: No values found in {env_file}{RESET}")
        return

    print(f"{BOLD}This will write the following to GitHub:{RESET}\n")

    print(f"{BOLD}SECRETS ({len(secrets)}):{RESET}")
    for name in sorted(secrets.keys()):
        print(f"  • {name} = {YELLOW}{mask_value(secrets[name])}{RESET}")

    print(f"\n{BOLD}VARIABLES ({len(variables)}):{RESET}")
    for name in sorted(variables.keys()):
        print(f"  • {name} = {CYAN}{variables[name]}{RESET}")

    print(f"\n{BOLD}{'─' * 40}{RESET}")
    print(f"{YELLOW}⚠ This will overwrite existing values in GitHub.{RESET}")

    if not confirm(
        f"\nProceed with writing {len(secrets)} secrets and {len(variables)} variables?"
    ):
        print(f"\n{YELLOW}Cancelled.{RESET}")
        return

    # Ensure environment exists
    if not ensure_environment_exists(repo, env_name):
        return

    # Write secrets
    print(f"\n{BOLD}Writing secrets...{RESET}")
    for name, value in secrets.items():
        if set_secret(repo, env_name, name, value):
            print(f"  {GREEN}✓{RESET} {name}")
        else:
            print(f"  {RED}✗{RESET} {name}")

    # Write variables
    print(f"\n{BOLD}Writing variables...{RESET}")
    gh_variables = get_github_variables(repo, env_name)
    for name, value in variables.items():
        exists = name in gh_variables
        success, error = set_variable(repo, env_name, name, value, exists)
        if success:
            print(f"  {GREEN}✓{RESET} {name}")
        else:
            print(f"  {RED}✗{RESET} {name} {DIM}({error}){RESET}")

    print(f"\n{GREEN}✓ Done!{RESET}")


def write_env_file(
    env_file: Path, secrets: Dict[str, str], variables: Dict[str, str]
) -> bool:
    """Write secrets and variables to a .env file with proper section headers."""
    try:
        lines = [
            "# ============================================================================",
            "# SECRETS (GitHub Secrets - sensitive values)",
            "# ============================================================================",
        ]
        for key in sorted(secrets.keys()):
            lines.append(f"{key}={secrets[key]}")

        lines.extend(
            [
                "",
                "# ============================================================================",
                "# VARIABLES (GitHub Variables - non-sensitive configuration)",
                "# ============================================================================",
            ]
        )
        for key in sorted(variables.keys()):
            lines.append(f"{key}={variables[key]}")

        lines.append("")  # Trailing newline
        env_file.write_text("\n".join(lines))
        return True
    except Exception as e:
        print(f"{RED}Error writing {env_file}: {e}{RESET}")
        return False


def cmd_download(repo: str, env_name: str, env_file: Path) -> None:
    """Download GitHub environment to local .env file."""
    print_header("Download from GitHub", f"{env_name} → {env_file}")

    print(f"{DIM}Fetching from GitHub...{RESET}\n")

    gh_variables = get_github_variables(repo, env_name)
    gh_secrets = get_github_secrets(repo, env_name)

    if not gh_variables and not gh_secrets:
        print(
            f"{YELLOW}No variables or secrets found in environment '{env_name}'.{RESET}"
        )
        print(f"{DIM}Nothing to download.{RESET}")
        return

    # Get current local values for comparison
    local_secrets, local_variables, _ = parse_env_file_with_sections(env_file)

    # Calculate what will change locally
    new_vars = []
    changed_vars = []
    deleted_local = []

    for key, value in gh_variables.items():
        if key not in local_variables:
            new_vars.append(("var", key, value))
            print(f"  {GREEN}+ [VAR]{RESET} {key} = {CYAN}{value}{RESET}")
        elif local_variables[key] != value:
            changed_vars.append(("var", key, value, local_variables[key]))
            print(
                f"  {YELLOW}~ [VAR]{RESET} {key}: {RED}{local_variables[key]}{RESET} → {GREEN}{value}{RESET}"
            )

    for key in gh_secrets:
        if key not in local_secrets:
            new_vars.append(("secret", key, "[HIDDEN]"))
            print(
                f"  {GREEN}+ [SECRET]{RESET} {key} {YELLOW}(value will be placeholder){RESET}"
            )

    # Check for local keys that will be removed (not in GitHub)
    for key in local_variables:
        if key not in gh_variables:
            deleted_local.append(("var", key))
            print(
                f"  {RED}- [VAR]{RESET} {key} {DIM}(will be removed from local){RESET}"
            )

    for key in local_secrets:
        if key not in gh_secrets:
            deleted_local.append(("secret", key))
            print(
                f"  {RED}- [SECRET]{RESET} {key} {DIM}(will be removed from local){RESET}"
            )

    total_changes = len(new_vars) + len(changed_vars)
    if not total_changes and not deleted_local:
        print(f"{GREEN}✓ Local .env is up to date with GitHub.{RESET}")
        return

    print(f"\n{BOLD}{'─' * 40}{RESET}")
    print(f"{BOLD}Summary:{RESET}")
    print(f"  {GREEN}+ Add/Update:{RESET} {total_changes} items")
    if deleted_local:
        print(f"  {RED}- Remove:{RESET}     {len(deleted_local)} items from local .env")
        print(
            f"\n{YELLOW}⚠ WARNING: {len(deleted_local)} local key(s) will be REMOVED from {env_file}{RESET}"
        )
        print(f"{DIM}  These exist in your local .env but not in GitHub.{RESET}")

    # Note about secrets
    print(f"\n{YELLOW}⚠ Note: Secret VALUES cannot be downloaded from GitHub.{RESET}")
    print(
        f"{DIM}  New secrets will be added with placeholder value 'REPLACE_ME'.{RESET}"
    )
    print(f"{DIM}  You'll need to fill in the actual secret values manually.{RESET}")

    if not confirm(f"\nOverwrite {env_file} with GitHub values?"):
        print(f"\n{YELLOW}Cancelled.{RESET}")
        return

    # Build new env content
    # For secrets, we can only get names (not values), so preserve existing or use placeholder
    new_secrets = {}
    for key in gh_secrets:
        if key in local_secrets:
            new_secrets[key] = local_secrets[key]  # Preserve existing value
        else:
            new_secrets[key] = "REPLACE_ME"  # Placeholder for new secrets

    if write_env_file(env_file, new_secrets, gh_variables):
        print(
            f"\n{GREEN}✓ Downloaded {len(gh_secrets)} secrets and {len(gh_variables)} variables to {env_file}{RESET}"
        )
    else:
        print(f"\n{RED}✗ Failed to write {env_file}{RESET}")


def cmd_upload(repo: str, env_name: str, env_file: Path) -> None:
    """Upload local .env to GitHub (adds, updates, and optionally removes)."""
    print_header("Upload to GitHub", f"{env_file} → {env_name}")

    # Safety check: abort if env file is missing
    if not env_file.exists():
        print(f"{RED}Error: Environment file not found: {env_file}{RESET}")
        print(f"{DIM}Cannot upload without a local .env file.{RESET}")
        print(
            f"{DIM}Use 'Download from GitHub' to fetch current values, or create {env_file} first.{RESET}"
        )
        return

    print(f"{DIM}Checking for changes...{RESET}\n")

    # Get local values including placeholder keys (to prevent accidental deletion)
    local_secrets, local_variables, placeholder_keys = parse_env_file_with_sections(
        env_file, include_placeholders=True
    )

    # Safety check: abort if env file has no usable values
    if not local_secrets and not local_variables:
        print(f"{RED}Error: No values found in {env_file}{RESET}")
        print(f"{DIM}Cannot upload an empty or placeholder-only .env file.{RESET}")
        print(
            f"{DIM}Use 'Download from GitHub' to fetch current values, or add values to {env_file}.{RESET}"
        )
        return

    gh_variables = get_github_variables(repo, env_name)
    gh_secrets = get_github_secrets(repo, env_name)

    # Calculate diff
    changes = []
    deletions = []
    skipped_placeholders = []

    # Check secrets - new ones to add
    for key, value in local_secrets.items():
        if key not in gh_secrets:
            changes.append(("new_secret", key, value, None))
            print(f"  {GREEN}+ [SECRET]{RESET} {key}")

    # Check variables - new and changed
    for key, value in local_variables.items():
        if key not in gh_variables:
            changes.append(("new_var", key, value, None))
            print(f"  {GREEN}+ [VAR]{RESET} {key} = {CYAN}{value}{RESET}")
        elif gh_variables[key] != value:
            changes.append(("changed_var", key, value, gh_variables[key]))
            print(
                f"  {YELLOW}~ [VAR]{RESET} {key}: {RED}{gh_variables[key]}{RESET} → {GREEN}{value}{RESET}"
            )

    # Check for variables to delete (in GitHub but not in local variables)
    # Use type-specific checks: variables against local_variables, secrets against local_secrets
    for key in gh_variables:
        if key not in local_variables:
            # Check if this key has a placeholder value (don't delete it)
            if placeholder_keys and key in placeholder_keys:
                skipped_placeholders.append(("var", key))
                print(
                    f"  {DIM}· [VAR]{RESET} {key} {DIM}(skipped - has placeholder in .env){RESET}"
                )
            else:
                deletions.append(("del_var", key))
                print(
                    f"  {RED}- [VAR]{RESET} {key} {DIM}(will be DELETED from GitHub){RESET}"
                )

    # Check for secrets to delete (in GitHub but not in local secrets)
    for key in gh_secrets:
        if key not in local_secrets:
            # Check if this key has a placeholder value (don't delete it)
            if placeholder_keys and key in placeholder_keys:
                skipped_placeholders.append(("secret", key))
                print(
                    f"  {DIM}· [SECRET]{RESET} {key} {DIM}(skipped - has placeholder in .env){RESET}"
                )
            else:
                deletions.append(("del_secret", key))
                print(
                    f"  {RED}- [SECRET]{RESET} {key} {DIM}(will be DELETED from GitHub){RESET}"
                )

    if not changes and not deletions:
        print(f"{GREEN}✓ No changes to apply. GitHub is up to date.{RESET}")
        return

    print(f"\n{BOLD}{'─' * 40}{RESET}")
    print(f"{BOLD}Summary:{RESET}")
    print(f"  {GREEN}+ Add/Update:{RESET} {len(changes)} items")
    print(f"  {RED}- Delete:{RESET}     {len(deletions)} items")

    # Prominent warning for deletions
    if deletions:
        print(f"\n{RED}{'!' * 60}{RESET}")
        print(
            f"{RED}  ⚠ WARNING: {len(deletions)} item(s) will be PERMANENTLY DELETED from GitHub!{RESET}"
        )
        print(f"{RED}{'!' * 60}{RESET}")
        print(
            f"{DIM}  These keys exist in GitHub but not in your local .env file.{RESET}"
        )
        print(
            f"{DIM}  If this is unintended, use 'Download from GitHub' first to sync locally.{RESET}"
        )

    if not confirm(f"\nApply these changes to '{env_name}'?"):
        print(f"\n{YELLOW}Cancelled.{RESET}")
        return

    # Ensure environment exists
    if not ensure_environment_exists(repo, env_name):
        return

    # Apply additions and updates
    if changes:
        print(f"\n{BOLD}Applying changes...{RESET}")
        for change_type, name, value, old_value in changes:
            error = ""
            if change_type == "new_secret":
                success = set_secret(repo, env_name, name, value)
            elif change_type == "new_var":
                success, error = set_variable(repo, env_name, name, value, exists=False)
            elif change_type == "changed_var":
                success, error = set_variable(repo, env_name, name, value, exists=True)
            else:
                success = False

            if success:
                print(f"  {GREEN}✓{RESET} {name}")
            else:
                err_msg = f" {DIM}({error}){RESET}" if error else ""
                print(f"  {RED}✗{RESET} {name}{err_msg}")

    # Apply deletions
    if deletions:
        print(f"\n{BOLD}Removing deleted items...{RESET}")
        for del_type, name in deletions:
            if del_type == "del_var":
                success, error = delete_variable(repo, env_name, name)
            elif del_type == "del_secret":
                success, error = delete_secret(repo, env_name, name)
            else:
                success = False
                error = "Unknown type"

            if success:
                print(f"  {GREEN}✓{RESET} {name} {DIM}(removed){RESET}")
            else:
                err_msg = f" {DIM}({error}){RESET}" if error else ""
                print(f"  {RED}✗{RESET} {name}{err_msg}")

    print(f"\n{GREEN}✓ Done!{RESET}")


def interactive_menu(repo: str, env_name: str, env_file: Path) -> None:
    """Run the interactive menu."""
    while True:
        print_header("GitHub Environment Manager", f"{repo}")

        print(f"  Current environment: {CYAN}{BOLD}{env_name}{RESET}")
        print(f"  Local .env file:     {CYAN}{env_file}{RESET}")
        print()

        options = [
            ("1", "Read GitHub environment"),
            ("2", "Diff local .env vs GitHub"),
            ("3", f"Download from GitHub {DIM}(GitHub → local .env){RESET}"),
            ("4", f"Upload to GitHub {DIM}(local .env → GitHub){RESET}"),
            ("5", "Write all to GitHub (creates & overwrites)"),
            ("6", "Change environment"),
            ("q", "Quit"),
        ]

        print_menu(options)

        choice = input("Select option: ").strip().lower()

        if choice == "1":
            cmd_read(repo, env_name, env_file)
        elif choice == "2":
            cmd_diff(repo, env_name, env_file)
        elif choice == "3":
            cmd_download(repo, env_name, env_file)
        elif choice == "4":
            cmd_upload(repo, env_name, env_file)
        elif choice == "5":
            cmd_write(repo, env_name, env_file)
        elif choice == "6":
            env_name = prompt_environment(env_name)
            continue  # Skip the "press Enter" prompt
        elif choice in ("q", "quit", "exit"):
            print(f"\n{DIM}Goodbye!{RESET}\n")
            break
        else:
            print(f"{YELLOW}Invalid option. Try again.{RESET}")
            continue

        print()
        input(f"{DIM}Press Enter to continue...{RESET}")


def prompt_initial_environment() -> str:
    """Prompt user to select environment at startup."""
    print(f"\n{BOLD}Select GitHub Environment:{RESET}")
    print(f"  {YELLOW}[1]{RESET} dev {DIM}(development - default){RESET}")
    print(f"  {YELLOW}[2]{RESET} prod {DIM}(production){RESET}")
    print(f"  {YELLOW}[3]{RESET} staging")
    print(f"  {YELLOW}[4]{RESET} Enter custom name")

    while True:
        response = input("\nChoice [1]: ").strip()

        if response == "" or response == "1":
            return "dev"
        if response == "2":
            return "prod"
        if response == "3":
            return "staging"
        if response == "4":
            custom = input("Enter environment name: ").strip()
            if custom:
                return custom
            print(f"{YELLOW}Environment name cannot be empty.{RESET}")
        else:
            print(f"{YELLOW}Invalid choice. Try 1-4.{RESET}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Manage GitHub environment variables and secrets interactively",
    )
    parser.add_argument(
        "--env", default=None, help="GitHub environment name (skips prompt if provided)"
    )
    parser.add_argument(
        "--env-file",
        default=".env",
        type=Path,
        help="Path to .env file (default: .env)",
    )
    parser.add_argument(
        "command",
        nargs="?",
        choices=["read", "write", "diff", "download", "upload"],
        help="Run a specific command: read, diff, download (GitHub→local), upload (local→GitHub), write",
    )

    args = parser.parse_args()

    # Get repository
    print(f"{DIM}Connecting to GitHub...{RESET}")
    repo = get_repo()
    print(f"{GREEN}✓{RESET} Connected to {CYAN}{repo}{RESET}")

    # Determine environment
    if args.env:
        env_name = args.env
    else:
        env_name = prompt_initial_environment()

    print(f"\n{GREEN}✓{RESET} Using environment: {CYAN}{BOLD}{env_name}{RESET}")

    # Show diff on startup (more useful than just reading GitHub state)
    cmd_diff(repo, env_name, args.env_file)

    # If command specified, run it directly (diff already shown above)
    if args.command:
        if args.command == "read":
            cmd_read(repo, env_name, args.env_file)
        elif args.command == "diff":
            pass  # Already shown above
        elif args.command == "write":
            cmd_write(repo, env_name, args.env_file)
        elif args.command == "download":
            cmd_download(repo, env_name, args.env_file)
        elif args.command == "upload":
            cmd_upload(repo, env_name, args.env_file)
        return

    # Interactive mode
    interactive_menu(repo, env_name, args.env_file)


if __name__ == "__main__":
    main()
