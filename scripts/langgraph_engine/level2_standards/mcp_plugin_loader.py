"""
MCP Plugin Loader - Plugin-based MCP discovery and management system.

Provides dynamic discovery and loading of MCP server plugins from the
~/.claude/mcp/plugins/ directory structure. Each plugin is independently
managed with its own manifest.json defining capabilities and configuration.

Plugin Directory Structure:
  ~/.claude/mcp/plugins/
    ├── filesystem/
    │   ├── manifest.json
    │   ├── __init__.py
    │   └── impl.py
    ├── github/ (future)
    │   ├── manifest.json
    │   └── impl.py
    └── [other plugins]/

Each plugin must have:
  - manifest.json: Plugin metadata and capabilities
  - impl.py: Implementation (class matching class_name in manifest)
"""

import json
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import sys as _sys

    _sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))
    from utils.path_resolver import get_claude_home

    _MCP_PLUGINS_DIR = get_claude_home() / "mcp" / "plugins"
except ImportError:
    _MCP_PLUGINS_DIR = Path.home() / ".claude" / "mcp" / "plugins"


class MCPPluginError(Exception):
    """Base exception for MCP plugin operations."""

    pass


class PluginManifestError(MCPPluginError):
    """Error loading or parsing plugin manifest."""

    pass


class PluginImplementationError(MCPPluginError):
    """Error loading or executing plugin implementation."""

    pass


class MCPPluginInstance(ABC):
    """Base class for all MCP plugin implementations.

    Each plugin module must provide a class that inherits from this.
    """

    @abstractmethod
    def get_capability_metadata(self) -> Dict[str, Any]:
        """Return metadata about this plugin's capabilities.

        Returns:
            Dict with 'name', 'version', 'description', 'capabilities' list
        """
        pass


class PluginManifest:
    """Represents a plugin's manifest.json metadata."""

    def __init__(self, data: Dict[str, Any], plugin_path: Path):
        """Initialize manifest from parsed JSON data.

        Args:
            data: Parsed manifest.json content
            plugin_path: Path to plugin directory
        """
        self.data = data
        self.plugin_path = plugin_path
        self._validate()

    def _validate(self) -> None:
        """Validate required manifest fields."""
        required = ["name", "short_name", "version", "enabled", "description"]
        missing = [f for f in required if f not in self.data]
        if missing:
            raise PluginManifestError(f"Missing required fields: {missing}")

    @property
    def name(self) -> str:
        return self.data.get("name")

    @property
    def short_name(self) -> str:
        return self.data.get("short_name")

    @property
    def version(self) -> str:
        return self.data.get("version")

    @property
    def enabled(self) -> bool:
        return self.data.get("enabled", True)

    @property
    def description(self) -> str:
        return self.data.get("description")

    @property
    def module(self) -> str:
        """Module filename (e.g., 'impl.py')."""
        return self.data.get("module", "impl.py")

    @property
    def class_name(self) -> str:
        """Python class name to instantiate."""
        return self.data.get("class_name", "MCP")

    @property
    def capabilities(self) -> List[Dict]:
        """List of capabilities this plugin provides."""
        return self.data.get("capabilities", [])

    @property
    def configuration(self) -> Dict:
        """Plugin-specific configuration."""
        return self.data.get("configuration", {})

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "short_name": self.short_name,
            "version": self.version,
            "enabled": self.enabled,
            "description": self.description,
            "capabilities": self.capabilities,
            "status": "ENABLED" if self.enabled else "DISABLED",
            "path": str(self.plugin_path),
        }


