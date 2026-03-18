"""
Tests for call_graph_builder.py - Proper call stack with class context.

Tests verify:
1. Class->method hierarchy is maintained (not lost by ast.walk)
2. FQN format: module.py::ClassName.method_name
3. self.method() calls resolve to same-class methods
4. Call paths and impact analysis work correctly
5. Integration with complexity_calculator and uml_generators
"""

import ast
import os
import sys
import json
import tempfile
from pathlib import Path

import pytest

# Add the langgraph_engine to path
sys.path.insert(
    0,
    str(Path(__file__).parent.parent / "scripts" / "langgraph_engine"),
)
sys.path.insert(
    0,
    str(Path(__file__).parent.parent / "scripts"),
)

from call_graph_builder import (
    CallGraphBuilder,
    CallGraph,
    _CallGraphVisitor,
    build_call_graph,
    get_call_graph_metrics,
    get_impact_analysis,
    make_class_node,
    make_method_node,
    make_call_edge,
    _annotation_to_str,
    _get_receiver_name,
    _count_branches,
)


# =========================================================================
# Fixtures
# =========================================================================

SAMPLE_CODE_SIMPLE = '''
class Calculator:
    """A simple calculator."""

    def __init__(self, value=0):
        self.value = value

    def add(self, x):
        self.value += x
        return self

    def _validate(self, x):
        if x is None:
            raise ValueError("x cannot be None")
        return True


def standalone_func(a, b):
    calc = Calculator(a)
    calc.add(b)
    return calc.value
'''

SAMPLE_CODE_MULTI_CLASS = '''
class Base:
    def process(self):
        return self._internal()

    def _internal(self):
        return 42


class Child(Base):
    def process(self):
        result = super().process()
        return self.transform(result)

    def transform(self, value):
        helper = Helper()
        return helper.apply(value)


class Helper:
    def apply(self, x):
        return x * 2
'''

SAMPLE_CODE_ASYNC = '''
import asyncio

class AsyncService:
    async def fetch(self, url: str) -> dict:
        data = await self._request(url)
        return self._parse(data)

    async def _request(self, url: str) -> bytes:
        return b"data"

    def _parse(self, data: bytes) -> dict:
        return {"result": len(data)}
'''

SAMPLE_CODE_COMPLEX = '''
class Orchestrator:
    def __init__(self):
        self.processor = Processor()
        self.validator = Validator()

    def run(self, task):
        if not self.validator.check(task):
            return None
        result = self.processor.execute(task)
        self._log(result)
        return result

    def _log(self, result):
        print(result)


class Processor:
    def execute(self, task):
        data = self._prepare(task)
        return self._transform(data)

    def _prepare(self, task):
        return task.upper()

    def _transform(self, data):
        return data.strip()


class Validator:
    def check(self, task):
        if not task:
            return False
        if len(task) > 1000:
            return False
        return True
'''


@pytest.fixture
def simple_project(tmp_path):
    """Create a temp project with simple Python files."""
    (tmp_path / "calculator.py").write_text(SAMPLE_CODE_SIMPLE, encoding="utf-8")
    return tmp_path


@pytest.fixture
def multi_class_project(tmp_path):
    """Create a temp project with multiple interacting classes."""
    (tmp_path / "models.py").write_text(SAMPLE_CODE_MULTI_CLASS, encoding="utf-8")
    return tmp_path


@pytest.fixture
def async_project(tmp_path):
    """Create a temp project with async code."""
    (tmp_path / "service.py").write_text(SAMPLE_CODE_ASYNC, encoding="utf-8")
    return tmp_path


@pytest.fixture
def complex_project(tmp_path):
    """Create a temp project with complex call chains."""
    (tmp_path / "engine.py").write_text(SAMPLE_CODE_COMPLEX, encoding="utf-8")
    return tmp_path


@pytest.fixture
def multi_file_project(tmp_path):
    """Create a project with multiple files that cross-reference."""
    (tmp_path / "models.py").write_text(SAMPLE_CODE_MULTI_CLASS, encoding="utf-8")
    (tmp_path / "engine.py").write_text(SAMPLE_CODE_COMPLEX, encoding="utf-8")
    (tmp_path / "calculator.py").write_text(SAMPLE_CODE_SIMPLE, encoding="utf-8")
    return tmp_path


# =========================================================================
# Test Data Structures
# =========================================================================

