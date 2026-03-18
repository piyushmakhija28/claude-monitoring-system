"""
UML Diagram Generator - Auto-generates 12 UML diagram types from codebase analysis.

Tier 1 (AST-based, no LLM): Class, Package, Component
Tier 2 (AST + LLM hybrid): Sequence, Activity, State
Tier 3 (LLM-powered): Use Case, Object, Deployment, Communication,
                       Composite Structure, Interaction Overview

Rendering:
- Mermaid syntax for GitHub-native rendering (Tier 1 + 2)
- PlantUML syntax for remaining types (Tier 3)
- Kroki.io free API for PlantUML -> SVG rendering
"""

import os
import ast
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ======================================================================
# Data classes (plain dicts for simplicity, no dataclass dep)
# ======================================================================

def _make_class_info(
    name, file_path, bases=None, methods=None, attributes=None
):
    """Create a ClassInfo dict."""
    return {
        "name": name,
        "file_path": str(file_path),
        "module": str(Path(file_path).stem),
        "bases": bases or [],
        "methods": methods or [],
        "attributes": attributes or [],
    }


def _make_method_info(name, params=None, return_type="", visibility="+"):
    """Create a MethodInfo dict."""
    return {
        "name": name,
        "params": params or [],
        "return_type": return_type,
        "visibility": visibility,
    }


def _make_attr_info(name, type_hint="", visibility="+"):
    """Create an AttributeInfo dict."""
    return {
        "name": name,
        "type_hint": type_hint,
        "visibility": visibility,
    }


# ======================================================================
# AST Analyzer
# ======================================================================

