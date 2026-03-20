"""
Figma MCP Server - FastMCP-based Figma REST API integration for Claude Code.

Fetches file metadata, nodes, styles, components, design tokens, layout
properties, image export URLs, and comments from the Figma REST API.

Backend: urllib.request (stdlib only, no external deps)
Transport: stdio

Tools (10):
  figma_get_file_info, figma_get_node, figma_get_styles,
  figma_get_components, figma_extract_design_tokens, figma_get_frame_layout,
  figma_export_image, figma_get_comments, figma_add_comment,
  figma_health_check

Environment Variables:
  FIGMA_ACCESS_TOKEN - Personal Access Token (required)
  FIGMA_TEAM_ID      - Team ID for team-level queries (optional)
  ENABLE_FIGMA       - Set to "1" to enable server (default "0")

Auth: Header X-Figma-Token on all requests.

Windows-Safe: ASCII only (cp1252 compatible)
"""

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional
from pathlib import Path

# Ensure src/mcp/ is in path for base package imports
sys.path.insert(0, str(Path(__file__).resolve().parent))

from mcp.server.fastmcp import FastMCP
from base.decorators import mcp_tool_handler

mcp = FastMCP(
    "figma-api",
    instructions="Figma design file operations via REST API"
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_TIMEOUT = 30  # seconds for all HTTP calls
_FIGMA_BASE_URL = "https://api.figma.com"


def _get_token() -> str:
    """Read and validate the Figma Personal Access Token from environment.

    Returns:
        Token string.

    Raises:
        EnvironmentError: If FIGMA_ACCESS_TOKEN is not set.
    """
    token = os.environ.get("FIGMA_ACCESS_TOKEN", "").strip()
    if not token:
        raise EnvironmentError(
            "Missing required environment variable: FIGMA_ACCESS_TOKEN. "
            "Set it to your Figma Personal Access Token before using figma_* tools."
        )
    return token


def _parse_file_key(file_key_or_url: str) -> str:
    """Extract a Figma file key from a URL or return it directly.

    Handles both raw file keys (e.g. ``AbCdEfGhIjKl``) and full Figma URLs
    (e.g. ``https://www.figma.com/file/AbCdEfGhIjKl/...``).

    Args:
        file_key_or_url: Raw file key or full Figma file URL.

    Returns:
        Extracted or unchanged file key string.
    """
    stripped = file_key_or_url.strip()
    if stripped.startswith("http"):
        # https://www.figma.com/file/<KEY>/Title or
        # https://www.figma.com/design/<KEY>/Title
        parts = stripped.split("/")
        for i, part in enumerate(parts):
            if part in ("file", "design") and i + 1 < len(parts):
                candidate = parts[i + 1].split("?")[0].split("#")[0]
                if candidate:
                    return candidate
    return stripped


# ---------------------------------------------------------------------------
# HTTP helper
# ---------------------------------------------------------------------------

def _make_figma_request(
    endpoint: str,
    params: Optional[Dict[str, str]] = None,
    method: str = "GET",
    body: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Execute a GET or POST request against the Figma REST API.

    Args:
        endpoint: API path starting with / (e.g. /v1/files/KEY).
        params: Optional query parameters dict for GET requests.
        method: HTTP method (GET or POST). Default GET.
        body: Optional request body dict for POST requests.

    Returns:
        Parsed JSON response dict.

    Raises:
        EnvironmentError: If FIGMA_ACCESS_TOKEN is missing.
        RuntimeError: On HTTP or network errors.
    """
    token = _get_token()

    url = _FIGMA_BASE_URL + endpoint
    if params:
        url += "?" + urllib.parse.urlencode(params)

    headers = {
        "X-Figma-Token": token,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    data: Optional[bytes] = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")

    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            raw = resp.read()
            if not raw:
                return {}
            return json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw_body = exc.read()
        try:
            err_json = json.loads(raw_body.decode("utf-8"))
            detail = err_json.get("err", "") or err_json.get("message", "") or str(exc)
        except Exception:
            detail = raw_body.decode("utf-8", errors="replace")[:500]
        raise RuntimeError(
            "Figma API error " + str(exc.code) + ": " + detail
        ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError("Figma network error: " + str(exc.reason)) from exc


# ---------------------------------------------------------------------------
# Design token extraction helpers
# ---------------------------------------------------------------------------

def _extract_tokens_from_node(node: Dict[str, Any], tokens: Dict[str, Any]) -> None:
    """Recursively extract design tokens from a Figma node tree.

    Mutates the ``tokens`` dict in-place, adding to:
      - ``tokens["colors"]``     (set of hex strings)
      - ``tokens["typography"]`` (list of style dicts)
      - ``tokens["spacing"]``    (list of padding/gap dicts)
      - ``tokens["radii"]``      (set of numeric corner-radius values)
      - ``tokens["shadows"]``    (list of drop-shadow dicts)

    Args:
        node: A single Figma node dict from the file JSON.
        tokens: Accumulator dict with the keys above.
    """
    # Colors from solid fills
    for fill in node.get("fills", []):
        if fill.get("type") == "SOLID" and fill.get("visible", True):
            c = fill.get("color", {})
            r = int(c.get("r", 0) * 255)
            g = int(c.get("g", 0) * 255)
            b = int(c.get("b", 0) * 255)
            hex_color = "#{:02x}{:02x}{:02x}".format(r, g, b)
            tokens["colors"].add(hex_color)

    # Typography from TEXT nodes
    if node.get("type") == "TEXT":
        style = node.get("style", {})
        if style.get("fontFamily"):
            tokens["typography"].append({
                "fontFamily": style.get("fontFamily"),
                "fontSize": style.get("fontSize"),
                "fontWeight": style.get("fontWeight"),
                "lineHeight": style.get("lineHeightPx"),
                "letterSpacing": style.get("letterSpacing"),
            })

    # Spacing from auto-layout frames
    if node.get("layoutMode"):
        tokens["spacing"].append({
            "paddingTop": node.get("paddingTop", 0),
            "paddingRight": node.get("paddingRight", 0),
            "paddingBottom": node.get("paddingBottom", 0),
            "paddingLeft": node.get("paddingLeft", 0),
            "gap": node.get("itemSpacing", 0),
            "direction": node.get("layoutMode"),
        })

    # Border radius
    corner = node.get("cornerRadius")
    if corner is not None:
        tokens["radii"].add(corner)
    # Also handle per-corner radii
    corners = node.get("rectangleCornerRadii")
    if corners:
        for val in corners:
            if val:
                tokens["radii"].add(val)

    # Shadows from DROP_SHADOW effects
    for effect in node.get("effects", []):
        if effect.get("type") == "DROP_SHADOW" and effect.get("visible", True):
            c = effect.get("color", {})
            tokens["shadows"].append({
                "offsetX": effect.get("offset", {}).get("x", 0),
                "offsetY": effect.get("offset", {}).get("y", 0),
                "radius": effect.get("radius", 0),
                "spread": effect.get("spread", 0),
                "color": "rgba({},{},{},{})".format(
                    int(c.get("r", 0) * 255),
                    int(c.get("g", 0) * 255),
                    int(c.get("b", 0) * 255),
                    round(c.get("a", 1), 2),
                ),
            })

    # Recurse into children
    for child in node.get("children", []):
        _extract_tokens_from_node(child, tokens)


def _deduplicate_typography(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Deduplicate typography entries by composite key of all fields.

    Args:
        items: List of typography dicts.

    Returns:
        Deduplicated list preserving first-seen order.
    """
    seen = set()
    unique = []
    for item in items:
        key = (
            item.get("fontFamily"),
            item.get("fontSize"),
            item.get("fontWeight"),
            item.get("lineHeight"),
            item.get("letterSpacing"),
        )
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def _deduplicate_spacing(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Deduplicate spacing entries by their full content.

    Args:
        items: List of spacing dicts.

    Returns:
        Deduplicated list preserving first-seen order.
    """
    seen = set()
    unique = []
    for item in items:
        key = (
            item.get("paddingTop"),
            item.get("paddingRight"),
            item.get("paddingBottom"),
            item.get("paddingLeft"),
            item.get("gap"),
            item.get("direction"),
        )
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
@mcp_tool_handler
def figma_get_file_info(file_key: str) -> dict:
    """Get Figma file metadata: name, last modified, version, and pages.

    Uses depth=1 to fetch only top-level document info without full node tree.

    Args:
        file_key: Figma file key or full Figma file URL.
    """
    key = _parse_file_key(file_key)
    data = _make_figma_request("/v1/files/" + key, params={"depth": "1"})

    document = data.get("document", {})
    pages = [
        {"name": child.get("name", ""), "id": child.get("id", "")}
        for child in document.get("children", [])
        if child.get("type") == "CANVAS"
    ]

    return {
        "file_key": key,
        "name": data.get("name", ""),
        "last_modified": data.get("lastModified", ""),
        "version": data.get("version", ""),
        "thumbnail_url": data.get("thumbnailUrl", ""),
        "pages": pages,
        "page_count": len(pages),
    }


@mcp.tool()
@mcp_tool_handler
def figma_get_node(file_key: str, node_id: str) -> dict:
    """Get details of a specific node (frame, component, group, etc.) by ID.

    Returns type, name, size, fills, strokes, effects, and a children summary.

    Args:
        file_key: Figma file key or full Figma file URL.
        node_id: Node ID string (e.g. "1:23" or "123:456").
    """
    key = _parse_file_key(file_key)
    data = _make_figma_request(
        "/v1/files/" + key + "/nodes",
        params={"ids": node_id},
    )

    nodes_map = data.get("nodes", {})
    # node_id may use ":" or "-" depending on how it was passed
    node_data = nodes_map.get(node_id) or next(iter(nodes_map.values()), {})
    node = node_data.get("document", {}) if node_data else {}

    # Build size summary
    bbox = node.get("absoluteBoundingBox") or node.get("size") or {}
    size = {
        "width": bbox.get("width") or node.get("size", {}).get("x"),
        "height": bbox.get("height") or node.get("size", {}).get("y"),
    }

    # Summarize children
    children_summary = [
        {"id": c.get("id"), "name": c.get("name"), "type": c.get("type")}
        for c in node.get("children", [])[:20]  # cap at 20
    ]

    return {
        "file_key": key,
        "node_id": node_id,
        "name": node.get("name", ""),
        "type": node.get("type", ""),
        "size": size,
        "fills": node.get("fills", []),
        "strokes": node.get("strokes", []),
        "effects": node.get("effects", []),
        "opacity": node.get("opacity", 1),
        "visible": node.get("visible", True),
        "children_count": len(node.get("children", [])),
        "children_summary": children_summary,
    }


@mcp.tool()
@mcp_tool_handler
def figma_get_styles(file_key: str) -> dict:
    """Extract all published styles from a Figma file (colors, text, effects, grids).

    Args:
        file_key: Figma file key or full Figma file URL.
    """
    key = _parse_file_key(file_key)
    data = _make_figma_request("/v1/files/" + key + "/styles")

    raw_styles = data.get("meta", {}).get("styles", [])
    styles = [
        {
            "key": s.get("key", ""),
            "name": s.get("name", ""),
            "type": s.get("style_type", ""),
            "description": s.get("description", ""),
            "node_id": s.get("node_id", ""),
        }
        for s in raw_styles
    ]

    # Group by type for convenience
    by_type: Dict[str, List[dict]] = {}
    for s in styles:
        t = s["type"]
        by_type.setdefault(t, []).append(s)

    return {
        "file_key": key,
        "total_styles": len(styles),
        "styles": styles,
        "by_type": by_type,
    }


@mcp.tool()
@mcp_tool_handler
def figma_get_components(file_key: str) -> dict:
    """List all published components and component sets in a Figma file.

    Args:
        file_key: Figma file key or full Figma file URL.
    """
    key = _parse_file_key(file_key)
    data = _make_figma_request("/v1/files/" + key + "/components")

    meta = data.get("meta", {})
    raw_components = meta.get("components", [])

    components = []
    for c in raw_components:
        components.append({
            "key": c.get("key", ""),
            "name": c.get("name", ""),
            "description": c.get("description", ""),
            "containing_frame": c.get("containing_frame", {}).get("name", ""),
            "node_id": c.get("node_id", ""),
        })

    raw_sets = meta.get("component_sets", [])
    component_sets = []
    for cs in raw_sets:
        component_sets.append({
            "key": cs.get("key", ""),
            "name": cs.get("name", ""),
            "description": cs.get("description", ""),
            "containing_frame": cs.get("containing_frame", {}).get("name", ""),
            "node_id": cs.get("node_id", ""),
        })

    return {
        "file_key": key,
        "component_count": len(components),
        "component_set_count": len(component_sets),
        "components": components,
        "component_sets": component_sets,
    }


@mcp.tool()
@mcp_tool_handler
def figma_extract_design_tokens(
    file_key: str,
    node_ids: Optional[str] = None,
) -> dict:
    """Extract design tokens from a Figma file: colors, typography, spacing, radii, shadows.

    Parses the full file node tree (or specific nodes) and returns structured
    token data organized by category. Colors and radii are deduplicated.

    Args:
        file_key: Figma file key or full Figma file URL.
        node_ids: Optional comma-separated node IDs to scope extraction.
                  If omitted, the full document tree is scanned.
    """
    key = _parse_file_key(file_key)

    tokens: Dict[str, Any] = {
        "colors": set(),
        "typography": [],
        "spacing": [],
        "radii": set(),
        "shadows": [],
    }

    if node_ids:
        # Fetch specific nodes
        ids_clean = ",".join(n.strip() for n in node_ids.split(",") if n.strip())
        data = _make_figma_request(
            "/v1/files/" + key + "/nodes",
            params={"ids": ids_clean},
        )
        for node_wrapper in data.get("nodes", {}).values():
            if node_wrapper:
                doc = node_wrapper.get("document", {})
                _extract_tokens_from_node(doc, tokens)
    else:
        # Fetch full file tree
        data = _make_figma_request("/v1/files/" + key)
        document = data.get("document", {})
        _extract_tokens_from_node(document, tokens)

    # Convert sets to sorted lists and deduplicate lists
    sorted_colors = sorted(tokens["colors"])
    unique_typography = _deduplicate_typography(tokens["typography"])
    unique_spacing = _deduplicate_spacing(tokens["spacing"])
    sorted_radii = sorted(tokens["radii"])

    return {
        "file_key": key,
        "tokens": {
            "colors": sorted_colors,
            "typography": unique_typography,
            "spacing": unique_spacing,
            "radii": sorted_radii,
            "shadows": tokens["shadows"],
        },
        "counts": {
            "colors": len(sorted_colors),
            "typography": len(unique_typography),
            "spacing": len(unique_spacing),
            "radii": len(sorted_radii),
            "shadows": len(tokens["shadows"]),
        },
    }


@mcp.tool()
@mcp_tool_handler
def figma_get_frame_layout(file_key: str, node_id: str) -> dict:
    """Get auto-layout / flexbox properties for a specific frame node.

    Returns layoutMode, padding, gap, alignment, sizing, and constraints.

    Args:
        file_key: Figma file key or full Figma file URL.
        node_id: Node ID of the frame (e.g. "1:23").
    """
    key = _parse_file_key(file_key)
    data = _make_figma_request(
        "/v1/files/" + key + "/nodes",
        params={"ids": node_id},
    )

    nodes_map = data.get("nodes", {})
    node_data = nodes_map.get(node_id) or next(iter(nodes_map.values()), {})
    node = node_data.get("document", {}) if node_data else {}

    bbox = node.get("absoluteBoundingBox") or {}

    return {
        "file_key": key,
        "node_id": node_id,
        "name": node.get("name", ""),
        "type": node.get("type", ""),
        "layout_mode": node.get("layoutMode"),
        "layout_align": node.get("layoutAlign"),
        "layout_grow": node.get("layoutGrow"),
        "primary_axis_align_items": node.get("primaryAxisAlignItems"),
        "counter_axis_align_items": node.get("counterAxisAlignItems"),
        "primary_axis_sizing_mode": node.get("primaryAxisSizingMode"),
        "counter_axis_sizing_mode": node.get("counterAxisSizingMode"),
        "padding_top": node.get("paddingTop", 0),
        "padding_right": node.get("paddingRight", 0),
        "padding_bottom": node.get("paddingBottom", 0),
        "padding_left": node.get("paddingLeft", 0),
        "item_spacing": node.get("itemSpacing", 0),
        "constraints": node.get("constraints", {}),
        "size": {
            "width": bbox.get("width"),
            "height": bbox.get("height"),
        },
        "clips_content": node.get("clipsContent"),
    }


@mcp.tool()
@mcp_tool_handler
def figma_export_image(
    file_key: str,
    node_id: str,
    format: str = "png",
    scale: int = 2,
) -> dict:
    """Export a node as a PNG or SVG and return the image URL.

    The returned URL is a temporary CDN link (expires in approximately 30 days).

    Args:
        file_key: Figma file key or full Figma file URL.
        node_id: Node ID to export (e.g. "1:23").
        format: Export format -- "png", "svg", "jpg", or "pdf". Default: "png".
        scale: Export scale factor (1-4). Default: 2.
    """
    key = _parse_file_key(file_key)
    allowed_formats = ("png", "svg", "jpg", "pdf")
    fmt = format.lower()
    if fmt not in allowed_formats:
        fmt = "png"

    scale_val = max(1, min(4, int(scale)))

    data = _make_figma_request(
        "/v1/images/" + key,
        params={
            "ids": node_id,
            "format": fmt,
            "scale": str(scale_val),
        },
    )

    err = data.get("err")
    images = data.get("images", {})
    image_url = images.get(node_id, "")

    return {
        "file_key": key,
        "node_id": node_id,
        "format": fmt,
        "scale": scale_val,
        "image_url": image_url,
        "error": err,
        "note": "URL expires in approximately 30 days",
    }


@mcp.tool()
@mcp_tool_handler
def figma_get_comments(file_key: str) -> dict:
    """Get all design review comments from a Figma file.

    Args:
        file_key: Figma file key or full Figma file URL.
    """
    key = _parse_file_key(file_key)
    data = _make_figma_request("/v1/files/" + key + "/comments")

    raw_comments = data.get("comments", [])
    comments = []
    for c in raw_comments:
        user = c.get("user", {})
        comments.append({
            "id": c.get("id", ""),
            "message": c.get("message", ""),
            "author": user.get("name", "") or user.get("handle", ""),
            "author_id": user.get("id", ""),
            "created_at": c.get("created_at", ""),
            "resolved_at": c.get("resolved_at"),
            "resolved": c.get("resolved_at") is not None,
            "parent_id": c.get("parent_id"),
            "node_id": (c.get("client_meta") or {}).get("node_id"),
        })

    resolved = [c for c in comments if c["resolved"]]
    open_comments = [c for c in comments if not c["resolved"]]

    return {
        "file_key": key,
        "total_comments": len(comments),
        "open_count": len(open_comments),
        "resolved_count": len(resolved),
        "comments": comments,
    }


@mcp.tool()
@mcp_tool_handler
def figma_add_comment(
    file_key: str,
    message: str,
    node_id: Optional[str] = None,
) -> dict:
    """Add an implementation or review comment to a Figma file.

    Args:
        file_key: Figma file key or full Figma file URL.
        message: Comment text to post.
        node_id: Optional node ID to anchor the comment to a specific frame.
    """
    key = _parse_file_key(file_key)

    body: Dict[str, Any] = {"message": message}
    if node_id:
        body["client_meta"] = {"node_id": node_id}

    data = _make_figma_request(
        "/v1/files/" + key + "/comments",
        method="POST",
        body=body,
    )

    return {
        "file_key": key,
        "comment_id": data.get("id", ""),
        "message": data.get("message", message),
        "created_at": data.get("created_at", ""),
        "node_id": node_id,
    }


@mcp.tool()
@mcp_tool_handler
def figma_health_check() -> dict:
    """Verify Figma API connectivity and token validity.

    Calls GET /v1/me to confirm the token works and returns the current user.
    """
    data = _make_figma_request("/v1/me")

    user_id = data.get("id", "")
    name = data.get("handle", "") or data.get("name", "")
    email = data.get("email", "")
    img = data.get("img_url", "")

    connected = bool(user_id)
    team_id = os.environ.get("FIGMA_TEAM_ID", "")

    return {
        "connected": connected,
        "user_id": user_id,
        "name": name,
        "email": email,
        "img_url": img,
        "team_id_configured": bool(team_id),
        "team_id": team_id,
        "enable_figma": os.environ.get("ENABLE_FIGMA", "0"),
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run(transport="stdio")