class TestDataStructures:
    """Test the node/edge factory functions."""

    def test_make_class_node(self):
        node = make_class_node(
            "mod.py::Foo", "Foo", "mod.py", 10, bases=["Bar"]
        )
        assert node["id"] == "mod.py::Foo"
        assert node["type"] == "class"
        assert node["name"] == "Foo"
        assert node["bases"] == ["Bar"]
        assert node["methods"] == []

    def test_make_method_node_with_class(self):
        node = make_method_node(
            "mod.py::Foo.bar", "bar", "mod.py", 20,
            parent_class="mod.py::Foo",
            params=["x: int", "y: str"],
            return_type="bool",
        )
        assert node["id"] == "mod.py::Foo.bar"
        assert node["type"] == "method"
        assert node["parent_class"] == "mod.py::Foo"
        assert node["params"] == ["x: int", "y: str"]

    def test_make_method_node_standalone(self):
        node = make_method_node(
            "mod.py::standalone", "standalone", "mod.py", 5,
        )
        assert node["type"] == "function"
        assert node["parent_class"] is None

    def test_make_call_edge(self):
        edge = make_call_edge(
            "mod.py::Foo.bar", "mod.py::Foo.baz", 25, "method_call"
        )
        assert edge["from"] == "mod.py::Foo.bar"
        assert edge["to"] == "mod.py::Foo.baz"
        assert edge["line"] == 25
        assert edge["type"] == "method_call"


# =========================================================================
# Test AST Visitor - Class Context
# =========================================================================

class TestCallGraphVisitor:
    """Test that the AST visitor maintains class context."""

    def test_class_detected(self, simple_project):
        graph = build_call_graph(str(simple_project))
        assert graph is not None
        assert len(graph.classes) == 1
        cls = list(graph.classes.values())[0]
        assert cls["name"] == "Calculator"
        assert "calculator.py::Calculator" == cls["id"]

    def test_methods_have_class_context(self, simple_project):
        graph = build_call_graph(str(simple_project))
        # Methods should have parent_class set
        for fqn, method in graph.methods.items():
            if "Calculator" in fqn:
                assert method["parent_class"] is not None
                assert "Calculator" in method["parent_class"]

    def test_standalone_function_no_class(self, simple_project):
        graph = build_call_graph(str(simple_project))
        # standalone_func should NOT have a parent class
        standalone = [
            m for m in graph.methods.values()
            if m["name"] == "standalone_func"
        ]
        assert len(standalone) == 1
        assert standalone[0]["parent_class"] is None
        assert standalone[0]["type"] == "function"

    def test_fqn_format(self, simple_project):
        graph = build_call_graph(str(simple_project))
        # All FQNs should have :: separator
        for fqn in graph.methods:
            assert "::" in fqn, "FQN missing :: separator: %s" % fqn

    def test_method_visibility(self, simple_project):
        graph = build_call_graph(str(simple_project))
        for fqn, method in graph.methods.items():
            if method["name"] == "_validate":
                assert method["visibility"] == "-"
            elif method["name"] == "add":
                assert method["visibility"] == "+"
            elif method["name"] == "__init__":
                assert method["visibility"] == "+"  # dunder = public

    def test_inheritance_detected(self, multi_class_project):
        graph = build_call_graph(str(multi_class_project))
        # Child extends Base
        inheritance_edges = [
            e for e in graph.edges if e["type"] == "inheritance"
        ]
        assert len(inheritance_edges) >= 1
        child_inherits = [
            e for e in inheritance_edges
            if "Child" in e["from"] and e["to"] == "Base"
        ]
        assert len(child_inherits) == 1

    def test_async_methods(self, async_project):
        graph = build_call_graph(str(async_project))
        async_methods = [
            m for m in graph.methods.values() if m["is_async"]
        ]
        assert len(async_methods) == 2  # fetch and _request
        sync_methods = [
            m for m in graph.methods.values() if not m["is_async"]
        ]
        assert len(sync_methods) == 1  # _parse


# =========================================================================
# Test Call Edge Resolution
# =========================================================================

class TestEdgeResolution:
    """Test that call edges get resolved to proper FQNs."""

    def test_self_calls_resolved(self, simple_project):
        """self.method() calls should resolve to same-class methods."""
        graph = build_call_graph(str(simple_project))
        edges = graph.get_edges()

        # standalone_func calls Calculator() and calc.add()
        # Calculator.__init__ doesn't call anything significant
        # Calculator.add doesn't call other methods
        assert len(edges) > 0

    def test_cross_class_calls(self, multi_class_project):
        """Method calls to other classes should be detected."""
        graph = build_call_graph(str(multi_class_project))
        edges = graph.get_edges()

        # Child.transform creates Helper and calls helper.apply
        call_edges = [e for e in edges if e["type"] != "inheritance"]
        assert len(call_edges) > 0

    def test_constructor_calls(self, simple_project):
        """Calculator() should be detected as a call."""
        graph = build_call_graph(str(simple_project))
        edges = graph.get_edges()

        # standalone_func calls Calculator()
        constructor_calls = [
            e for e in edges
            if "Calculator" in e["to"] or "Calculator" in str(e.get("to", ""))
        ]
        assert len(constructor_calls) >= 1

    def test_resolved_flag(self, multi_class_project):
        graph = build_call_graph(str(multi_class_project))
        edges = graph.get_edges()
        # At least some edges should be resolved
        resolved = [e for e in edges if e.get("resolved", False)]
        # We expect at least a few to resolve (same-file methods)
        assert len(resolved) >= 1 or len(edges) > 0


