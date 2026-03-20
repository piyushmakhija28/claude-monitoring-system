"""
Tests for figma_mcp_server.py

Coverage:
  - All 10 tool functions
  - _parse_file_key: URL extraction and direct key pass-through
  - _get_token: missing token detection
  - _make_figma_request: GET, POST, HTTP errors (401, 404, 429), network errors
  - _extract_tokens_from_node: colors, typography, spacing, radii, shadows, recursion
  - _deduplicate_typography and _deduplicate_spacing helpers
  - figma_get_file_info: pages extraction
  - figma_get_node: size, children summary, fill/stroke/effect passthrough
  - figma_get_styles: grouping by type
  - figma_get_components: components and component_sets
  - figma_extract_design_tokens: full tree and node-scoped extraction
  - figma_get_frame_layout: layout mode, padding, alignment fields
  - figma_export_image: format validation, scale clamping, URL extraction
  - figma_get_comments: resolved/open split, node anchor
  - figma_add_comment: body construction with and without node_id
  - figma_health_check: connected/disconnected states

Windows-Safe: ASCII only (cp1252 compatible)
"""

import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, call, patch
import urllib.error

# Add src/mcp to path so imports resolve correctly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src" / "mcp"))

import figma_mcp_server as figma


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

def _env(extra: dict | None = None) -> dict:
    """Return a minimal env dict with a valid token."""
    base = {
        "FIGMA_ACCESS_TOKEN": "figd_test-secret-token",
        "ENABLE_FIGMA": "1",
    }
    if extra:
        base.update(extra)
    return base


def _fake_response(data: dict | list, status: int = 200) -> MagicMock:
    """Build a fake urllib response with .read() returning JSON bytes."""
    body = json.dumps(data).encode("utf-8")
    mock_resp = MagicMock()
    mock_resp.read.return_value = body
    mock_resp.status = status
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


def _parse(result: str) -> dict:
    """Parse JSON string returned by a decorated tool function."""
    return json.loads(result)


def _http_error(code: int, message: str = "error") -> urllib.error.HTTPError:
    """Build a fake HTTPError with a JSON body."""
    import io
    body_bytes = json.dumps({"err": message}).encode("utf-8")
    resp = io.BytesIO(body_bytes)
    err = urllib.error.HTTPError(
        url="https://api.figma.com/v1/test",
        code=code,
        msg=message,
        hdrs={},
        fp=resp,
    )
    return err


# ---------------------------------------------------------------------------
# _parse_file_key
# ---------------------------------------------------------------------------

class TestParseFileKey(unittest.TestCase):

    def test_raw_key_returned_unchanged(self):
        self.assertEqual(figma._parse_file_key("AbCdEfGhIjKl"), "AbCdEfGhIjKl")

    def test_figma_file_url(self):
        url = "https://www.figma.com/file/AbCdEfGhIjKl/My-Design"
        self.assertEqual(figma._parse_file_key(url), "AbCdEfGhIjKl")

    def test_figma_design_url(self):
        url = "https://www.figma.com/design/XyZkEy123456/Component-Library"
        self.assertEqual(figma._parse_file_key(url), "XyZkEy123456")

    def test_figma_url_with_query_params(self):
        url = "https://www.figma.com/file/Key99?node-id=1%3A2"
        self.assertEqual(figma._parse_file_key(url), "Key99")

    def test_strips_whitespace(self):
        self.assertEqual(figma._parse_file_key("  KeyABC  "), "KeyABC")


# ---------------------------------------------------------------------------
# _get_token
# ---------------------------------------------------------------------------