class UMLAstAnalyzer:
    """Python AST analysis for structural UML diagrams."""

    def __init__(self, project_root):
        self.project_root = Path(project_root)

    def extract_classes(self, file_path):
        """Extract class info from a single Python file.

        Returns list of ClassInfo dicts.
        """
        file_path = Path(file_path)
        classes = []
        try:
            source = file_path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source, filename=str(file_path))
        except (SyntaxError, OSError) as e:
            logger.debug("Cannot parse %s: %s", file_path, e)
            return classes

        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue

            bases = []
            for base in node.bases:
                if isinstance(base, ast.Name):
                    bases.append(base.id)
                elif isinstance(base, ast.Attribute):
                    bases.append(ast.dump(base))

            methods = []
            attributes = []

            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    vis = "-" if item.name.startswith("_") else "+"
                    if item.name.startswith("__") and item.name.endswith("__"):
                        vis = "+"  # dunder methods are public interface

                    params = []
                    for arg in item.args.args:
                        if arg.arg != "self":
                            params.append(arg.arg)

                    ret = ""
                    if item.returns:
                        try:
                            ret = ast.dump(item.returns)
                        except Exception:
                            pass

                    methods.append(
                        _make_method_info(item.name, params, ret, vis)
                    )

                elif isinstance(item, ast.Assign):
                    for target in item.targets:
                        if isinstance(target, ast.Name):
                            attributes.append(
                                _make_attr_info(target.id, "", "+")
                            )

                elif isinstance(item, ast.AnnAssign) and item.target:
                    if isinstance(item.target, ast.Name):
                        hint = ""
                        if item.annotation:
                            try:
                                hint = ast.dump(item.annotation)
                            except Exception:
                                pass
                        attributes.append(
                            _make_attr_info(item.target.id, hint, "+")
                        )

            # Also scan __init__ for self.attr assignments
            for item in node.body:
                if (isinstance(item, ast.FunctionDef)
                        and item.name == "__init__"):
                    for stmt in ast.walk(item):
                        if (isinstance(stmt, ast.Assign)
                                and len(stmt.targets) == 1):
                            target = stmt.targets[0]
                            if (isinstance(target, ast.Attribute)
                                    and isinstance(target.value, ast.Name)
                                    and target.value.id == "self"):
                                attr_name = target.attr
                                vis = "-" if attr_name.startswith("_") else "+"
                                # Avoid duplicates
                                existing = [
                                    a["name"] for a in attributes
                                ]
                                if attr_name not in existing:
                                    attributes.append(
                                        _make_attr_info(attr_name, "", vis)
                                    )

            classes.append(
                _make_class_info(
                    node.name, file_path, bases, methods, attributes
                )
            )

        return classes

    def extract_all_classes(self, directory=None):
        """Recursively extract classes from all .py files."""
        root = Path(directory) if directory else self.project_root
        all_classes = []

        for py_file in root.rglob("*.py"):
            # Skip test files, __pycache__, venv
            rel = str(py_file.relative_to(root))
            if any(skip in rel for skip in [
                "__pycache__", ".venv", "venv", "node_modules"
            ]):
                continue
            all_classes.extend(self.extract_classes(py_file))

        return all_classes

    def extract_imports(self, file_path):
        """Extract import statements from a Python file.

        Returns dict with 'imports' and 'from_imports' lists.
        """
        file_path = Path(file_path)
        result = {"imports": [], "from_imports": [], "file": str(file_path)}
        try:
            source = file_path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source, filename=str(file_path))
        except (SyntaxError, OSError):
            return result

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    result["imports"].append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    result["from_imports"].append(
                        {"module": module, "name": alias.name}
                    )

        return result

    def build_dependency_graph(self, directory=None):
        """Build module-level dependency map.

        Returns dict: {module_name: set_of_imported_modules}
        """
        root = Path(directory) if directory else self.project_root
        graph = {}

        for py_file in root.rglob("*.py"):
            rel = str(py_file.relative_to(root))
            if any(skip in rel for skip in [
                "__pycache__", ".venv", "venv", "node_modules"
            ]):
                continue

            module_name = py_file.stem
            imports = self.extract_imports(py_file)
            deps = set()

            for imp in imports["imports"]:
                deps.add(imp.split(".")[0])
            for fi in imports["from_imports"]:
                if fi["module"]:
                    deps.add(fi["module"].split(".")[0])

            # Filter to only project-internal deps
            graph[module_name] = deps

        return graph

    def extract_call_chains(self, file_path, entry_func=None):
        """Extract static call chains from a file.

        Returns list of call chain dicts:
        [{caller, callee, file}]
        """
        file_path = Path(file_path)
        chains = []
        try:
            source = file_path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source, filename=str(file_path))
        except (SyntaxError, OSError):
            return chains

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            caller = node.name
            if entry_func and caller != entry_func:
                continue

            for child in ast.walk(node):
                if isinstance(child, ast.Call):
                    callee = ""
                    if isinstance(child.func, ast.Name):
                        callee = child.func.id
                    elif isinstance(child.func, ast.Attribute):
                        callee = child.func.attr
                    if callee:
                        chains.append({
                            "caller": caller,
                            "callee": callee,
                            "file": str(file_path),
                        })

        return chains


# ======================================================================
# Diagram Generator
# ======================================================================