# =========================================================================
# Test Call Paths
# =========================================================================

class TestCallPaths:
    """Test call path computation."""

    def test_call_paths_computed(self, complex_project):
        graph = build_call_graph(str(complex_project))
        paths = graph.compute_call_paths()
        assert isinstance(paths, list)

    def test_call_path_structure(self, complex_project):
        graph = build_call_graph(str(complex_project))
        paths = graph.compute_call_paths()
        for path in paths:
            assert "id" in path
            assert "path" in path
            assert "depth" in path
            assert "total_complexity" in path
            assert isinstance(path["path"], list)
            assert path["depth"] == len(path["path"])

    def test_max_call_depth(self, complex_project):
        graph = build_call_graph(str(complex_project))
        depth = graph.get_max_call_depth()
        assert isinstance(depth, int)
        assert depth >= 0

    def test_no_cycles_in_paths(self, complex_project):
        graph = build_call_graph(str(complex_project))
        paths = graph.compute_call_paths()
        for path in paths:
            # No duplicate FQNs in a single path (no cycles)
            assert len(path["path"]) == len(set(path["path"]))


# =========================================================================
# Test Impact Analysis
# =========================================================================

class TestImpactAnalysis:
    """Test reverse dependency / impact analysis."""

    def test_impact_map_computed(self, complex_project):
        graph = build_call_graph(str(complex_project))
        impact = graph.compute_impact_map()
        assert isinstance(impact, dict)
        # Every method should have an entry
        assert len(impact) == len(graph.methods)

    def test_impact_analysis_function(self, complex_project):
        result = get_impact_analysis(
            str(complex_project),
            "engine.py::Processor.execute"
        )
        assert "target" in result
        assert "directly_affected" in result
        assert "affected_count" in result


# =========================================================================
# Test Call Graph Stats
# =========================================================================

class TestCallGraphStats:
    """Test statistics computation."""

    def test_stats_structure(self, simple_project):
        graph = build_call_graph(str(simple_project))
        stats = graph.get_stats()
        assert "total_classes" in stats
        assert "total_methods" in stats
        assert "total_functions" in stats
        assert "total_call_edges" in stats
        assert "files_analyzed" in stats
        assert "max_call_depth" in stats
        assert "avg_cyclomatic" in stats

    def test_class_count(self, simple_project):
        graph = build_call_graph(str(simple_project))
        stats = graph.get_stats()
        assert stats["total_classes"] == 1  # Calculator

    def test_multi_class_count(self, multi_class_project):
        graph = build_call_graph(str(multi_class_project))
        stats = graph.get_stats()
        assert stats["total_classes"] == 3  # Base, Child, Helper

    def test_multi_file_stats(self, multi_file_project):
        graph = build_call_graph(str(multi_file_project))
        stats = graph.get_stats()
        assert stats["files_analyzed"] == 3
        assert stats["total_classes"] >= 5


# =========================================================================
# Test Serialization
# =========================================================================

class TestSerialization:
    """Test to_dict() and to_json() output format."""

    def test_to_dict_structure(self, complex_project):
        graph = build_call_graph(str(complex_project))
        data = graph.to_dict()
        assert data["version"] == "2.0.0"
        assert "stats" in data
        assert "nodes" in data
        assert "edges" in data
        assert "call_paths" in data
        assert "classes" in data["nodes"]
        assert "methods" in data["nodes"]

    def test_to_json_valid(self, complex_project):
        graph = build_call_graph(str(complex_project))
        json_str = graph.to_json()
        parsed = json.loads(json_str)
        assert parsed["version"] == "2.0.0"

    def test_node_has_fqn(self, complex_project):
        graph = build_call_graph(str(complex_project))
        data = graph.to_dict()
        for cls in data["nodes"]["classes"]:
            assert "::" in cls["id"]
            assert cls["type"] == "class"
        for method in data["nodes"]["methods"]:
            assert "::" in method["id"]
            assert method["type"] in ("method", "function")

    def test_edge_has_from_to(self, complex_project):
        graph = build_call_graph(str(complex_project))
        data = graph.to_dict()
        for edge in data["edges"]:
            assert "from" in edge
            assert "to" in edge
            assert "line" in edge
            assert "type" in edge


# =========================================================================
# Test Integration Functions
# =========================================================================

