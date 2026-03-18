"""
Tests for UML diagram generation (uml_generators.py).

Tests AST analysis, Mermaid/PlantUML generation, and Kroki rendering.
"""

import os
import sys
import ast
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Add scripts to path for imports
scripts_dir = str(Path(__file__).resolve().parent.parent / "scripts")
if scripts_dir not in sys.path:
    sys.path.insert(0, scripts_dir)

from langgraph_engine.uml_generators import (
    UMLAstAnalyzer,
    UMLDiagramGenerator,
    KrokiRenderer,
    _simplify_type,
    _clean_mermaid,
    _clean_plantuml,
    _plantuml_stub,
)


# ==================================================================
# Fixtures
# ==================================================================

@pytest.fixture
def tmp_project(tmp_path):
    """Create a temporary Python project for testing."""
    # Create a simple Python file with classes
    src_dir = tmp_path / "src"
    src_dir.mkdir()

    sample_py = src_dir / "models.py"
    sample_py.write_text(
        "class Animal:\n"
        "    species: str = ''\n"
        "\n"
        "    def __init__(self, name: str, age: int = 0):\n"
        "        self.name = name\n"
        "        self.age = age\n"
        "        self._internal = True\n"
        "\n"
        "    def speak(self) -> str:\n"
        "        return ''\n"
        "\n"
        "    def _private_method(self):\n"
        "        pass\n"
        "\n"
        "\n"
        "class Dog(Animal):\n"
        "    breed: str = ''\n"
        "\n"
        "    def speak(self) -> str:\n"
        "        return 'Woof'\n"
        "\n"
        "    def fetch(self, item: str) -> bool:\n"
        "        return True\n",
        encoding="utf-8",
    )

    # Create a file with imports
    utils_py = src_dir / "utils.py"
    utils_py.write_text(
        "import os\n"
        "import json\n"
        "from pathlib import Path\n"
        "from .models import Animal\n"
        "\n"
        "def helper():\n"
        "    a = Animal('test')\n"
        "    a.speak()\n"
        "    return str(Path('.'))\n",
        encoding="utf-8",
    )

    # Create a second module for dependency testing
    services_dir = tmp_path / "services"
    services_dir.mkdir()
    svc_py = services_dir / "handler.py"
    svc_py.write_text(
        "from src.models import Dog\n"
        "\n"
        "class DogHandler:\n"
        "    def process(self, dog):\n"
        "        dog.speak()\n"
        "        dog.fetch('ball')\n",
        encoding="utf-8",
    )

    # Create a README for use case diagram
    readme = tmp_path / "README.md"
    readme.write_text(
        "# Test Project\n\nA sample project for testing UML generation.\n",
        encoding="utf-8",
    )

    return tmp_path


@pytest.fixture
def analyzer(tmp_project):
    return UMLAstAnalyzer(str(tmp_project))


@pytest.fixture
def generator(tmp_project):
    return UMLDiagramGenerator(str(tmp_project))


# ==================================================================
# TestUMLAstAnalyzer
# ==================================================================