class MCPPluginLoader:
    """Dynamically discovers and loads MCP server plugins.

    Scans ~/.claude/mcp/plugins/ for plugin directories, loads manifest.json
    from each, and provides methods to dynamically instantiate and route to MCPs.
    """

    def __init__(self, plugins_path: Optional[str] = None):
        """Initialize plugin loader.

        Args:
            plugins_path: Path to plugins directory. Defaults to ~/.claude/mcp/plugins/
        """
        if plugins_path is None:
            self.plugins_path = _MCP_PLUGINS_DIR
        else:
            self.plugins_path = Path(plugins_path)

        self._cache: Dict[str, Any] = {}  # Cache loaded manifests and instances
        self._logger = self._setup_logger()

    def _setup_logger(self):
        """Setup simple logging."""

        class SimpleLogger:
            @staticmethod
            def debug(msg: str) -> None:
                pass  # Suppress debug output

            @staticmethod
            def info(msg: str) -> None:
                print(f"[MCP] {msg}", file=sys.stderr)

            @staticmethod
            def warning(msg: str) -> None:
                print(f"[MCP WARNING] {msg}", file=sys.stderr)

            @staticmethod
            def error(msg: str) -> None:
                print(f"[MCP ERROR] {msg}", file=sys.stderr)

        return SimpleLogger()

    def discover_plugins(self) -> Dict[str, PluginManifest]:
        """Scan plugins directory and load all manifest.json files.

        Returns:
            Dict mapping plugin names to PluginManifest objects

        Raises:
            MCPPluginError: If plugin discovery fails
        """
        if not self.plugins_path.exists():
            self._logger.warning(f"Plugins directory not found: {self.plugins_path}")
            return {}

        plugins = {}

        try:
            for plugin_dir in self.plugins_path.iterdir():
                if not plugin_dir.is_dir():
                    continue

                manifest_path = plugin_dir / "manifest.json"
                if not manifest_path.exists():
                    self._logger.debug(f"No manifest found in {plugin_dir}")
                    continue

                try:
                    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
                    manifest = PluginManifest(manifest_data, plugin_dir)

                    plugin_name = manifest.short_name
                    plugins[plugin_name] = manifest

                    self._logger.debug(f"Discovered plugin: {plugin_name} v{manifest.version}")

                except (json.JSONDecodeError, PluginManifestError) as e:
                    self._logger.warning(f"Failed to load {manifest_path}: {e}")
                    continue

        except Exception as e:
            self._logger.error(f"Plugin discovery failed: {e}")
            raise MCPPluginError(f"Failed to discover plugins: {e}")

        return plugins

    def load_plugin(self, plugin_name: str) -> MCPPluginInstance:
        """Load and instantiate a specific plugin.

        Args:
            plugin_name: Short name of plugin (e.g., 'filesystem')

        Returns:
            Instantiated plugin object

        Raises:
            PluginImplementationError: If plugin cannot be loaded
        """
        # Check cache first
        cache_key = f"instance_{plugin_name}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Discover all plugins to get manifest
        all_plugins = self.discover_plugins()
        if plugin_name not in all_plugins:
            raise PluginImplementationError(f"Plugin not found: {plugin_name}")

        manifest = all_plugins[plugin_name]

        if not manifest.enabled:
            raise PluginImplementationError(f"Plugin is disabled: {plugin_name}")

        # Load the implementation module
        plugin_dir = manifest.plugin_path
        module_path = plugin_dir / manifest.module

        if not module_path.exists():
            raise PluginImplementationError(f"Plugin implementation not found: {module_path}")

        try:
            # Add plugin dir to sys.path temporarily
            sys.path.insert(0, str(plugin_dir))

            # Import the module
            module_name = module_path.stem
            import importlib.util

            spec = importlib.util.spec_from_file_location(module_name, module_path)
            if spec is None or spec.loader is None:
                raise PluginImplementationError(f"Cannot load spec for {module_path}")

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Get the class and instantiate
            if not hasattr(module, manifest.class_name):
                raise PluginImplementationError(f"Class {manifest.class_name} not found in {module_name}")

            plugin_class = getattr(module, manifest.class_name)
            instance = plugin_class()

            # Cache it
            self._cache[cache_key] = instance

            self._logger.debug(f"Loaded plugin instance: {plugin_name}")
            return instance

        except PluginImplementationError:
            raise
        except Exception as e:
            raise PluginImplementationError(f"Failed to load {plugin_name}: {e}")

        finally:
            # Clean up sys.path
            if str(plugin_dir) in sys.path:
                sys.path.remove(str(plugin_dir))

    def get_available_mcps(self) -> List[Dict[str, Any]]:
        """Get list of all available MCPs with metadata.

        Returns:
            List of dicts with plugin info: name, version, description, capabilities, status
        """
        plugins = self.discover_plugins()
        result = []

        for name, manifest in plugins.items():
            result.append(
                {
                    "name": manifest.name,
                    "short_name": manifest.short_name,
                    "version": manifest.version,
                    "description": manifest.description,
                    "capabilities": manifest.capabilities,
                    "status": "ENABLED" if manifest.enabled else "DISABLED",
                    "path": str(manifest.plugin_path),
                }
            )

        return result

    def validate_plugin_manifest(self, manifest_path: Path) -> bool:
        """Validate a plugin manifest.json file.

        Args:
            manifest_path: Path to manifest.json

        Returns:
            True if valid, raises exception otherwise
        """
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            PluginManifest(data, manifest_path.parent)
            return True
        except Exception as e:
            self._logger.error(f"Manifest validation failed: {e}")
            raise PluginManifestError(f"Invalid manifest: {e}")

    def reload_all_plugins(self) -> Dict[str, str]:
        """Reload all plugins (clear cache and rediscover).

        Returns:
            Dict mapping plugin names to status (OK, ERROR)
        """
        self._cache.clear()
        result = {}

        try:
            plugins = self.discover_plugins()
            for name in plugins:
                try:
                    self.load_plugin(name)
                    result[name] = "OK"
                except Exception as e:
                    result[name] = f"ERROR: {e}"
        except Exception as e:
            result["_discovery"] = f"ERROR: {e}"

        return result

    def route_to_mcp(self, mcp_name: str, operation: str, **kwargs) -> Dict[str, Any]:
        """Route an operation to a specific MCP server.

        Args:
            mcp_name: Name of MCP to route to
            operation: Operation name (e.g., 'read_smart')
            **kwargs: Arguments for the operation

        Returns:
            Result from MCP operation

        Raises:
            MCPPluginError: If routing fails
        """
        try:
            plugin = self.load_plugin(mcp_name)

            if not hasattr(plugin, operation):
                raise MCPPluginError(f"Operation {operation} not found in {mcp_name}")

            operation_fn = getattr(plugin, operation)
            return operation_fn(**kwargs)

        except Exception as e:
            raise MCPPluginError(f"Failed to route to {mcp_name}.{operation}: {e}")


# Singleton instance for global access
_loader_instance: Optional[MCPPluginLoader] = None


def get_mcp_loader() -> MCPPluginLoader:
    """Get or create the singleton MCPPluginLoader instance."""
    global _loader_instance
    if _loader_instance is None:
        _loader_instance = MCPPluginLoader()
    return _loader_instance


def reset_mcp_loader() -> None:
    """Reset the singleton loader (for testing)."""
    global _loader_instance
    _loader_instance = None
