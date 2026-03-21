"""
Draw.io Diagram MCP Server - Generate editable .drawio files for all SDLC diagrams.

No external API required. draw.io files are pure XML (mxGraph format).
All 12 UML diagram types + call graph supported.

Tools:
    generate_drawio_diagram    - Single diagram as .drawio file
    generate_all_drawio        - All 12 diagram types as .drawio files
    get_shareable_url          - app.diagrams.net shareable URL for a .drawio file
    list_drawio_diagrams       - List existing .drawio files in output dir
    convert_mermaid_to_drawio  - Convert existing Mermaid .md to .drawio (best-effort)
"""

import sys
from pathlib import Path

# Path setup
sys.path.insert(0, str(Path(__file__).resolve().parent))

from mcp.server.fastmcp import FastMCP
from base.decorators import mcp_tool_handler

mcp = FastMCP(
    "drawio-diagram",
    instructions=(
        "Generate editable draw.io (.drawio) diagrams for all SDLC UML types. "
        "Files can be opened in draw.io desktop, app.diagrams.net, or VS Code. "
        "Produces shareable URLs (app.diagrams.net) for collaboration."
    ),
)


# ---- helpers ----------------------------------------------------------

def _scripts_dir():
    return Path(__file__).resolve().parent.parent.parent / "scripts"


def _ensure_scripts_path():
    sd = str(_scripts_dir())
    if sd not in sys.path:
        sys.path.insert(0, sd)


def _get_converter():
    _ensure_scripts_path()
    from langgraph_engine.diagrams.drawio_converter import DrawioConverter
    return DrawioConverter()


def _get_ast_analyzer(project_path):
    """Load AST analysis data from the project."""
    _ensure_scripts_path()
    try:
        from langgraph_engine.diagrams.ast_analyzer import UMLAstAnalyzer
        analyzer = UMLAstAnalyzer(project_path)
        return analyzer.analyze()
    except Exception:
        return {}


def _get_call_graph_data(project_path):
    """Load call graph data as analysis_data dict."""
    _ensure_scripts_path()
    try:
        from langgraph_engine.call_graph_builder import CallGraphBuilder
        builder = CallGraphBuilder(project_path)
        graph = builder.build()
        classes = []
        for fqn, info in list(graph.items())[:60]:
            parts = fqn.split("::")
            if len(parts) == 2:
                file_part, cls_method = parts
                if "." in cls_method:
                    cls_name = cls_method.split(".")[0]
                else:
                    cls_name = Path(file_part).stem
            else:
                cls_name = fqn
            # Deduplicate
            existing = next((c for c in classes if c["name"] == cls_name), None)
            if not existing:
                existing = {"name": cls_name, "methods": [], "attributes": [], "bases": []}
                classes.append(existing)
            method_name = info.get("method", fqn.split(".")[-1] if "." in fqn else fqn)
            existing["methods"].append({"name": method_name, "visibility": "+"})
        return {"classes": classes}
    except Exception:
        return {}


def _resolve_output_dir(project_path, output_dir):
    """Return absolute Path for output_dir."""
    od = Path(output_dir)
    if not od.is_absolute():
        od = Path(project_path) / od
    od.mkdir(parents=True, exist_ok=True)
    return od


def _save_drawio(xml_content, output_path):
    """Write XML to a .drawio file."""
    with open(str(output_path), "w", encoding="utf-8") as f:
        f.write(xml_content)
    return str(output_path)


# ======================================================================
# Tool 1: generate_drawio_diagram
# ======================================================================

@mcp.tool()
@mcp_tool_handler
def generate_drawio_diagram(
    diagram_type: str,
    project_path: str,
    output_dir: str = "docs/drawio",
    github_repo: str = "",
    github_branch: str = "main",
) -> dict:
    """Generate a single UML diagram as an editable .drawio file.

    Analyzes the project with AST/CallGraph and produces a draw.io XML file
    that can be opened directly in draw.io, app.diagrams.net, or VS Code
    with the draw.io extension.

    Args:
        diagram_type: One of: class, sequence, activity, state, component,
                      package, deployment, usecase, object, communication,
                      composite, interaction.
        project_path: Root path of the project to analyze.
        output_dir: Output directory (relative to project root, or absolute).
                    Default: docs/drawio
        github_repo: Optional "owner/repo" for shareable GitHub URL.
                     E.g. "techdeveloper-org/claude-workflow-engine"
        github_branch: Branch for GitHub raw URL. Default: "main"

    Returns:
        dict with output_file, shareable_url, diagram_type, file_size_bytes.
    """
    _ensure_scripts_path()
    from langgraph_engine.diagrams.drawio_converter import DrawioConverter, get_shareable_url

    # Get analysis data
    analysis_data = _get_ast_analyzer(project_path)
    if not analysis_data.get("classes"):
        analysis_data = _get_call_graph_data(project_path)

    converter = DrawioConverter()
    xml = converter.convert(diagram_type, analysis_data)

    od = _resolve_output_dir(project_path, output_dir)
    filename = "%s-diagram.drawio" % diagram_type
    out_path = od / filename
    _save_drawio(xml, out_path)

    # Shareable URL
    github_raw_url = ""
    if github_repo:
        rel = str(out_path).replace("\\", "/")
        # Try to make relative path from project_path
        try:
            rel = str(out_path.relative_to(Path(project_path))).replace("\\", "/")
        except ValueError:
            pass
        github_raw_url = (
            "https://raw.githubusercontent.com/%s/%s/%s"
            % (github_repo, github_branch, rel)
        )

    url = get_shareable_url(xml, github_raw_url or None)

    return {
        "diagram_type": diagram_type,
        "format": "drawio",
        "output_file": str(out_path),
        "shareable_url": url,
        "file_size_bytes": len(xml.encode("utf-8")),
        "open_hint": (
            "Open in: draw.io desktop, https://app.diagrams.net, "
            "or VS Code draw.io extension"
        ),
    }