class TestGetToken(unittest.TestCase):

    def test_returns_token_when_set(self):
        with patch.dict(os.environ, _env(), clear=True):
            token = figma._get_token()
        self.assertEqual(token, "figd_test-secret-token")

    def test_raises_when_token_missing(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(EnvironmentError) as ctx:
                figma._get_token()
        self.assertIn("FIGMA_ACCESS_TOKEN", str(ctx.exception))

    def test_raises_when_token_empty_string(self):
        with patch.dict(os.environ, {"FIGMA_ACCESS_TOKEN": "  "}, clear=True):
            with self.assertRaises(EnvironmentError):
                figma._get_token()


# ---------------------------------------------------------------------------
# _make_figma_request
# ---------------------------------------------------------------------------

class TestMakeFigmaRequest(unittest.TestCase):

    def test_get_request_sets_x_figma_token_header(self):
        fake_resp = _fake_response({"ok": True})
        with patch.dict(os.environ, _env(), clear=True):
            with patch("urllib.request.urlopen", return_value=fake_resp) as mock_open:
                figma._make_figma_request("/v1/me")
        req_obj = mock_open.call_args[0][0]
        self.assertEqual(req_obj.get_header("X-figma-token"), "figd_test-secret-token")

    def test_get_request_appends_query_params(self):
        fake_resp = _fake_response({})
        with patch.dict(os.environ, _env(), clear=True):
            with patch("urllib.request.urlopen", return_value=fake_resp) as mock_open:
                figma._make_figma_request("/v1/files/KEY", params={"depth": "1"})
        req_url = mock_open.call_args[0][0].full_url
        self.assertIn("depth=1", req_url)
        self.assertIn("api.figma.com", req_url)

    def test_post_request_sends_json_body(self):
        fake_resp = _fake_response({"id": "123"})
        with patch.dict(os.environ, _env(), clear=True):
            with patch("urllib.request.urlopen", return_value=fake_resp) as mock_open:
                figma._make_figma_request(
                    "/v1/files/KEY/comments",
                    method="POST",
                    body={"message": "hello"},
                )
        req_obj = mock_open.call_args[0][0]
        self.assertEqual(req_obj.get_method(), "POST")
        sent_body = json.loads(req_obj.data.decode("utf-8"))
        self.assertEqual(sent_body["message"], "hello")

    def test_returns_empty_dict_for_empty_body(self):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b""
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        with patch.dict(os.environ, _env(), clear=True):
            with patch("urllib.request.urlopen", return_value=mock_resp):
                result = figma._make_figma_request("/v1/me")
        self.assertEqual(result, {})

    def test_http_401_raises_runtime_error(self):
        with patch.dict(os.environ, _env(), clear=True):
            with patch("urllib.request.urlopen", side_effect=_http_error(401, "Unauthorized")):
                with self.assertRaises(RuntimeError) as ctx:
                    figma._make_figma_request("/v1/me")
        self.assertIn("401", str(ctx.exception))

    def test_http_404_raises_runtime_error(self):
        with patch.dict(os.environ, _env(), clear=True):
            with patch("urllib.request.urlopen", side_effect=_http_error(404, "Not Found")):
                with self.assertRaises(RuntimeError) as ctx:
                    figma._make_figma_request("/v1/files/BADKEY")
        self.assertIn("404", str(ctx.exception))

    def test_http_429_raises_runtime_error(self):
        with patch.dict(os.environ, _env(), clear=True):
            with patch("urllib.request.urlopen", side_effect=_http_error(429, "Rate limited")):
                with self.assertRaises(RuntimeError) as ctx:
                    figma._make_figma_request("/v1/files/KEY")
        self.assertIn("429", str(ctx.exception))

    def test_network_error_raises_runtime_error(self):
        import urllib.error as ue
        with patch.dict(os.environ, _env(), clear=True):
            with patch("urllib.request.urlopen", side_effect=ue.URLError("connection refused")):
                with self.assertRaises(RuntimeError) as ctx:
                    figma._make_figma_request("/v1/me")
        self.assertIn("network error", str(ctx.exception).lower())


# ---------------------------------------------------------------------------
# Design token extraction helpers
# ---------------------------------------------------------------------------

class TestExtractTokensFromNode(unittest.TestCase):

    def _fresh_tokens(self) -> dict:
        return {
            "colors": set(),
            "typography": [],
            "spacing": [],
            "radii": set(),
            "shadows": [],
        }

    def test_extracts_solid_fill_color(self):
        node = {
            "fills": [{"type": "SOLID", "visible": True, "color": {"r": 1.0, "g": 0.0, "b": 0.0}}],
            "children": [],
        }
        tokens = self._fresh_tokens()
        figma._extract_tokens_from_node(node, tokens)
        self.assertIn("#ff0000", tokens["colors"])

    def test_skips_non_solid_fill(self):
        node = {
            "fills": [{"type": "GRADIENT_LINEAR", "visible": True, "color": {"r": 1.0, "g": 0.0, "b": 0.0}}],
            "children": [],
        }
        tokens = self._fresh_tokens()
        figma._extract_tokens_from_node(node, tokens)
        self.assertEqual(len(tokens["colors"]), 0)

    def test_skips_invisible_fill(self):
        node = {
            "fills": [{"type": "SOLID", "visible": False, "color": {"r": 1.0, "g": 0.0, "b": 0.0}}],
            "children": [],
        }
        tokens = self._fresh_tokens()
        figma._extract_tokens_from_node(node, tokens)
        self.assertEqual(len(tokens["colors"]), 0)

    def test_extracts_typography_from_text_node(self):
        node = {
            "type": "TEXT",
            "style": {
                "fontFamily": "Inter",
                "fontSize": 16,
                "fontWeight": 400,
                "lineHeightPx": 24.0,
                "letterSpacing": 0,
            },
            "fills": [],
            "children": [],
        }
        tokens = self._fresh_tokens()
        figma._extract_tokens_from_node(node, tokens)
        self.assertEqual(len(tokens["typography"]), 1)
        self.assertEqual(tokens["typography"][0]["fontFamily"], "Inter")
        self.assertEqual(tokens["typography"][0]["fontSize"], 16)

    def test_skips_typography_when_no_font_family(self):
        node = {"type": "TEXT", "style": {}, "fills": [], "children": []}
        tokens = self._fresh_tokens()
        figma._extract_tokens_from_node(node, tokens)
        self.assertEqual(len(tokens["typography"]), 0)

    def test_extracts_spacing_from_auto_layout_node(self):
        node = {
            "layoutMode": "HORIZONTAL",
            "paddingTop": 8,
            "paddingRight": 16,
            "paddingBottom": 8,
            "paddingLeft": 16,
            "itemSpacing": 12,
            "fills": [],
            "children": [],
        }
        tokens = self._fresh_tokens()
        figma._extract_tokens_from_node(node, tokens)
        self.assertEqual(len(tokens["spacing"]), 1)
        sp = tokens["spacing"][0]
        self.assertEqual(sp["paddingTop"], 8)
        self.assertEqual(sp["gap"], 12)
        self.assertEqual(sp["direction"], "HORIZONTAL")

    def test_no_spacing_without_layout_mode(self):
        node = {"paddingTop": 8, "fills": [], "children": []}
        tokens = self._fresh_tokens()
        figma._extract_tokens_from_node(node, tokens)
        self.assertEqual(len(tokens["spacing"]), 0)

    def test_extracts_corner_radius(self):
        node = {"cornerRadius": 8, "fills": [], "children": []}
        tokens = self._fresh_tokens()
        figma._extract_tokens_from_node(node, tokens)
        self.assertIn(8, tokens["radii"])

    def test_extracts_rectangle_corner_radii(self):
        node = {"rectangleCornerRadii": [4, 8, 4, 8], "fills": [], "children": []}
        tokens = self._fresh_tokens()
        figma._extract_tokens_from_node(node, tokens)
        self.assertIn(4, tokens["radii"])
        self.assertIn(8, tokens["radii"])

    def test_extracts_drop_shadow_effect(self):
        node = {
            "effects": [{
                "type": "DROP_SHADOW",
                "visible": True,
                "offset": {"x": 0, "y": 2},
                "radius": 4,
                "spread": 0,
                "color": {"r": 0.0, "g": 0.0, "b": 0.0, "a": 0.25},
            }],
            "fills": [],
            "children": [],
        }
        tokens = self._fresh_tokens()
        figma._extract_tokens_from_node(node, tokens)
        self.assertEqual(len(tokens["shadows"]), 1)
        shadow = tokens["shadows"][0]
        self.assertEqual(shadow["offsetY"], 2)
        self.assertEqual(shadow["radius"], 4)
        self.assertIn("rgba(0,0,0,0.25)", shadow["color"])

    def test_skips_invisible_shadow(self):
        node = {
            "effects": [{
                "type": "DROP_SHADOW",
                "visible": False,
                "offset": {"x": 0, "y": 2},
                "radius": 4,
                "spread": 0,
                "color": {"r": 0.0, "g": 0.0, "b": 0.0, "a": 0.25},
            }],
            "fills": [],
            "children": [],
        }
        tokens = self._fresh_tokens()
        figma._extract_tokens_from_node(node, tokens)
        self.assertEqual(len(tokens["shadows"]), 0)

    def test_recursion_collects_from_children(self):
        node = {
            "fills": [],
            "children": [
                {
                    "type": "TEXT",
                    "style": {"fontFamily": "Roboto", "fontSize": 14, "fontWeight": 400},
                    "fills": [{"type": "SOLID", "visible": True, "color": {"r": 0.0, "g": 0.0, "b": 0.0}}],
                    "children": [],
                }
            ],
        }
        tokens = self._fresh_tokens()
        figma._extract_tokens_from_node(node, tokens)
        self.assertIn("#000000", tokens["colors"])
        self.assertEqual(len(tokens["typography"]), 1)

    def test_deep_recursion_three_levels(self):
        node = {
            "fills": [],
            "children": [
                {
                    "fills": [],
                    "children": [
                        {
                            "fills": [{"type": "SOLID", "visible": True, "color": {"r": 0.0, "g": 1.0, "b": 0.0}}],
                            "children": [],
                        }
                    ],
                }
            ],
        }
        tokens = self._fresh_tokens()
        figma._extract_tokens_from_node(node, tokens)
        self.assertIn("#00ff00", tokens["colors"])


class TestDeduplicateHelpers(unittest.TestCase):

    def test_deduplicate_typography_removes_duplicates(self):
        items = [
            {"fontFamily": "Inter", "fontSize": 16, "fontWeight": 400, "lineHeight": 24, "letterSpacing": 0},
            {"fontFamily": "Inter", "fontSize": 16, "fontWeight": 400, "lineHeight": 24, "letterSpacing": 0},
            {"fontFamily": "Inter", "fontSize": 24, "fontWeight": 700, "lineHeight": 32, "letterSpacing": 0},
        ]
        result = figma._deduplicate_typography(items)
        self.assertEqual(len(result), 2)

    def test_deduplicate_typography_preserves_order(self):
        items = [
            {"fontFamily": "A", "fontSize": 12, "fontWeight": 400, "lineHeight": 18, "letterSpacing": 0},
            {"fontFamily": "B", "fontSize": 14, "fontWeight": 400, "lineHeight": 20, "letterSpacing": 0},
        ]
        result = figma._deduplicate_typography(items)
        self.assertEqual(result[0]["fontFamily"], "A")
        self.assertEqual(result[1]["fontFamily"], "B")

    def test_deduplicate_spacing_removes_duplicates(self):
        items = [
            {"paddingTop": 8, "paddingRight": 16, "paddingBottom": 8, "paddingLeft": 16, "gap": 12, "direction": "HORIZONTAL"},
            {"paddingTop": 8, "paddingRight": 16, "paddingBottom": 8, "paddingLeft": 16, "gap": 12, "direction": "HORIZONTAL"},
            {"paddingTop": 4, "paddingRight": 8, "paddingBottom": 4, "paddingLeft": 8, "gap": 8, "direction": "VERTICAL"},
        ]
        result = figma._deduplicate_spacing(items)
        self.assertEqual(len(result), 2)


# ---------------------------------------------------------------------------
# figma_get_file_info
# ---------------------------------------------------------------------------

class TestFigmaGetFileInfo(unittest.TestCase):

    def test_returns_file_metadata_and_pages(self):
        fake_data = {
            "name": "Design System",
            "lastModified": "2026-03-15T10:00:00Z",
            "version": "42",
            "thumbnailUrl": "https://cdn.figma.com/thumb.png",
            "document": {
                "children": [
                    {"type": "CANVAS", "name": "Page 1", "id": "0:1"},
                    {"type": "CANVAS", "name": "Components", "id": "0:2"},
                ]
            },
        }
        with patch.dict(os.environ, _env(), clear=True):
            with patch("figma_mcp_server._make_figma_request", return_value=fake_data):
                result = _parse(figma.figma_get_file_info("AbCdEfGh"))

        self.assertTrue(result["success"])
        self.assertEqual(result["name"], "Design System")
        self.assertEqual(result["version"], "42")
        self.assertEqual(result["page_count"], 2)
        self.assertEqual(result["pages"][0]["name"], "Page 1")
        self.assertEqual(result["pages"][1]["id"], "0:2")

    def test_parses_figma_url_as_file_key(self):
        with patch.dict(os.environ, _env(), clear=True):
            with patch("figma_mcp_server._make_figma_request", return_value={"name": "X", "document": {"children": []}}) as mock_req:
                figma.figma_get_file_info("https://www.figma.com/file/KEY123/Title")
        args = mock_req.call_args[0]
        self.assertIn("KEY123", args[0])

    def test_missing_token_returns_error_response(self):
        with patch.dict(os.environ, {}, clear=True):
            result = _parse(figma.figma_get_file_info("KEY"))
        self.assertFalse(result["success"])
        self.assertIn("FIGMA_ACCESS_TOKEN", result["error"])


# ---------------------------------------------------------------------------
# figma_get_node
# ---------------------------------------------------------------------------

class TestFigmaGetNode(unittest.TestCase):

    def test_returns_node_properties(self):
        node_doc = {
            "name": "Hero Frame",
            "type": "FRAME",
            "absoluteBoundingBox": {"width": 1440, "height": 900},
            "fills": [{"type": "SOLID"}],
            "strokes": [],
            "effects": [],
            "opacity": 1,
            "visible": True,
            "children": [
                {"id": "1:2", "name": "Title", "type": "TEXT"},
                {"id": "1:3", "name": "Subtitle", "type": "TEXT"},
            ],
        }
        fake_data = {"nodes": {"1:1": {"document": node_doc}}}
        with patch.dict(os.environ, _env(), clear=True):
            with patch("figma_mcp_server._make_figma_request", return_value=fake_data):
                result = _parse(figma.figma_get_node("KEY", "1:1"))

        self.assertTrue(result["success"])
        self.assertEqual(result["name"], "Hero Frame")
        self.assertEqual(result["type"], "FRAME")
        self.assertEqual(result["size"]["width"], 1440)
        self.assertEqual(result["children_count"], 2)
        self.assertEqual(result["children_summary"][0]["name"], "Title")

    def test_empty_nodes_returns_partial_result(self):
        fake_data = {"nodes": {}}
        with patch.dict(os.environ, _env(), clear=True):
            with patch("figma_mcp_server._make_figma_request", return_value=fake_data):
                result = _parse(figma.figma_get_node("KEY", "9:9"))
        self.assertTrue(result["success"])
        self.assertEqual(result["name"], "")


# ---------------------------------------------------------------------------
# figma_get_styles
# ---------------------------------------------------------------------------

class TestFigmaGetStyles(unittest.TestCase):

    def test_returns_styles_grouped_by_type(self):
        fake_data = {
            "meta": {
                "styles": [
                    {"key": "s1", "name": "Primary", "style_type": "FILL", "description": "", "node_id": "1:1"},
                    {"key": "s2", "name": "Heading 1", "style_type": "TEXT", "description": "H1", "node_id": "1:2"},
                    {"key": "s3", "name": "Card Shadow", "style_type": "EFFECT", "description": "", "node_id": "1:3"},
                    {"key": "s4", "name": "Secondary", "style_type": "FILL", "description": "", "node_id": "1:4"},
                ]
            }
        }
        with patch.dict(os.environ, _env(), clear=True):
            with patch("figma_mcp_server._make_figma_request", return_value=fake_data):
                result = _parse(figma.figma_get_styles("KEY"))

        self.assertTrue(result["success"])
        self.assertEqual(result["total_styles"], 4)
        self.assertEqual(len(result["by_type"]["FILL"]), 2)
        self.assertEqual(len(result["by_type"]["TEXT"]), 1)
        self.assertEqual(len(result["by_type"]["EFFECT"]), 1)


# ---------------------------------------------------------------------------
# figma_get_components
# ---------------------------------------------------------------------------

class TestFigmaGetComponents(unittest.TestCase):

    def test_returns_components_and_sets(self):
        fake_data = {
            "meta": {
                "components": [
                    {"key": "c1", "name": "Button/Primary", "description": "Primary CTA", "containing_frame": {"name": "Buttons"}, "node_id": "2:1"},
                    {"key": "c2", "name": "Icon/Arrow", "description": "", "containing_frame": {"name": "Icons"}, "node_id": "2:2"},
                ],
                "component_sets": [
                    {"key": "cs1", "name": "Button", "description": "All button variants", "containing_frame": {"name": "Buttons"}, "node_id": "3:1"},
                ],
            }
        }
        with patch.dict(os.environ, _env(), clear=True):
            with patch("figma_mcp_server._make_figma_request", return_value=fake_data):
                result = _parse(figma.figma_get_components("KEY"))

        self.assertTrue(result["success"])
        self.assertEqual(result["component_count"], 2)
        self.assertEqual(result["component_set_count"], 1)
        self.assertEqual(result["components"][0]["name"], "Button/Primary")
        self.assertEqual(result["components"][0]["containing_frame"], "Buttons")
        self.assertEqual(result["component_sets"][0]["name"], "Button")


# ---------------------------------------------------------------------------
# figma_extract_design_tokens
# ---------------------------------------------------------------------------

class TestFigmaExtractDesignTokens(unittest.TestCase):

    def _build_full_file(self) -> dict:
        return {
            "document": {
                "type": "DOCUMENT",
                "fills": [],
                "children": [
                    {
                        "type": "CANVAS",
                        "fills": [],
                        "children": [
                            {
                                "type": "FRAME",
                                "layoutMode": "VERTICAL",
                                "paddingTop": 16,
                                "paddingRight": 24,
                                "paddingBottom": 16,
                                "paddingLeft": 24,
                                "itemSpacing": 8,
                                "cornerRadius": 4,
                                "fills": [{"type": "SOLID", "visible": True, "color": {"r": 0.9, "g": 0.9, "b": 0.9}}],
                                "effects": [
                                    {
                                        "type": "DROP_SHADOW",
                                        "visible": True,
                                        "offset": {"x": 0, "y": 4},
                                        "radius": 8,
                                        "spread": 0,
                                        "color": {"r": 0.0, "g": 0.0, "b": 0.0, "a": 0.1},
                                    }
                                ],
                                "children": [
                                    {
                                        "type": "TEXT",
                                        "style": {
                                            "fontFamily": "Inter",
                                            "fontSize": 16,
                                            "fontWeight": 400,
                                            "lineHeightPx": 24.0,
                                            "letterSpacing": 0,
                                        },
                                        "fills": [{"type": "SOLID", "visible": True, "color": {"r": 0.1, "g": 0.1, "b": 0.1}}],
                                        "children": [],
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
        }

    def test_extracts_all_token_categories_from_full_file(self):
        fake_data = self._build_full_file()
        with patch.dict(os.environ, _env(), clear=True):
            with patch("figma_mcp_server._make_figma_request", return_value=fake_data):
                result = _parse(figma.figma_extract_design_tokens("KEY"))

        self.assertTrue(result["success"])
        tokens = result["tokens"]
        self.assertGreater(len(tokens["colors"]), 0)
        self.assertGreater(len(tokens["typography"]), 0)
        self.assertGreater(len(tokens["spacing"]), 0)
        self.assertGreater(len(tokens["radii"]), 0)
        self.assertGreater(len(tokens["shadows"]), 0)

    def test_colors_are_sorted(self):
        fake_data = self._build_full_file()
        with patch.dict(os.environ, _env(), clear=True):
            with patch("figma_mcp_server._make_figma_request", return_value=fake_data):
                result = _parse(figma.figma_extract_design_tokens("KEY"))
        colors = result["tokens"]["colors"]
        self.assertEqual(colors, sorted(colors))

    def test_radii_are_sorted(self):
        fake_data = self._build_full_file()
        with patch.dict(os.environ, _env(), clear=True):
            with patch("figma_mcp_server._make_figma_request", return_value=fake_data):
                result = _parse(figma.figma_extract_design_tokens("KEY"))
        radii = result["tokens"]["radii"]
        self.assertEqual(radii, sorted(radii))

    def test_scoped_extraction_calls_nodes_endpoint(self):
        fake_nodes_data = {
            "nodes": {
                "1:1": {
                    "document": {
                        "fills": [{"type": "SOLID", "visible": True, "color": {"r": 1.0, "g": 0.5, "b": 0.0}}],
                        "children": [],
                    }
                }
            }
        }
        with patch.dict(os.environ, _env(), clear=True):
            with patch("figma_mcp_server._make_figma_request", return_value=fake_nodes_data) as mock_req:
                result = _parse(figma.figma_extract_design_tokens("KEY", node_ids="1:1"))

        call_endpoint = mock_req.call_args[0][0]
        self.assertIn("nodes", call_endpoint)
        self.assertTrue(result["success"])
        # int(0.5 * 255) = 127 = 0x7f, so green channel is 7f not 80
        self.assertIn("#ff7f00", result["tokens"]["colors"])

    def test_counts_match_token_list_lengths(self):
        fake_data = self._build_full_file()
        with patch.dict(os.environ, _env(), clear=True):
            with patch("figma_mcp_server._make_figma_request", return_value=fake_data):
                result = _parse(figma.figma_extract_design_tokens("KEY"))
        counts = result["counts"]
        tokens = result["tokens"]
        self.assertEqual(counts["colors"], len(tokens["colors"]))
        self.assertEqual(counts["typography"], len(tokens["typography"]))
        self.assertEqual(counts["spacing"], len(tokens["spacing"]))
        self.assertEqual(counts["radii"], len(tokens["radii"]))
        self.assertEqual(counts["shadows"], len(tokens["shadows"]))


# ---------------------------------------------------------------------------
# figma_get_frame_layout
# ---------------------------------------------------------------------------

class TestFigmaGetFrameLayout(unittest.TestCase):

    def test_returns_layout_properties(self):
        node_doc = {
            "name": "Card",
            "type": "FRAME",
            "layoutMode": "VERTICAL",
            "primaryAxisAlignItems": "MIN",
            "counterAxisAlignItems": "STRETCH",
            "primaryAxisSizingMode": "AUTO",
            "counterAxisSizingMode": "FIXED",
            "paddingTop": 16,
            "paddingRight": 24,
            "paddingBottom": 16,
            "paddingLeft": 24,
            "itemSpacing": 12,
            "clipsContent": True,
            "absoluteBoundingBox": {"width": 320, "height": 480},
            "constraints": {"horizontal": "LEFT", "vertical": "TOP"},
        }
        fake_data = {"nodes": {"2:5": {"document": node_doc}}}
        with patch.dict(os.environ, _env(), clear=True):
            with patch("figma_mcp_server._make_figma_request", return_value=fake_data):
                result = _parse(figma.figma_get_frame_layout("KEY", "2:5"))

        self.assertTrue(result["success"])
        self.assertEqual(result["layout_mode"], "VERTICAL")
        self.assertEqual(result["padding_top"], 16)
        self.assertEqual(result["padding_right"], 24)
        self.assertEqual(result["item_spacing"], 12)
        self.assertEqual(result["size"]["width"], 320)
        self.assertTrue(result["clips_content"])


# ---------------------------------------------------------------------------
# figma_export_image
# ---------------------------------------------------------------------------

class TestFigmaExportImage(unittest.TestCase):

    def test_returns_image_url(self):
        fake_data = {
            "err": None,
            "images": {"1:10": "https://cdn.figma.com/images/abc123.png"},
        }
        with patch.dict(os.environ, _env(), clear=True):
            with patch("figma_mcp_server._make_figma_request", return_value=fake_data):
                result = _parse(figma.figma_export_image("KEY", "1:10"))

        self.assertTrue(result["success"])
        self.assertEqual(result["image_url"], "https://cdn.figma.com/images/abc123.png")
        self.assertEqual(result["format"], "png")
        self.assertEqual(result["scale"], 2)

    def test_custom_format_and_scale(self):
        fake_data = {"err": None, "images": {"1:10": "https://cdn.figma.com/x.svg"}}
        with patch.dict(os.environ, _env(), clear=True):
            with patch("figma_mcp_server._make_figma_request", return_value=fake_data) as mock_req:
                result = _parse(figma.figma_export_image("KEY", "1:10", format="svg", scale=1))
        params = mock_req.call_args[1]["params"]
        self.assertEqual(params["format"], "svg")
        self.assertEqual(params["scale"], "1")

    def test_invalid_format_falls_back_to_png(self):
        fake_data = {"err": None, "images": {"1:10": "https://cdn.figma.com/x.png"}}
        with patch.dict(os.environ, _env(), clear=True):
            with patch("figma_mcp_server._make_figma_request", return_value=fake_data) as mock_req:
                figma.figma_export_image("KEY", "1:10", format="webp")
        params = mock_req.call_args[1]["params"]
        self.assertEqual(params["format"], "png")

    def test_scale_clamped_to_max_4(self):
        fake_data = {"err": None, "images": {"1:10": "url"}}
        with patch.dict(os.environ, _env(), clear=True):
            with patch("figma_mcp_server._make_figma_request", return_value=fake_data) as mock_req:
                result = _parse(figma.figma_export_image("KEY", "1:10", scale=10))
        params = mock_req.call_args[1]["params"]
        self.assertEqual(params["scale"], "4")

    def test_scale_clamped_to_min_1(self):
        fake_data = {"err": None, "images": {"1:10": "url"}}
        with patch.dict(os.environ, _env(), clear=True):
            with patch("figma_mcp_server._make_figma_request", return_value=fake_data) as mock_req:
                figma.figma_export_image("KEY", "1:10", scale=0)
        params = mock_req.call_args[1]["params"]
        self.assertEqual(params["scale"], "1")


# ---------------------------------------------------------------------------
# figma_get_comments
# ---------------------------------------------------------------------------

class TestFigmaGetComments(unittest.TestCase):

    def test_returns_split_open_and_resolved_comments(self):
        fake_data = {
            "comments": [
                {
                    "id": "c1",
                    "message": "Looks good",
                    "user": {"name": "Alice", "id": "u1"},
                    "created_at": "2026-01-01T10:00:00Z",
                    "resolved_at": None,
                    "client_meta": {"node_id": "1:5"},
                },
                {
                    "id": "c2",
                    "message": "Fix padding",
                    "user": {"name": "Bob", "id": "u2"},
                    "created_at": "2026-01-02T09:00:00Z",
                    "resolved_at": "2026-01-03T08:00:00Z",
                    "client_meta": None,
                },
            ]
        }
        with patch.dict(os.environ, _env(), clear=True):
            with patch("figma_mcp_server._make_figma_request", return_value=fake_data):
                result = _parse(figma.figma_get_comments("KEY"))

        self.assertTrue(result["success"])
        self.assertEqual(result["total_comments"], 2)
        self.assertEqual(result["open_count"], 1)
        self.assertEqual(result["resolved_count"], 1)
        self.assertEqual(result["comments"][0]["author"], "Alice")
        self.assertFalse(result["comments"][0]["resolved"])
        self.assertTrue(result["comments"][1]["resolved"])
        self.assertEqual(result["comments"][0]["node_id"], "1:5")

    def test_empty_comments(self):
        with patch.dict(os.environ, _env(), clear=True):
            with patch("figma_mcp_server._make_figma_request", return_value={"comments": []}):
                result = _parse(figma.figma_get_comments("KEY"))
        self.assertEqual(result["total_comments"], 0)
        self.assertEqual(result["open_count"], 0)


# ---------------------------------------------------------------------------
# figma_add_comment
# ---------------------------------------------------------------------------

class TestFigmaAddComment(unittest.TestCase):

    def test_adds_comment_without_node(self):
        fake_data = {
            "id": "c99",
            "message": "Approved",
            "created_at": "2026-03-20T10:00:00Z",
        }
        with patch.dict(os.environ, _env(), clear=True):
            with patch("figma_mcp_server._make_figma_request", return_value=fake_data) as mock_req:
                result = _parse(figma.figma_add_comment("KEY", "Approved"))

        self.assertTrue(result["success"])
        self.assertEqual(result["comment_id"], "c99")
        self.assertIsNone(result["node_id"])
        # Verify no client_meta in body
        body = mock_req.call_args[1]["body"]
        self.assertNotIn("client_meta", body)

    def test_adds_comment_with_node_id(self):
        fake_data = {"id": "c100", "message": "OK", "created_at": "2026-03-20T11:00:00Z"}
        with patch.dict(os.environ, _env(), clear=True):
            with patch("figma_mcp_server._make_figma_request", return_value=fake_data) as mock_req:
                result = _parse(figma.figma_add_comment("KEY", "OK", node_id="3:7"))

        body = mock_req.call_args[1]["body"]
        self.assertEqual(body["client_meta"]["node_id"], "3:7")
        self.assertEqual(result["node_id"], "3:7")

    def test_uses_post_method(self):
        fake_data = {"id": "c1", "message": "hi", "created_at": "2026-03-20T00:00:00Z"}
        with patch.dict(os.environ, _env(), clear=True):
            with patch("figma_mcp_server._make_figma_request", return_value=fake_data) as mock_req:
                figma.figma_add_comment("KEY", "hi")
        method = mock_req.call_args[1]["method"]
        self.assertEqual(method, "POST")


# ---------------------------------------------------------------------------
# figma_health_check
# ---------------------------------------------------------------------------

class TestFigmaHealthCheck(unittest.TestCase):

    def test_connected_when_user_id_present(self):
        fake_data = {
            "id": "u123",
            "handle": "alice",
            "email": "alice@example.com",
            "img_url": "https://cdn.figma.com/profile/alice.jpg",
        }
        with patch.dict(os.environ, _env({"FIGMA_TEAM_ID": "team-42"}), clear=True):
            with patch("figma_mcp_server._make_figma_request", return_value=fake_data):
                result = _parse(figma.figma_health_check())

        self.assertTrue(result["success"])
        self.assertTrue(result["connected"])
        self.assertEqual(result["name"], "alice")
        self.assertEqual(result["email"], "alice@example.com")
        self.assertEqual(result["team_id"], "team-42")
        self.assertTrue(result["team_id_configured"])

    def test_not_connected_when_no_user_id(self):
        with patch.dict(os.environ, _env(), clear=True):
            with patch("figma_mcp_server._make_figma_request", return_value={}):
                result = _parse(figma.figma_health_check())
        self.assertFalse(result["connected"])

    def test_missing_token_returns_error(self):
        with patch.dict(os.environ, {}, clear=True):
            result = _parse(figma.figma_health_check())
        self.assertFalse(result["success"])
        self.assertIn("FIGMA_ACCESS_TOKEN", result["error"])

    def test_api_error_returns_error_response(self):
        with patch.dict(os.environ, _env(), clear=True):
            with patch("figma_mcp_server._make_figma_request", side_effect=RuntimeError("Figma API error 401: Unauthorized")):
                result = _parse(figma.figma_health_check())
        self.assertFalse(result["success"])
        self.assertIn("401", result["error"])


if __name__ == "__main__":
    unittest.main()