class UMLDiagramGenerator:
    """Generate Mermaid/PlantUML syntax from analysis results."""

    def __init__(self, project_root, output_dir="docs/uml"):
        self.project_root = Path(project_root)
        self.output_dir = self.project_root / output_dir
        self.analyzer = UMLAstAnalyzer(project_root)

    # ------------------------------------------------------------------
    # Tier 1: AST-based (no LLM)
    # ------------------------------------------------------------------

    def generate_class_diagram(self, classes=None, scope="all"):
        """Generate Mermaid classDiagram from Python AST analysis.

        Args:
            classes: Pre-extracted class list, or None to auto-extract.
            scope: "all" for full project, or a directory/file path.
        """
        if classes is None:
            if scope == "all":
                classes = self.analyzer.extract_all_classes()
            else:
                scope_path = Path(scope)
                if scope_path.is_file():
                    classes = self.analyzer.extract_classes(scope_path)
                else:
                    classes = self.analyzer.extract_all_classes(scope_path)

        if not classes:
            return "classDiagram\n    note \"No classes found\""

        lines = ["classDiagram"]

        for cls in classes:
            lines.append("    class %s {" % cls["name"])

            for attr in cls.get("attributes", [])[:10]:
                vis = attr.get("visibility", "+")
                hint = attr.get("type_hint", "")
                type_str = ""
                if hint:
                    # Simplify AST dump to readable type
                    type_str = _simplify_type(hint)
                    type_str = ": %s" % type_str if type_str else ""
                lines.append("        %s%s%s" % (vis, attr["name"], type_str))

            for method in cls.get("methods", [])[:15]:
                vis = method.get("visibility", "+")
                params = ", ".join(method.get("params", [])[:4])
                ret = ""
                if method.get("return_type"):
                    ret = " %s" % _simplify_type(method["return_type"])
                lines.append(
                    "        %s%s(%s)%s" % (vis, method["name"], params, ret)
                )

            lines.append("    }")

        # Add inheritance relationships
        for cls in classes:
            for base in cls.get("bases", []):
                if any(c["name"] == base for c in classes):
                    lines.append(
                        "    %s <|-- %s" % (base, cls["name"])
                    )

        return "\n".join(lines)

    def generate_package_diagram(self, dep_graph=None):
        """Generate Mermaid flowchart from module dependencies."""
        if dep_graph is None:
            dep_graph = self.analyzer.build_dependency_graph()

        if not dep_graph:
            return "flowchart LR\n    note[No modules found]"

        # Group modules by directory
        lines = ["flowchart LR"]

        # Collect all known project modules
        project_modules = set(dep_graph.keys())

        for module, deps in sorted(dep_graph.items()):
            for dep in sorted(deps):
                # Only show internal dependencies
                if dep in project_modules:
                    lines.append("    %s --> %s" % (module, dep))

        # Add isolated modules (no deps shown)
        connected = set()
        for module, deps in dep_graph.items():
            internal_deps = deps & project_modules
            if internal_deps:
                connected.add(module)
                connected.update(internal_deps)

        for module in sorted(project_modules - connected):
            lines.append("    %s" % module)

        return "\n".join(lines)

    def generate_component_diagram(self, dep_graph=None):
        """Generate Mermaid flowchart representing components."""
        if dep_graph is None:
            dep_graph = self.analyzer.build_dependency_graph()

        if not dep_graph:
            return "flowchart TB\n    note[No components found]"

        lines = ["flowchart TB"]

        # Group by top-level directories
        groups = {}
        for module in dep_graph:
            # Try to find the file to determine its directory
            for py_file in self.project_root.rglob("%s.py" % module):
                try:
                    rel = py_file.relative_to(self.project_root)
                    parts = rel.parts
                    group = parts[0] if len(parts) > 1 else "root"
                    if group not in groups:
                        groups[group] = []
                    groups[group].append(module)
                except ValueError:
                    pass
                break

        for group, modules in sorted(groups.items()):
            safe_group = group.replace("-", "_").replace(".", "_")
            lines.append("    subgraph %s[%s]" % (safe_group, group))
            for mod in sorted(set(modules)):
                lines.append("        %s[%s]" % (mod, mod))
            lines.append("    end")

        # Add cross-group dependencies
        project_modules = set(dep_graph.keys())
        for module, deps in dep_graph.items():
            for dep in deps:
                if dep in project_modules and dep != module:
                    lines.append("    %s --> %s" % (module, dep))

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Tier 2: AST + LLM hybrid
    # ------------------------------------------------------------------

    def generate_sequence_diagram(self, call_chains=None, context=""):
        """Generate Mermaid sequenceDiagram from call chains."""
        if call_chains is None:
            # Auto-extract from main entry points
            call_chains = []
            for py_file in self.project_root.rglob("*.py"):
                rel = str(py_file.relative_to(self.project_root))
                if any(skip in rel for skip in [
                    "__pycache__", ".venv", "test"
                ]):
                    continue
                chains = self.analyzer.extract_call_chains(py_file)
                call_chains.extend(chains[:20])
                if len(call_chains) >= 80:
                    break

        if not call_chains:
            return "sequenceDiagram\n    Note over System: No call chains found"

        lines = ["sequenceDiagram"]
        # Deduplicate and limit
        seen = set()
        count = 0
        for chain in call_chains:
            key = (chain["caller"], chain["callee"])
            if key in seen or chain["caller"] == chain["callee"]:
                continue
            seen.add(key)
            lines.append(
                "    %s->>%s: %s()" % (
                    chain["caller"], chain["callee"], chain["callee"]
                )
            )
            count += 1
            if count >= 30:
                break

        if context:
            enriched = self._llm_enrich(
                "\n".join(lines), "sequence diagram", context
            )
            if enriched:
                return enriched

        return "\n".join(lines)

    def generate_activity_diagram(self, function_code="", context=""):
        """Generate Mermaid flowchart TD from function logic."""
        if not function_code and not context:
            return "flowchart TD\n    Start([Start]) --> End([End])"

        prompt = (
            "Generate a Mermaid flowchart TD (activity diagram) for "
            "the following code/context. Output ONLY the Mermaid syntax, "
            "no markdown fences.\n\n%s\n\n%s"
            % (function_code[:2000], context[:500])
        )

        result = self._llm_generate(prompt)
        if result:
            return _clean_mermaid(result)

        # Fallback: basic structure
        return "flowchart TD\n    Start([Start]) --> Process[Process] --> End([End])"

    def generate_state_diagram(self, state_info="", context=""):
        """Generate Mermaid stateDiagram-v2."""
        if not state_info and not context:
            return "stateDiagram-v2\n    [*] --> Idle\n    Idle --> [*]"

        prompt = (
            "Generate a Mermaid stateDiagram-v2 for the following "
            "system/context. Output ONLY the Mermaid syntax, "
            "no markdown fences.\n\n%s\n\n%s"
            % (state_info[:2000], context[:500])
        )

        result = self._llm_generate(prompt)
        if result:
            return _clean_mermaid(result)

        return "stateDiagram-v2\n    [*] --> Idle\n    Idle --> [*]"

    # ------------------------------------------------------------------
    # Tier 3: LLM-powered
    # ------------------------------------------------------------------

    def generate_usecase_diagram(self, srs_content="", readme_content=""):
        """Generate PlantUML use case diagram from requirements docs."""
        if not srs_content:
            srs_path = self.project_root / "SRS.md"
            if srs_path.is_file():
                srs_content = srs_path.read_text(
                    encoding="utf-8", errors="replace"
                )[:3000]
        if not readme_content:
            readme_path = self.project_root / "README.md"
            if readme_path.is_file():
                readme_content = readme_path.read_text(
                    encoding="utf-8", errors="replace"
                )[:2000]

        content = srs_content or readme_content
        if not content:
            return _plantuml_stub("usecase", "No requirements docs found")

        prompt = (
            "Generate a PlantUML use case diagram from these requirements. "
            "Output ONLY PlantUML syntax starting with @startuml and ending "
            "with @enduml. Keep it concise (max 15 use cases).\n\n%s" % content
        )

        result = self._llm_generate(prompt)
        if result:
            return _clean_plantuml(result)

        return _plantuml_stub("usecase", "LLM generation unavailable")

    def generate_object_diagram(self, classes=None, context=""):
        """Generate PlantUML object diagram showing class instances."""
        if classes is None:
            classes = self.analyzer.extract_all_classes()

        class_summary = "\n".join(
            "- %s (attrs: %s)" % (
                c["name"],
                ", ".join(a["name"] for a in c.get("attributes", [])[:5])
            )
            for c in classes[:15]
        )

        prompt = (
            "Generate a PlantUML object diagram showing example instances "
            "of these classes with realistic field values. Output ONLY "
            "PlantUML syntax (@startuml to @enduml).\n\nClasses:\n%s\n\n%s"
            % (class_summary, context[:500])
        )

        result = self._llm_generate(prompt)
        if result:
            return _clean_plantuml(result)

        return _plantuml_stub("object", "LLM generation unavailable")

    def generate_deployment_diagram(self, infra_files=None):
        """Generate PlantUML deployment diagram from infrastructure files."""
        infra_content = ""
        if infra_files is None:
            # Auto-detect infrastructure files
            patterns = [
                "Dockerfile", "docker-compose.yml", "docker-compose.yaml",
                "*.k8s.yml", "*.k8s.yaml", "deployment.yml",
                "Procfile", ".github/workflows/*.yml",
            ]
            for pattern in patterns:
                for f in self.project_root.glob(pattern):
                    try:
                        infra_content += "\n--- %s ---\n" % f.name
                        infra_content += f.read_text(
                            encoding="utf-8", errors="replace"
                        )[:1000]
                    except OSError:
                        pass

        if not infra_content:
            # Generate based on project structure
            infra_content = "Python project with modules: %s" % ", ".join(
                d.name for d in self.project_root.iterdir()
                if d.is_dir() and not d.name.startswith(".")
            )

        prompt = (
            "Generate a PlantUML deployment diagram for this project. "
            "Output ONLY PlantUML syntax (@startuml to @enduml).\n\n%s"
            % infra_content[:3000]
        )

        result = self._llm_generate(prompt)
        if result:
            return _clean_plantuml(result)

        return _plantuml_stub("deployment", "LLM generation unavailable")

    def generate_communication_diagram(self, dep_graph=None, context=""):
        """Generate PlantUML communication diagram."""
        if dep_graph is None:
            dep_graph = self.analyzer.build_dependency_graph()

        module_summary = "\n".join(
            "- %s depends on: %s" % (mod, ", ".join(sorted(deps)[:5]))
            for mod, deps in sorted(dep_graph.items())[:20]
        )

        prompt = (
            "Generate a PlantUML communication diagram showing how these "
            "modules interact. Output ONLY PlantUML syntax "
            "(@startuml to @enduml).\n\nModules:\n%s\n\n%s"
            % (module_summary, context[:500])
        )

        result = self._llm_generate(prompt)
        if result:
            return _clean_plantuml(result)

        return _plantuml_stub("communication", "LLM generation unavailable")

    def generate_composite_structure_diagram(self, classes=None, context=""):
        """Generate PlantUML composite structure diagram."""
        if classes is None:
            classes = self.analyzer.extract_all_classes()

        class_summary = "\n".join(
            "- %s: methods=%s, attrs=%s" % (
                c["name"],
                ", ".join(m["name"] for m in c.get("methods", [])[:5]),
                ", ".join(a["name"] for a in c.get("attributes", [])[:5]),
            )
            for c in classes[:10]
        )

        prompt = (
            "Generate a PlantUML composite structure diagram showing "
            "internal structure of these classes (ports, parts, connectors). "
            "Output ONLY PlantUML syntax (@startuml to @enduml).\n\n%s\n\n%s"
            % (class_summary, context[:500])
        )

        result = self._llm_generate(prompt)
        if result:
            return _clean_plantuml(result)

        return _plantuml_stub("composite", "LLM generation unavailable")

    def generate_interaction_overview(self, call_chains=None, context=""):
        """Generate PlantUML interaction overview diagram."""
        if call_chains is None:
            call_chains = []
            for py_file in self.project_root.rglob("*.py"):
                rel = str(py_file.relative_to(self.project_root))
                if any(skip in rel for skip in [
                    "__pycache__", ".venv", "test"
                ]):
                    continue
                chains = self.analyzer.extract_call_chains(py_file)
                call_chains.extend(chains[:10])
                if len(call_chains) >= 40:
                    break

        chain_summary = "\n".join(
            "- %s calls %s" % (c["caller"], c["callee"])
            for c in call_chains[:20]
        )

        prompt = (
            "Generate a PlantUML interaction overview diagram (activity "
            "diagram with interaction fragments) for these call flows. "
            "Output ONLY PlantUML syntax (@startuml to @enduml).\n\n%s\n\n%s"
            % (chain_summary, context[:500])
        )

        result = self._llm_generate(prompt)
        if result:
            return _clean_plantuml(result)

        return _plantuml_stub("interaction", "LLM generation unavailable")

    # ------------------------------------------------------------------
    # Orchestration
    # ------------------------------------------------------------------

    def generate_all(self, scope="project"):
        """Generate all applicable diagrams.

        Returns dict: {diagram_name: syntax_string}
        """
        results = {}

        # Tier 1: Always generate (AST-based, fast)
        try:
            classes = self.analyzer.extract_all_classes()
            dep_graph = self.analyzer.build_dependency_graph()

            results["class-diagram"] = self.generate_class_diagram(classes)
            results["package-diagram"] = self.generate_package_diagram(
                dep_graph
            )
            results["component-diagram"] = self.generate_component_diagram(
                dep_graph
            )
        except Exception as e:
            logger.warning("Tier 1 diagram generation failed: %s", e)

        # Tier 2: AST + LLM (may fail gracefully)
        try:
            results["sequence-diagram"] = self.generate_sequence_diagram()
        except Exception as e:
            logger.debug("Sequence diagram failed: %s", e)

        # Tier 3: LLM-powered (best-effort)
        for name, method in [
            ("usecase-diagram", self.generate_usecase_diagram),
            ("object-diagram", lambda: self.generate_object_diagram(classes)),
            ("deployment-diagram", self.generate_deployment_diagram),
            ("communication-diagram",
             lambda: self.generate_communication_diagram(dep_graph)),
        ]:
            try:
                results[name] = method() if not callable(method) else method()
            except Exception as e:
                logger.debug("%s failed: %s", name, e)

        return results

    def save_diagram(self, name, syntax, format="md"):
        """Save diagram to docs/uml/{name}.md with proper markdown wrapper.

        Returns the output file path.
        """
        self.output_dir.mkdir(parents=True, exist_ok=True)

        now = datetime.now().strftime("%Y-%m-%d")
        title = name.replace("-", " ").title()

        # Determine if Mermaid or PlantUML
        is_plantuml = syntax.strip().startswith("@startuml")
        lang = "plantuml" if is_plantuml else "mermaid"

        content_lines = [
            "# %s" % title,
            "",
            "> Auto-generated by Claude Workflow Engine | "
            "Last updated: %s" % now,
            "",
        ]

        content_lines.append("```%s" % lang)
        content_lines.append(syntax)
        content_lines.append("```")
        content_lines.append("")
        content_lines.append("## Notes")
        content_lines.append("")
        content_lines.append("- Generated from: %s" % str(self.project_root))
        content_lines.append("- Scope: Full project")
        content_lines.append("")

        out_path = self.output_dir / ("%s.md" % name)
        out_path.write_text("\n".join(content_lines), encoding="utf-8")

        logger.info("Saved diagram: %s", out_path)
        return str(out_path)

    # ------------------------------------------------------------------
    # LLM helpers (lazy import)
    # ------------------------------------------------------------------

    def _llm_generate(self, prompt):
        """Call LLM via llm_call.py (lazy import, graceful fallback)."""
        try:
            from langgraph_engine.llm_call import llm_call
            result = llm_call(prompt, model="fast", timeout=60)
            return result
        except ImportError:
            logger.debug("llm_call not available, skipping LLM generation")
            return None
        except Exception as e:
            logger.debug("LLM call failed: %s", e)
            return None

    def _llm_enrich(self, diagram_syntax, diagram_type, context):
        """Use LLM to enrich an AST-generated diagram."""
        prompt = (
            "Improve this %s Mermaid diagram by adding better labels "
            "and notes. Output ONLY the improved Mermaid syntax, "
            "no markdown fences.\n\nCurrent diagram:\n%s\n\nContext:\n%s"
            % (diagram_type, diagram_syntax, context[:1000])
        )
        return self._llm_generate(prompt)


