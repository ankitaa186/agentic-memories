"""Check the maintained onboarding docs, local links, assets, and runnable example.

Historical design/sprint documents are not linted, but links to them must resolve.
Uses only the standard library: python3 scripts/check_docs.py
"""

import ast
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
PAGES = (
    [
        ROOT / name
        for name in (
            "README.md",
            "CHANGELOG.md",
            "CONTRIBUTING.md",
            "docs/README.md",
            "docs/MCP.md",
            "docs/ROADMAP.md",
            "docs/assets/README.md",
            "examples/README.md",
        )
    ]
    + sorted((ROOT / "docs/guides").glob("*.md"))
    + sorted((ROOT / "docs/releases").glob("*.md"))
)


def without_fences(source):
    return re.sub(r"^```.*?^```\s*$", "", source, flags=re.M | re.S)


def anchors(path):
    found = set()
    counts = {}
    for heading in re.findall(
        r"^#{1,6}\s+(.+)$", without_fences(path.read_text()), re.M
    ):
        slug = re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-")
        count = counts.get(slug, 0)
        counts[slug] = count + 1
        found.add(f"{slug}-{count}" if count else slug)
    return found


def main():
    errors = []
    links = 0
    for page in PAGES:
        source = page.read_text()
        for target in re.findall(r"\]\(([^\s)]+)\)", without_fences(source)):
            url = urlsplit(target)
            if url.scheme or url.netloc:
                continue
            links += 1
            path = (page.parent / unquote(url.path)).resolve() if url.path else page
            if not path.exists():
                errors.append(f"{page.relative_to(ROOT)}: missing {target}")
            elif url.fragment and path.suffix == ".md":
                if unquote(url.fragment) not in anchors(path):
                    errors.append(f"{page.relative_to(ROOT)}: missing anchor {target}")
        for block in re.findall(r"^```json\s*\n(.*?)^```", source, flags=re.M | re.S):
            try:
                # Some guides intentionally show multiple newline-delimited calls.
                decoder = json.JSONDecoder()
                rest = block.strip()
                while rest:
                    _, end = decoder.raw_decode(rest)
                    rest = rest[end:].strip()
            except ValueError as exc:
                errors.append(f"{page.relative_to(ROOT)}: invalid JSON example: {exc}")
    for asset in (ROOT / "docs/assets").glob("*.svg"):
        tree = ET.parse(asset)
        ns = {"svg": "http://www.w3.org/2000/svg"}
        if tree.find("svg:title", ns) is None or tree.find("svg:desc", ns) is None:
            errors.append(f"{asset.name}: missing accessible title/description")
    for example_path in (ROOT / "examples").glob("*.py"):
        ast.parse(example_path.read_text())
    inventory = json.loads((ROOT / "docs/mcp-route-mapping.json").read_text())
    tools = {item["tool"] for item in inventory}
    example = (ROOT / "examples/mcp_memory.py").read_text()
    for tool in ("store_transcript", "retrieve"):
        if tool not in tools or f'"{tool}"' not in example:
            errors.append(f"Demo tool missing from inventory/example: {tool}")
    readme = (ROOT / "README.md").read_text()
    application = sum(
        not item["path"].startswith(("/docs", "/redoc", "/openapi"))
        for item in inventory
    )
    if (
        f"**{application} application operations and {len(inventory) - application} documentation tools**"
        not in readme
    ):
        errors.append("README tool count does not match inventory")
    if len(readme.splitlines()) > 350:
        errors.append("README exceeds the 350-line onboarding budget")
    if re.search(r"digital soul|hypersapience|human-like consciousness", readme, re.I):
        errors.append("README contains retired product positioning")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(
        f"PASS: {len(PAGES)} maintained pages, {links} local links, SVG metadata, JSON examples, demo syntax, and {len(tools)} tool inventory entries."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