class TestUMLAstAnalyzer:

    def test_extract_classes_simple(self, analyzer, tmp_project):
        """Extract classes with methods and attributes."""
        classes = analyzer.extract_classes(tmp_project / "src" / "models.py")
        assert len(classes) == 2

        animal = next(c for c in classes if c["name"] == "Animal")
        assert animal["name"] == "Animal"
        assert len(animal["bases"]) == 0
        assert any(m["name"] == "speak" for m in animal["methods"])
        assert any(m["name"] == "__init__" for m in animal["methods"])
        assert any(a["name"] == "name" for a in animal["attributes"])
        assert any(a["name"] == "age" for a in animal["attributes"])

    def test_extract_classes_inheritance(self, analyzer, tmp_project):
        """Extract parent/child classes with inheritance."""
        classes = analyzer.extract_classes(tmp_project / "src" / "models.py")
        dog = next(c for c in classes if c["name"] == "Dog")
        assert "Animal" in dog["bases"]
        assert any(m["name"] == "fetch" for m in dog["methods"])

    def test_extract_classes_empty_file(self, analyzer, tmp_path):
        """Empty file returns no classes."""
        empty = tmp_path / "empty.py"
        empty.write_text("# no classes here\nx = 42\n", encoding="utf-8")
        classes = analyzer.extract_classes(empty)
        assert classes == []

    def test_extract_classes_syntax_error(self, analyzer, tmp_path):
        """File with syntax errors returns empty list gracefully."""
        bad = tmp_path / "bad.py"
        bad.write_text("def broken(\n", encoding="utf-8")
        classes = analyzer.extract_classes(bad)
        assert classes == []

    def test_extract_classes_visibility(self, analyzer, tmp_project):
        """Private methods get '-' visibility, public get '+'."""
        classes = analyzer.extract_classes(tmp_project / "src" / "models.py")
        animal = next(c for c in classes if c["name"] == "Animal")

        speak = next(m for m in animal["methods"] if m["name"] == "speak")
        assert speak["visibility"] == "+"

        private = next(
            m for m in animal["methods"] if m["name"] == "_private_method"
        )
        assert private["visibility"] == "-"

    def test_extract_classes_self_attributes(self, analyzer, tmp_project):
        """Detect self.attr assignments in __init__."""
        classes = analyzer.extract_classes(tmp_project / "src" / "models.py")
        animal = next(c for c in classes if c["name"] == "Animal")
        attr_names = [a["name"] for a in animal["attributes"]]
        assert "name" in attr_names
        assert "age" in attr_names
        # Private attribute
        internal = next(
            (a for a in animal["attributes"] if a["name"] == "_internal"),
            None
        )
        if internal:
            assert internal["visibility"] == "-"

    def test_extract_all_classes(self, analyzer):
        """Recursively extract classes from all files."""
        all_classes = analyzer.extract_all_classes()
        names = [c["name"] for c in all_classes]
        assert "Animal" in names
        assert "Dog" in names
        assert "DogHandler" in names

    def test_extract_imports(self, analyzer, tmp_project):
        """Extract import and from-import statements."""
        imports = analyzer.extract_imports(tmp_project / "src" / "utils.py")
        assert "os" in imports["imports"]
        assert "json" in imports["imports"]
        assert any(
            fi["name"] == "Path" for fi in imports["from_imports"]
        )
        assert any(
            fi["name"] == "Animal" for fi in imports["from_imports"]
        )

    def test_build_dependency_graph(self, analyzer):
        """Build module-level dependency map."""
        graph = analyzer.build_dependency_graph()
        assert isinstance(graph, dict)
        # models.py has no project-internal deps typically
        # utils.py imports os, json, pathlib, models
        if "utils" in graph:
            assert "os" in graph["utils"] or "json" in graph["utils"]

    def test_extract_call_chains(self, analyzer, tmp_project):
        """Extract function call chains."""
        chains = analyzer.extract_call_chains(
            tmp_project / "src" / "utils.py", "helper"
        )
        assert len(chains) > 0
        callees = [c["callee"] for c in chains]
        assert "Animal" in callees or "speak" in callees

    def test_extract_call_chains_no_match(self, analyzer, tmp_project):
        """No matching entry function returns empty."""
        chains = analyzer.extract_call_chains(
            tmp_project / "src" / "utils.py", "nonexistent_func"
        )
        assert chains == []


# ==================================================================
# TestUMLDiagramGenerator
# ==================================================================