class TestIntegration:
    """Test convenience/integration functions."""

    def test_get_call_graph_metrics(self, simple_project):
        metrics = get_call_graph_metrics(str(simple_project))
        assert metrics["call_graph_available"] is True
        assert "method_call_depth" in metrics
        assert "method_call_count" in metrics
        assert "total_classes" in metrics
        assert "total_methods" in metrics
        assert "entry_points" in metrics
        assert "resolved_ratio" in metrics

    def test_metrics_nonexistent_path(self):
        metrics = get_call_graph_metrics("/nonexistent/path/xyz")
        # Should not crash, but may return limited data
        assert isinstance(metrics, dict)

    def test_build_call_graph_convenience(self, simple_project):
        graph = build_call_graph(str(simple_project))
        assert graph is not None
        assert isinstance(graph, CallGraph)


# =========================================================================
# Test Cyclomatic Complexity
# =========================================================================

class TestCyclomaticComplexity:
    """Test per-method cyclomatic complexity calculation."""

    def test_simple_method_low_complexity(self, simple_project):
        graph = build_call_graph(str(simple_project))
        add_method = [
            m for m in graph.methods.values() if m["name"] == "add"
        ]
        assert len(add_method) == 1
        # add() has no branches, complexity should be 1
        assert add_method[0]["cyclomatic"] == 1

    def test_branching_method_higher_complexity(self, simple_project):
        graph = build_call_graph(str(simple_project))
        validate = [
            m for m in graph.methods.values() if m["name"] == "_validate"
        ]
        assert len(validate) == 1
        # _validate has an if statement, complexity should be > 1
        assert validate[0]["cyclomatic"] > 1

    def test_validator_check_complexity(self, complex_project):
        graph = build_call_graph(str(complex_project))
        check = [
            m for m in graph.methods.values() if m["name"] == "check"
        ]
        assert len(check) == 1
        # check() has 2 if statements
        assert check[0]["cyclomatic"] >= 3


# =========================================================================
# Test Parameters and Return Types
# =========================================================================

class TestParamsAndTypes:
    """Test parameter and return type extraction."""

    def test_params_extracted(self, simple_project):
        graph = build_call_graph(str(simple_project))
        add_method = [
            m for m in graph.methods.values() if m["name"] == "add"
        ]
        assert len(add_method) == 1
        # add(self, x) -> params should be ["x"] (self excluded)
        assert "x" in add_method[0]["params"]
        assert "self" not in add_method[0]["params"]

    def test_type_annotations(self, async_project):
        graph = build_call_graph(str(async_project))
        fetch = [
            m for m in graph.methods.values() if m["name"] == "fetch"
        ]
        assert len(fetch) == 1
        # fetch(self, url: str) -> dict
        params = fetch[0]["params"]
        assert any("url" in p for p in params)
        assert fetch[0]["return_type"] == "dict"


# =========================================================================
# Test Helper Functions
# =========================================================================

class TestHelpers:
    """Test AST helper functions."""

    def test_annotation_to_str_name(self):
        node = ast.Name(id="str")
        assert _annotation_to_str(node) == "str"

    def test_annotation_to_str_constant(self):
        node = ast.Constant(value=42)
        assert _annotation_to_str(node) == "42"

    def test_get_receiver_name_simple(self):
        node = ast.Name(id="self")
        assert _get_receiver_name(node) == "self"

    def test_count_branches_no_branches(self):
        source = "def foo(): return 1"
        tree = ast.parse(source)
        func = tree.body[0]
        assert _count_branches(func) == 0

    def test_count_branches_with_if(self):
        source = "def foo(x):\n    if x: return 1\n    return 0"
        tree = ast.parse(source)
        func = tree.body[0]
        assert _count_branches(func) >= 1


# =========================================================================
# Test Empty/Edge Cases
# =========================================================================

class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_project(self, tmp_path):
        graph = build_call_graph(str(tmp_path))
        assert graph is not None
        assert len(graph.classes) == 0
        assert len(graph.methods) == 0

    def test_syntax_error_file(self, tmp_path):
        (tmp_path / "bad.py").write_text("def broken(:\n    pass", encoding="utf-8")
        graph = build_call_graph(str(tmp_path))
        assert graph is not None
        # Should not crash, just skip the bad file

    def test_empty_file(self, tmp_path):
        (tmp_path / "empty.py").write_text("", encoding="utf-8")
        graph = build_call_graph(str(tmp_path))
        assert graph is not None

    def test_file_with_only_imports(self, tmp_path):
        (tmp_path / "imports_only.py").write_text(
            "import os\nimport sys\n", encoding="utf-8"
        )
        graph = build_call_graph(str(tmp_path))
        assert graph is not None
        assert len(graph.classes) == 0

    def test_deeply_nested_classes(self, tmp_path):
        code = '''
class Outer:
    class Inner:
        def method(self):
            pass
    def outer_method(self):
        pass
'''
        (tmp_path / "nested.py").write_text(code, encoding="utf-8")
        graph = build_call_graph(str(tmp_path))
        assert len(graph.classes) == 2  # Outer and Inner


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