# ======================================================================
# Tool 2: generate_all_drawio
# ======================================================================

@mcp.tool()
@mcp_tool_handler
def generate_all_drawio(
    project_path: str,
    output_dir: str = "docs/drawio",
    github_repo: str = "",
    github_branch: str = "main",
) -> dict:
    """Generate ALL 12 SDLC UML diagram types as editable .drawio files.

    Analyzes the project once and produces 12 .drawio files covering the
    complete SDLC: class, sequence, activity, state, component, package,
    deployment, use case, object, communication, composite, interaction.

    Args:
        project_path: Root path of the project to analyze.
        output_dir: Output directory. Default: docs/drawio
        github_repo: Optional "owner/repo" for shareable GitHub URLs.
        github_branch: Branch for GitHub raw URL. Default: "main"

    Returns:
        dict with generated list (diagram_type, file, url per diagram),
        output_dir, and total count.
    """
    _ensure_scripts_path()
    from langgraph_engine.diagrams.drawio_converter import DrawioConverter, get_shareable_url

    DIAGRAM_TYPES = [
        "class", "sequence", "activity", "state",
        "component", "package", "deployment", "usecase",
        "object", "communication", "composite", "interaction",
    ]

    analysis_data = _get_ast_analyzer(project_path)
    if not analysis_data.get("classes"):
        analysis_data = _get_call_graph_data(project_path)

    converter = DrawioConverter()
    od = _resolve_output_dir(project_path, output_dir)

    generated = []
    failed = []

    for dtype in DIAGRAM_TYPES:
        try:
            xml = converter.convert(dtype, analysis_data)
            filename = "%s-diagram.drawio" % dtype
            out_path = od / filename
            _save_drawio(xml, out_path)

            github_raw_url = ""
            if github_repo:
                try:
                    rel = str(out_path.relative_to(Path(project_path))).replace("\\", "/")
                except ValueError:
                    rel = filename
                github_raw_url = (
                    "https://raw.githubusercontent.com/%s/%s/%s"
                    % (github_repo, github_branch, rel)
                )

            url = get_shareable_url(xml, github_raw_url or None)

            generated.append({
                "diagram_type": dtype,
                "output_file": str(out_path),
                "shareable_url": url,
                "file_size_bytes": len(xml.encode("utf-8")),
            })
        except Exception as e:
            failed.append({"diagram_type": dtype, "error": str(e)})

    return {
        "output_dir": str(od),
        "generated": generated,
        "failed": failed,
        "total_generated": len(generated),
        "total_failed": len(failed),
        "open_hint": (
            "Open any .drawio file in: draw.io desktop, "
            "https://app.diagrams.net (File > Open from URL / local), "
            "or VS Code with 'Draw.io Integration' extension."
        ),
    }


# ======================================================================
# Tool 3: get_shareable_url
# ======================================================================

@mcp.tool()
@mcp_tool_handler
def get_shareable_url(
    drawio_file_path: str,
    github_repo: str = "",
    github_branch: str = "main",
    project_path: str = "",
) -> dict:
    """Get a shareable app.diagrams.net URL for an existing .drawio file.

    Two URL modes:
        GitHub URL (recommended): If github_repo is provided and the file
            is committed, returns a ?url= link. Anyone with the link can
            view and edit the diagram.
        Encoded URL: Falls back to encoding the XML directly in the URL
            fragment (#H). Works offline but URL is very long.

    Args:
        drawio_file_path: Absolute path to the .drawio file.
        github_repo: "owner/repo" for GitHub-hosted URL. E.g. "org/repo"
        github_branch: Branch name. Default: "main"
        project_path: Project root for computing relative path.

    Returns:
        dict with shareable_url, url_type ("github" or "encoded"), file_path.
    """
    _ensure_scripts_path()
    from langgraph_engine.diagrams.drawio_converter import get_shareable_url as _get_url

    fp = Path(drawio_file_path)
    if not fp.exists():
        return {"error": "File not found: %s" % drawio_file_path}

    with open(str(fp), "r", encoding="utf-8") as f:
        xml = f.read()

    github_raw_url = ""
    url_type = "encoded"

    if github_repo:
        rel = str(fp)
        if project_path:
            try:
                rel = str(fp.relative_to(Path(project_path))).replace("\\", "/")
            except ValueError:
                rel = fp.name
        github_raw_url = (
            "https://raw.githubusercontent.com/%s/%s/%s"
            % (github_repo, github_branch, rel)
        )
        url_type = "github"

    url = _get_url(xml, github_raw_url or None)

    return {
        "shareable_url": url,
        "url_type": url_type,
        "file_path": str(fp),
        "file_size_bytes": len(xml.encode("utf-8")),
        "note": (
            "GitHub URL works best when the file is committed and pushed. "
            "Encoded URL works immediately but is longer."
        ) if url_type == "github" else (
            "Encoded URL works immediately - share with anyone."
        ),
    }