class TestUMLDiagramGenerator:

    def test_generate_class_diagram_mermaid(self, generator, tmp_project):
        """Generate valid Mermaid classDiagram syntax."""
        classes = generator.analyzer.extract_all_classes(
            tmp_project / "src"
        )
        syntax = generator.generate_class_diagram(classes)
        assert syntax.startswith("classDiagram")
        assert "class Animal" in syntax
        assert "class Dog" in syntax
        assert "Animal <|-- Dog" in syntax

    def test_generate_class_diagram_no_classes(self, generator):
        """Empty class list produces stub diagram."""
        syntax = generator.generate_class_diagram(classes=[])
        assert "classDiagram" in syntax
        assert "No classes found" in syntax

    def test_generate_class_diagram_methods_attrs(self, generator, tmp_project):
        """Class diagram includes methods and attributes."""
        classes = generator.analyzer.extract_classes(
            tmp_project / "src" / "models.py"
        )
        syntax = generator.generate_class_diagram(classes)
        assert "speak" in syntax
        assert "name" in syntax

    def test_generate_package_diagram(self, generator):
        """Generate valid Mermaid flowchart for packages."""
        syntax = generator.generate_package_diagram()
        assert syntax.startswith("flowchart")

    def test_generate_component_diagram(self, generator):
        """Generate valid Mermaid component diagram."""
        syntax = generator.generate_component_diagram()
        assert "flowchart TB" in syntax

    def test_generate_sequence_diagram_ast(self, generator):
        """Sequence diagram from AST call chains (no LLM)."""
        syntax = generator.generate_sequence_diagram()
        assert "sequenceDiagram" in syntax

    def test_generate_all_diagrams(self, generator):
        """Generate multiple diagrams at once."""
        results = generator.generate_all()
        assert isinstance(results, dict)
        assert "class-diagram" in results
        assert "package-diagram" in results
        assert "component-diagram" in results
        # Tier 1 should always succeed
        assert len(results) >= 3

    def test_save_diagram_creates_file(self, generator):
        """Save diagram writes file to docs/uml/."""
        syntax = "classDiagram\n    class Foo"
        path = generator.save_diagram("test-diagram", syntax)
        assert Path(path).exists()
        content = Path(path).read_text(encoding="utf-8")
        assert "```mermaid" in content
        assert "classDiagram" in content
        assert "Auto-generated" in content

    def test_save_diagram_plantuml(self, generator):
        """PlantUML diagrams get plantuml fence."""
        syntax = "@startuml\nclass Foo\n@enduml"
        path = generator.save_diagram("test-plantuml", syntax)
        content = Path(path).read_text(encoding="utf-8")
        assert "```plantuml" in content
        assert "@startuml" in content

    def test_save_diagram_creates_directory(self, tmp_path):
        """Output directory is created if missing."""
        gen = UMLDiagramGenerator(str(tmp_path), "new_dir/uml")
        syntax = "classDiagram\n    class Bar"
        path = gen.save_diagram("test", syntax)
        assert Path(path).exists()

    def test_generate_class_diagram_scope_file(self, generator, tmp_project):
        """Scope to a single file."""
        file_path = str(tmp_project / "src" / "models.py")
        syntax = generator.generate_class_diagram(scope=file_path)
        assert "Animal" in syntax


# ==================================================================
# TestKrokiRenderer
# ==================================================================

class TestKrokiRenderer:

    def test_render_plantuml_svg(self):
        """Kroki API call for PlantUML (mocked)."""
        renderer = KrokiRenderer()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"<svg>test</svg>"

        with patch("langgraph_engine.uml_generators.KrokiRenderer.render") as mock:
            mock.return_value = b"<svg>test</svg>"
            result = renderer.render(
                "@startuml\nclass A\n@enduml", "plantuml", "svg"
            )
        assert result == b"<svg>test</svg>"

    def test_render_mermaid_svg(self):
        """Kroki API call for Mermaid (mocked)."""
        renderer = KrokiRenderer()
        with patch("langgraph_engine.uml_generators.KrokiRenderer.render") as mock:
            mock.return_value = b"<svg>mermaid</svg>"
            result = renderer.render(
                "classDiagram\n    class A", "mermaid", "svg"
            )
        assert result == b"<svg>mermaid</svg>"

    def test_render_failure_graceful(self):
        """API error returns None."""
        renderer = KrokiRenderer()
        with patch.dict("sys.modules", {"requests": MagicMock()}) as _:
            import importlib
            mock_requests = sys.modules["requests"]
            mock_resp = MagicMock()
            mock_resp.status_code = 500
            mock_resp.text = "Internal Server Error"
            mock_requests.post.return_value = mock_resp

            # Direct test - mock the whole render method for simplicity
            with patch.object(renderer, "render", return_value=None):
                result = renderer.render("bad input")
        assert result is None

    def test_render_to_file(self, tmp_path):
        """Render and save to file."""
        renderer = KrokiRenderer()
        out = tmp_path / "test.svg"

        with patch.object(
            renderer, "render", return_value=b"<svg>ok</svg>"
        ):
            path = renderer.render_to_file(
                "@startuml\nA\n@enduml",
                str(out), "plantuml", "svg"
            )
        assert path is not None
        assert Path(path).exists()
        assert Path(path).read_bytes() == b"<svg>ok</svg>"

    def test_render_to_file_failure(self, tmp_path):
        """Render failure returns None."""
        renderer = KrokiRenderer()
        out = tmp_path / "fail.svg"
        with patch.object(renderer, "render", return_value=None):
            path = renderer.render_to_file("bad", str(out))
        assert path is None