# ======================================================================
# Kroki Renderer
# ======================================================================

class KrokiRenderer:
    """Render PlantUML/Mermaid via Kroki.io free API."""

    KROKI_URL = "https://kroki.io"

    def render(self, diagram_text, diagram_type="plantuml",
               output_format="svg"):
        """Render diagram via Kroki.io API.

        Args:
            diagram_text: PlantUML or Mermaid source text.
            diagram_type: "plantuml", "mermaid", etc.
            output_format: "svg", "png", etc.

        Returns bytes or None on failure.
        """
        try:
            import requests
        except ImportError:
            logger.warning("requests not available for Kroki rendering")
            return None

        url = "%s/%s/%s" % (self.KROKI_URL, diagram_type, output_format)

        try:
            resp = requests.post(
                url,
                data=diagram_text.encode("utf-8"),
                headers={"Content-Type": "text/plain"},
                timeout=30,
            )
            if resp.status_code == 200:
                return resp.content
            logger.warning(
                "Kroki API returned %d: %s",
                resp.status_code, resp.text[:200]
            )
            return None
        except Exception as e:
            logger.warning("Kroki rendering failed: %s", e)
            return None

    def render_to_file(self, diagram_text, output_path,
                       diagram_type="plantuml", output_format="svg"):
        """Render and save to file. Returns path or None."""
        data = self.render(diagram_text, diagram_type, output_format)
        if data is None:
            return None

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(data)
        return str(output_path)


