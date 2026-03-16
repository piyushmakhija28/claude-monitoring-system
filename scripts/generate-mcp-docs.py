#!/usr/bin/env python3
"""
MCP Documentation Generator - Auto-generate tool tables from @mcp.tool() decorators.

Scans all MCP server files in src/mcp/ and extracts tool names, docstrings,
and parameter info to generate a markdown summary.

Usage:
    python scripts/generate-mcp-docs.py              # Print to stdout
    python scripts/generate-mcp-docs.py --output docs/MCP-TOOLS.md  # Write to file

Windows-safe: ASCII only (cp1252 compatible).
"""

import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MCP_DIR = PROJECT_ROOT / "src" / "mcp"


def extract_tools(filepath):
    """Extract @mcp.tool() decorated functions from a Python file."""
    try:
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except Exception as e:
        return [], str(e)

    tools = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        # Check for @mcp.tool() decorator
        for dec in node.decorator_list:
            is_mcp_tool = False
            if isinstance(dec, ast.Call):
                if isinstance(dec.func, ast.Attribute) and dec.func.attr == "tool":
                    is_mcp_tool = True
            elif isinstance(dec, ast.Attribute) and dec.attr == "tool":
                is_mcp_tool = True

            if is_mcp_tool:
                docstring = ast.get_docstring(node) or ""
                first_line = docstring.split("\n")[0].strip() if docstring else ""
                params = []
                for arg in node.args.args:
                    if arg.arg != "self":
                        params.append(arg.arg)
                tools.append({
                    "name": node.name,
                    "doc": first_line,
                    "params": params,
                    "line": node.lineno,
                })
                break

    return tools, None


def get_server_name(filepath):
    """Extract FastMCP server name from file."""
    try:
        for line in filepath.read_text(encoding="utf-8").splitlines():
            if "FastMCP(" in line:
                # Extract name from FastMCP("name", ...)
                start = line.index('"') + 1
                end = line.index('"', start)
                return line[start:end]
    except Exception:
        pass
    return filepath.stem.replace("_mcp_server", "")


def main():
    output_file = None
    if len(sys.argv) > 2 and sys.argv[1] == "--output":
        output_file = Path(sys.argv[2])

    lines = []
    lines.append("# MCP Tool Reference")
    lines.append("")
    lines.append("Auto-generated from `src/mcp/*_mcp_server.py` via `scripts/generate-mcp-docs.py`.")
    lines.append("")

    total_tools = 0
    total_servers = 0

    server_files = sorted(MCP_DIR.glob("*_mcp_server.py"))

    for server_file in server_files:
        server_name = get_server_name(server_file)
        tools, error = extract_tools(server_file)

        if error:
            lines.append(f"## {server_name} (ERROR: {error})")
            lines.append("")
            continue

        total_servers += 1
        total_tools += len(tools)

        lines.append(f"## {server_name} ({len(tools)} tools)")
        lines.append("")
        lines.append(f"**File:** `{server_file.name}`")
        lines.append("")
        lines.append("| Tool | Description | Parameters |")
        lines.append("|------|-------------|------------|")

        for tool in tools:
            params_str = ", ".join(tool["params"]) if tool["params"] else "-"
            doc = tool["doc"][:80] if tool["doc"] else "-"
            lines.append(f"| `{tool['name']}` | {doc} | {params_str} |")

        lines.append("")

    # Summary
    lines.append("---")
    lines.append("")
    lines.append(f"**Total: {total_servers} servers, {total_tools} tools**")
    lines.append("")

    output = "\n".join(lines)

    if output_file:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(output, encoding="utf-8")
        print(f"[OK] Generated {output_file} ({total_servers} servers, {total_tools} tools)")
    else:
        print(output)


if __name__ == "__main__":
    main()
