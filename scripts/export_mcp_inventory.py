"""Regenerate the reviewable REST/MCP contract: python -m scripts.export_mcp_inventory."""

import ast
import inspect
import json
from pathlib import Path

from fastapi.routing import APIRoute

from src.app import app


def inventory():
    spec = app.openapi()
    routes = {
        (r.path, m): r for r in app.routes if isinstance(r, APIRoute) for m in r.methods
    }
    rows = []
    for name, op in app.state.mcp.operations.items():
        operation = spec.get("paths", {}).get(op.path, {}).get(op.method.lower(), {})
        route = routes.get((op.path, op.method))
        statuses = set()
        source = None
        if route:
            source_file = Path(inspect.getsourcefile(route.endpoint))
            source = str(source_file.relative_to(Path.cwd()))
            tree = ast.parse(source_file.read_text())
            functions = {
                n.name: n
                for n in tree.body
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
            pending, seen = [route.endpoint.__name__], set()
            # Include same-module helper error statuses as well as the handler.
            while pending:
                function = pending.pop()
                if function in seen or function not in functions:
                    continue
                seen.add(function)
                for node in ast.walk(functions[function]):
                    if isinstance(node, ast.Call):
                        if (
                            isinstance(node.func, ast.Name)
                            and node.func.id in functions
                        ):
                            pending.append(node.func.id)
                        for kw in node.keywords:
                            if kw.arg == "status_code" and isinstance(
                                kw.value, ast.Constant
                            ):
                                if isinstance(kw.value.value, int):
                                    statuses.add(kw.value.value)
        rows.append(
            {
                "tool": name,
                "method": op.method,
                "path": op.path,
                "source": source,
                "parameters": operation.get("parameters", []),
                "requestBody": operation.get("requestBody"),
                "responses": operation.get("responses", {}),
                "additional_explicit_handler_statuses": sorted(statuses),
                "inputSchema": op.tool.inputSchema,
                "annotations": op.tool.annotations.model_dump(),
            }
        )
    return rows


if __name__ == "__main__":
    Path("docs/mcp-route-mapping.json").write_text(
        json.dumps(inventory(), indent=2) + "\n"
    )