# ======================================================================
# Utility functions
# ======================================================================

def _simplify_type(ast_dump):
    """Convert AST dump string to readable type name."""
    if not ast_dump:
        return ""
    # Handle common patterns from ast.dump()
    s = ast_dump
    # Name(id='str') -> str
    if "Name(id='" in s:
        start = s.find("id='") + 4
        end = s.find("'", start)
        if end > start:
            return s[start:end]
    # Constant(value=...) -> skip
    if "Constant" in s:
        return ""
    # Subscript patterns -> simplify
    if len(s) > 30:
        return ""
    return ""


def _clean_mermaid(text):
    """Clean LLM output to extract Mermaid syntax."""
    if not text:
        return ""
    # Remove markdown fences if present
    text = text.strip()
    if text.startswith("```mermaid"):
        text = text[len("```mermaid"):].strip()
    if text.startswith("```"):
        text = text[3:].strip()
    if text.endswith("```"):
        text = text[:-3].strip()
    return text


def _clean_plantuml(text):
    """Clean LLM output to extract PlantUML syntax."""
    if not text:
        return ""
    text = text.strip()
    # Remove markdown fences
    if text.startswith("```plantuml"):
        text = text[len("```plantuml"):].strip()
    if text.startswith("```"):
        text = text[3:].strip()
    if text.endswith("```"):
        text = text[:-3].strip()
    # Ensure @startuml/@enduml wrapper
    if not text.startswith("@startuml"):
        text = "@startuml\n" + text
    if not text.endswith("@enduml"):
        text = text + "\n@enduml"
    return text


def _plantuml_stub(diagram_type, message):
    """Generate a PlantUML stub with a note."""
    return (
        "@startuml\nnote \"%s: %s\" as N1\n@enduml"
        % (diagram_type, message)
    )
