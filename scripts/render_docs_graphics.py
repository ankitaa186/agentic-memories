from pathlib import Path
from html import escape
import re
import textwrap

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
        "01 / CONVERSATION",
        "Share an experience",
        ["“Evening walks", "help me unwind.”"],
    ),
    (
        397,
        "02 / EXTRACTION",
        "Identify what matters",
        ["Extract and organize memories.", "Check duplicates and store."],
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
        "MCP tools: store_transcript → extraction pipeline → retrieve",
        16,
        "#bcb0cf",
    )
)
save(
    "memory-flow.svg",
    378,
    "Memory across sessions",
    "Submit conversation, extract memories, then recall them in a later session.",
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
        "Conversation → Extraction → Recall",
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

# The principal product flow: conversations enter; the service derives memories.
b = text(40, 52, "Conversation in. Useful memories out.", 32, weight="bold")
b += text(
    40,
    84,
    "Your companion supplies dialogue. The pipeline builds the memories.",
    18,
    "#bcb0cf",
)
b += rect(40, 112, 1000, 84, "#65517f")
b += text(62, 142, "CONVERSATION", 14, "#c4b5fd", "bold")
b += text(
    62,
    174,
    "“Evening walks help me unwind. I like herbal tea and a novel afterward.”",
    22,
)
for x, title, detail in [
    (40, "1 / Worthiness", ["Is this worth", "remembering?"]),
    (298, "2 / Extraction", ["Identify useful facts,", "preferences and experiences."]),
    (556, "3 / Organization", ["Classify, enrich, embed", "and check duplicates."]),
    (814, "4 / Memory", ["Build profile context;", "store applicable records."]),
]:
    b += rect(x, 248, 226, 145, "#a78bfa")
    b += text(x + 15, 282, title, 21, weight="bold")
    b += text(x + 15, 321, detail[0], 16, "#d4c8e5")
    b += text(x + 15, 348, detail[1], 16, "#d4c8e5")
    if x < 814:
        b += line(x + 231, 320, x + 249, 320)
b += line(150, 201, 150, 236)
b += line(927, 399, 927, 433)
b += rect(40, 446, 1000, 86, "#c4b5fd")
b += text(62, 478, "LATER RECALL / retrieve", 16, "#c4b5fd", "bold")
b += text(62, 511, "Extracted context is available to help your companion respond.", 22)
save(
    "extraction-pipeline.svg",
    565,
    "Conversation extraction pipeline",
    "Dialogue passes through worthiness assessment, extraction, classification and enrichment, duplicate checks, profile extraction and storage. Later retrieval supplies context to the companion.",
    b,
)

# Render only recorded extraction results, never invent model output for the graphic.
transcript = root.parents[1] / "examples" / "mcp-memory-output.txt"
recording = transcript.read_text()
if (
    "PASS: recalled pipeline-extracted memories through a new connection."
    not in recording
):
    raise ValueError(
        "A successful extraction recording is required for the demo graphic"
    )
extracted = re.findall(r"^EXTRACTED \[(.*?)\]: (.*)$", recording, re.M)
if not extracted:
    raise ValueError("No extracted memories found in recording")
b = text(40, 51, "From a conversation to personal memory", 30, weight="bold")
b += text(
    40,
    83,
    "Real MCP extraction run • wording and memory count vary by model",
    17,
    "#bcb0cf",
)
b += rect(40, 112, 1000, 72, "#65517f")
b += text(
    62, 143, "INPUT / 4 conversation turns via store_transcript", 20, weight="bold"
)
b += text(
    62,
    170,
    "Evening walks, quiet routes, herbal tea, reading and avoiding coffee.",
    18,
    "#d4c8e5",
)
b += text(
    40,
    225,
    f"EXTRACTED / {len(extracted)} memories returned by the pipeline",
    21,
    "#c4b5fd",
    "bold",
)
y = 245
for layer, content in extracted:
    lines = textwrap.wrap(content, width=81)
    height = 45 + len(lines) * 25
    b += rect(40, y, 1000, height)
    b += text(58, y + 24, layer.upper(), 13, "#c4b5fd", "bold")
    for index, line_text in enumerate(lines):
        b += text(58, y + 50 + index * 25, line_text, 19)
    y += height + 10
b += text(
    40,
    y + 30,
    "NEW SESSION / retrieved records matched extraction-result IDs",
    19,
    "#ddd0ff",
    "bold",
)
b += text(
    40,
    y + 61,
    "Printed memories are actual extraction output, not manually authored records.",
    17,
    "#bcb0cf",
)
save(
    "mcp-demo.svg",
    y + 92,
    "Verified conversation extraction example",
    "A real run of store_transcript produced classified memories from four conversation turns. A new MCP connection recalled those extracted records.",
    b,
)