# ======================================================================
# Tool 4: list_drawio_diagrams
# ======================================================================

@mcp.tool()
@mcp_tool_handler
def list_drawio_diagrams(
    project_path: str,
    output_dir: str = "docs/drawio",
) -> dict:
    """List all existing .drawio diagram files in the output directory.

    Args:
        project_path: Root path of the project.
        output_dir: Directory to scan. Default: docs/drawio

    Returns:
        dict with files list (name, path, size_bytes, modified) and total count.
    """
    od = _resolve_output_dir(project_path, output_dir)
    files = []

    for f in sorted(od.glob("*.drawio")):
        stat = f.stat()
        files.append({
            "name": f.name,
            "path": str(f),
            "size_bytes": stat.st_size,
            "modified": str(stat.st_mtime),
        })

    return {
        "output_dir": str(od),
        "files": files,
        "total": len(files),
        "supported_types": [
            "class", "sequence", "activity", "state", "component",
            "package", "deployment", "usecase", "object",
            "communication", "composite", "interaction",
        ],
    }


# ======================================================================
# Tool 5: convert_mermaid_to_drawio
# ======================================================================

@mcp.tool()
@mcp_tool_handler
def convert_mermaid_to_drawio(
    project_path: str,
    uml_dir: str = "docs/uml",
    output_dir: str = "docs/drawio",
    github_repo: str = "",
    github_branch: str = "main",
) -> dict:
    """Re-generate .drawio files for all existing Mermaid UML .md files.

    Scans docs/uml/ for *-diagram.md files and re-generates them as .drawio
    using the same project analysis. Useful for converting an existing Mermaid
    workflow to draw.io without re-running the full pipeline.

    Note: The Mermaid text itself is not parsed - instead the project is
    re-analyzed to produce equivalent draw.io diagrams.

    Args:
        project_path: Root path of the project.
        uml_dir: Directory containing existing Mermaid .md files.
        output_dir: Output directory for .drawio files. Default: docs/drawio
        github_repo: Optional "owner/repo" for shareable URLs.
        github_branch: Branch. Default: "main"

    Returns:
        dict with converted list and summary.
    """
    _ensure_scripts_path()
    from langgraph_engine.diagrams.drawio_converter import DrawioConverter, get_shareable_url

    MERMAID_TYPE_MAP = {
        "class-diagram": "class",
        "sequence-diagram": "sequence",
        "activity-diagram": "activity",
        "state-diagram": "state",
        "component-diagram": "component",
        "package-diagram": "package",
        "deployment-diagram": "deployment",
        "use-case-diagram": "usecase",
        "object-diagram": "object",
        "communication-diagram": "communication",
        "composite-structure-diagram": "composite",
        "interaction-overview-diagram": "interaction",
        "call-graph-diagram": "class",  # repurpose call graph as class view
    }

    uml_path = Path(project_path) / uml_dir if not Path(uml_dir).is_absolute() else Path(uml_dir)
    analysis_data = _get_ast_analyzer(project_path)
    if not analysis_data.get("classes"):
        analysis_data = _get_call_graph_data(project_path)

    converter = DrawioConverter()
    od = _resolve_output_dir(project_path, output_dir)

    converted = []
    skipped = []

    for md_file in sorted(uml_path.glob("*-diagram.md")):
        stem = md_file.stem  # e.g. "class-diagram"
        dtype = MERMAID_TYPE_MAP.get(stem)
        if not dtype:
            skipped.append({"file": str(md_file), "reason": "unknown type"})
            continue

        try:
            xml = converter.convert(dtype, analysis_data)
            out_filename = stem + ".drawio"
            out_path = od / out_filename
            _save_drawio(xml, out_path)

            github_raw_url = ""
            if github_repo:
                try:
                    rel = str(out_path.relative_to(Path(project_path))).replace("\\", "/")
                except ValueError:
                    rel = out_filename
                github_raw_url = (
                    "https://raw.githubusercontent.com/%s/%s/%s"
                    % (github_repo, github_branch, rel)
                )

            url = get_shareable_url(xml, github_raw_url or None)
            converted.append({
                "source_md": str(md_file),
                "output_drawio": str(out_path),
                "diagram_type": dtype,
                "shareable_url": url,
            })
        except Exception as e:
            skipped.append({"file": str(md_file), "reason": str(e)})

    return {
        "output_dir": str(od),
        "converted": converted,
        "skipped": skipped,
        "total_converted": len(converted),
        "total_skipped": len(skipped),
    }


if __name__ == "__main__":
    mcp.run()