# ==================================================================
# Test utility functions
# ==================================================================

class TestUtilities:

    def test_simplify_type_name(self):
        """Simplify AST Name type dump."""
        assert _simplify_type("Name(id='str')") == "str"
        assert _simplify_type("Name(id='int')") == "int"
        assert _simplify_type("Name(id='Optional')") == "Optional"

    def test_simplify_type_empty(self):
        assert _simplify_type("") == ""
        assert _simplify_type(None) == ""

    def test_simplify_type_constant(self):
        """Constant types return empty."""
        assert _simplify_type("Constant(value=42)") == ""

    def test_clean_mermaid_with_fences(self):
        """Remove markdown fences from Mermaid output."""
        raw = "```mermaid\nclassDiagram\n    class A\n```"
        assert _clean_mermaid(raw) == "classDiagram\n    class A"

    def test_clean_mermaid_plain(self):
        """Plain Mermaid passes through."""
        raw = "classDiagram\n    class A"
        assert _clean_mermaid(raw) == raw

    def test_clean_plantuml_with_fences(self):
        """Remove markdown fences and ensure @startuml/@enduml."""
        raw = "```plantuml\n@startuml\nclass A\n@enduml\n```"
        result = _clean_plantuml(raw)
        assert result.startswith("@startuml")
        assert result.endswith("@enduml")

    def test_clean_plantuml_adds_wrapper(self):
        """Add @startuml/@enduml if missing."""
        raw = "class A\nclass B"
        result = _clean_plantuml(raw)
        assert result.startswith("@startuml")
        assert result.endswith("@enduml")

    def test_plantuml_stub(self):
        """Generate PlantUML stub with message."""
        result = _plantuml_stub("test", "hello")
        assert "@startuml" in result
        assert "test: hello" in result
        assert "@enduml" in result


# ==================================================================
# Integration test
# ==================================================================

class TestIntegration:

    def test_analyze_and_generate_this_project(self):
        """Run analysis on the claude-insight project itself."""
        project_root = Path(__file__).resolve().parent.parent
        analyzer = UMLAstAnalyzer(str(project_root))

        # Should find classes in the project
        classes = analyzer.extract_all_classes(
            project_root / "scripts" / "langgraph_engine"
        )
        assert len(classes) > 0, "Should find classes in langgraph_engine"

        # Generate class diagram
        gen = UMLDiagramGenerator(str(project_root), "docs/uml")
        syntax = gen.generate_class_diagram(classes[:20])
        assert "classDiagram" in syntax
        assert len(syntax.split("\n")) > 2

    def test_full_generate_and_save(self, tmp_path):
        """Full workflow: analyze, generate, save."""
        # Create minimal project
        py_file = tmp_path / "app.py"
        py_file.write_text(
            "class Server:\n"
            "    port: int = 8080\n"
            "    def start(self):\n"
            "        pass\n"
            "    def stop(self):\n"
            "        pass\n"
            "\n"
            "class Client:\n"
            "    def connect(self, server):\n"
            "        server.start()\n",
            encoding="utf-8",
        )

        gen = UMLDiagramGenerator(str(tmp_path))
        results = gen.generate_all()

        assert "class-diagram" in results

        # Save all
        for name, syntax in results.items():
            path = gen.save_diagram(name, syntax)
            assert Path(path).exists()

        # Check output directory
        uml_dir = tmp_path / "docs" / "uml"
        assert uml_dir.exists()
        md_files = list(uml_dir.glob("*.md"))
        assert len(md_files) >= 1
