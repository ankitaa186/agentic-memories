from pathlib import Path
from html import escape

root = Path(__file__).resolve().parents[1] / "docs" / "assets"
base = """<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="{height}" viewBox="0 0 1080 {height}" role="img" aria-labelledby="title desc">
<title id="title">{title}</title><desc id="desc">{desc}</desc>
<defs><linearGradient id="accent"><stop stop-color="#a78bfa"/><stop offset="1" stop-color="#c4b5fd"/></linearGradient><marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#94a3b8"/></marker></defs>
<rect width="1080" height="{height}" rx="20" fill="#0b0a12"/>
<g font-family="Arial, Helvetica, sans-serif">"""


def text(x, y, value, size=18, color="#f4efff", weight="normal"):
    return f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" font-weight="{weight}">{escape(value)}</text>\n'


def rect(x, y, w, h, stroke="#3c2e50"):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="#191326" stroke="{stroke}"/>\n'


def line(x, y, x2, y2):
    return f'<path d="M{x} {y} L{x2} {y2}" stroke="#94a3b8" stroke-width="2" fill="none" marker-end="url(#arrow)"/>\n'


def save(name, h, title, desc, body):
    (root / name).write_text(
        base.format(height=h, title=title, desc=desc) + body + "</g></svg>\n"
    )


b = text(
    40, 52, "A familiar preference. A new conversation.", 30, weight="bold"
) + text(
    40,
    83,
    "Your companion can recall what you have shared before.",
    18,
    "#bcb0cf",
)
for x, step, title, lines in [
    (
        40,
        "01 / STORE",
        "Save a preference",
        ["“Evening walks", "help me unwind.”"],
    ),
    (
        397,
        "02 / PERSIST",
        "Close the session",
        ["The memory stays in storage.", "The client connection ends."],
    ),
    (
        754,
        "03 / RECALL",
        "Ask in a new session",
        ["“How do I unwind?”", "Recall a familiar preference."],
    ),
]:
    b += (
        rect(x, 120, 286, 185, "#65517f")
        + text(x + 22, 153, step, 14, "#a5b4fc", "bold")
        + text(x + 22, 191, title, 23, weight="bold")
    )
    for i, t in enumerate(lines):
        b += text(x + 22, 231 + i * 27, t, 17, "#d4c8e5")
b += (
    line(337, 212, 382, 212)
    + line(694, 212, 739, 212)
    + text(
        40,
        343,
        "MCP tools: store_memory_direct → retrieve   •   The agent decides when to call them.",
        16,
        "#bcb0cf",
    )
)
save(
    "memory-flow.svg",
    378,
    "Memory across sessions",
    "Store a preference, close the connection, and recall it through a new connection.",
    b,
)
b = text(40, 52, "One memory service. Two ways to connect.", 30, weight="bold") + text(
    40,
    83,
    "MCP is the preferred agent interface; REST shares the same application.",
    18,
    "#bcb0cf",
)
b += (
    rect(150, 120, 350, 90, "#a78bfa")
    + text(175, 154, "Personal AI via MCP", 23, weight="bold")
    + text(175, 184, "Streamable HTTP /mcp", 18, "#d4c8e5")
)
b += (
    rect(580, 120, 350, 90)
    + text(605, 154, "REST clients + web UI", 23, weight="bold")
    + text(605, 184, "HTTP routes", 18, "#d4c8e5")
)
b += line(325, 214, 325, 255) + line(755, 214, 755, 255)
b += (
    rect(150, 265, 780, 115, "#c4b5fd")
    + text(175, 306, "Shared FastAPI application", 25, weight="bold")
    + text(
        175,
        342,
        "Validation • ingestion • retrieval • profiles • intents • maintenance",
        19,
        "#d4c8e5",
    )
)
for x in [210, 540, 870]:
    b += line(x, 384, x, 426)
for x, title, sub in [
    (60, "ChromaDB", "Vectors + memory documents"),
    (390, "PostgreSQL + TimescaleDB", "Structured + time-based records"),
    (720, "Redis", "Cache + coordination"),
]:
    b += (
        rect(x, 438, 300, 96)
        + text(x + 17, 473, title, 20, weight="bold")
        + text(x + 17, 505, sub, 16, "#d4c8e5")
    )
b += text(
    60,
    578,
    "Configured providers: embeddings + extraction   /   Optional tracing: Langfuse",
    17,
    "#bcb0cf",
)
save(
    "architecture.svg",
    615,
    "Agentic Memories architecture",
    "Personal AI via MCP and REST clients share FastAPI and its ChromaDB, PostgreSQL with TimescaleDB, and Redis stores.",
    b,
)
# Social card is editable, with no implied benchmark or client endorsement.
b = (
    text(65, 90, "OPEN SOURCE / MCP", 18, "#a5b4fc", "bold")
    + text(65, 184, "Agentic Memories", 58, weight="bold")
    + text(65, 246, "Memory for your", 38, "#d4c8e5")
    + text(65, 298, "personal AI companion.", 38, "#d4c8e5")
)
b += (
    rect(65, 351, 950, 110, "#65517f")
    + text(
        90,
        394,
        "Experiences. Preferences. Continuity.",
        27,
        weight="bold",
    )
    + text(90, 429, "Self-hosted memory service • MCP + REST", 20, "#bcb0cf")
    + text(65, 526, "github.com/ankitaa186/agentic-memories", 19, "#a5b4fc")
)
save(
    "social-preview.svg",
    567,
    "Agentic Memories social preview",
    "Open-source MCP memory service. Memory for your personal AI companion.",
    b,
)

# A compact, accurate visual of the captured example output.
transcript = root.parents[1] / "examples" / "mcp-memory-output.txt"
if (
    transcript.exists()
    and "PASS:" in transcript.read_text()
    and "CLEANUP:" in transcript.read_text()
):
    b = text(
        40, 51, "A preference remembered across conversations", 30, weight="bold"
    ) + text(
        40,
        83,
        "Recorded MCP example • retrieved content, not a generated answer",
        17,
        "#bcb0cf",
    )
    b += rect(40, 116, 1000, 144, "#a78bfa") + text(
        64, 151, "SESSION 1 / store_memory_direct", 17, "#c4b5fd", "bold"
    )
    b += text(64, 190, "Evening walks help me unwind.", 23) + text(
        64, 226, "I prefer quiet routes near the water.", 23
    )
    b += text(64, 302, "Connection closed → New MCP connection", 18, "#bcb0cf")
    b += rect(40, 334, 1000, 170, "#c4b5fd") + text(
        64, 371, "SESSION 2 / retrieve", 17, "#c4b5fd", "bold"
    )
    b += text(64, 410, "How do I like to unwind?", 23, weight="bold")
    b += text(64, 449, "Recalled the saved evening-walk preference.", 22) + text(
        64, 482, "Verified matching record ID and content.", 17, "#bcb0cf"
    )
    b += text(
        40,
        551,
        "PASS / cross-session recall     CLEANUP / demo record deleted",
        18,
        "#ddd0ff",
    )
    save(
        "mcp-demo.svg",
        590,
        "Verified cross-session MCP example",
        "A real run stores an evening-walk preference, recalls the identical record through a new connection, and deletes the demo memory.",
        b,
    )
