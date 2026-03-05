"""
Path Resolver for Claude Insight.

Provides portable, cross-platform data directory resolution for all
services that need to read or write data files. Supports three operating
modes based on a priority chain:

Priority:
    0. CLAUDE_INSIGHT_DATA_DIR environment variable (set by IDE launcher)
    1. ~/.claude/memory/ (present when Claude Memory System is installed)
    2. ./data/ within the project root (portable/standalone mode)

Module-level singletons:
    path_resolver (PathResolver): Global shared instance.

Convenience functions (all delegate to path_resolver):
    get_sessions_dir() -> Path
    get_logs_dir() -> Path
    get_config_dir() -> Path
    get_data_dir(subdir=None) -> Path
    get_file(*parts) -> Path
    is_global_mode() -> bool
    is_local_mode() -> bool
    get_mode_info() -> dict
    get_scripts_dir() -> Path
    get_policies_dir() -> Path
    get_session_logs_dir() -> Path

Classes:
    PathResolver: Data directory resolver with three-tier priority fallback.
"""

from pathlib import Path
import os


class PathResolver:
    """Resolve data storage paths for Claude Insight with a three-tier priority chain.

    Chooses the base data directory according to the following priority:
    0. CLAUDE_INSIGHT_DATA_DIR env var (IDE launcher override)
    1. ~/.claude/memory/ if it exists (Claude Memory System installed)
    2. <project_root>/data/ (portable standalone mode)

    In modes 0 and 2 (IDE and LOCAL), creates the required subdirectory
    structure automatically.

    Attributes:
        project_root (Path): Absolute path to the project root (parent of src/).
        global_memory (Path): Standard global memory path (~/.claude/memory).
        base_dir (Path): The resolved data root directory for this instance.
        mode (str): Operating mode string - 'IDE', 'GLOBAL', or 'LOCAL'.
        has_global_memory (bool): True when using the global memory directory.
    """

    def __init__(self):
        """Initialize PathResolver and resolve the operating mode and base_dir."""
        self.project_root = Path(__file__).parent.parent.parent
        self.global_memory = Path.home() / '.claude' / 'memory'

        # Priority 0: Environment variable (set by IDE)
        env_data_dir = os.environ.get('CLAUDE_INSIGHT_DATA_DIR')
        if env_data_dir:
            self.base_dir = Path(env_data_dir)
            self.mode = "IDE"
            self.has_global_memory = False
            self._ensure_local_structure()
        # Priority 1: Global ~/.claude/memory
        elif self.global_memory.exists():
            self.base_dir = self.global_memory
            self.mode = "GLOBAL"
            self.has_global_memory = True
        # Priority 2: Local ./data/
        else:
            self.base_dir = self.project_root / 'data'
            self.mode = "LOCAL"
            self.has_global_memory = False
            self._ensure_local_structure()

    def _ensure_local_structure(self):
        """Create the required local data directory structure under base_dir.

        Creates the following subdirectories (parents=True, exist_ok=True):
        sessions/, logs/, config/, anomalies/, forecasts/, performance/.

        Returns:
            None
        """
        dirs = [
            self.base_dir / 'sessions',
            self.base_dir / 'logs',
            self.base_dir / 'config',
            self.base_dir / 'anomalies',
            self.base_dir / 'forecasts',
            self.base_dir / 'performance',
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)

    def get_sessions_dir(self):
        """Get sessions directory"""
        return self.base_dir / 'sessions'

    def get_logs_dir(self):
        """Get logs directory"""
        return self.base_dir / 'logs'

    def get_scripts_dir(self):
        """Get scripts directory (hooks live here, NOT in memory/current/)"""
        return Path.home() / '.claude' / 'scripts'

    def get_policies_dir(self):
        """Get policies directory"""
        return Path.home() / '.claude' / 'policies'

    def get_session_logs_dir(self):
        """Get per-session logs directory (flow-trace.json, etc.)"""
        return self.base_dir / 'logs' / 'sessions'

    def get_config_dir(self):
        """Get config directory"""
        return self.base_dir / 'config'

    def get_data_dir(self, subdir=None):
        """Get data directory (optionally with subdirectory)"""
        if subdir:
            return self.base_dir / subdir
        return self.base_dir

    def get_file(self, *parts):
        """Get file path within data directory"""
        return self.base_dir.joinpath(*parts)

    def is_global_mode(self):
        """Check if using global ~/.claude/memory"""
        return self.mode == "GLOBAL"

    def is_local_mode(self):
        """Check if using local ./data/"""
        return self.mode == "LOCAL"

    def get_mode_info(self):
        """Get current mode information"""
        return {
            'mode': self.mode,
            'base_dir': str(self.base_dir),
            'has_global_memory': self.has_global_memory
        }


# Global instance
path_resolver = PathResolver()


# Convenience functions

def get_sessions_dir():
    """Return the sessions directory path from the global PathResolver instance.

    Returns:
        Path: Absolute path to the sessions directory.
    """
    return path_resolver.get_sessions_dir()


def get_logs_dir():
    """Return the logs directory path from the global PathResolver instance.

    Returns:
        Path: Absolute path to the logs directory.
    """
    return path_resolver.get_logs_dir()


def get_config_dir():
    """Return the config directory path from the global PathResolver instance.

    Returns:
        Path: Absolute path to the config directory.
    """
    return path_resolver.get_config_dir()


def get_data_dir(subdir=None):
    """Return the data root (optionally with a subdirectory appended).

    Args:
        subdir (str or None): Optional subdirectory name to append to the
            base data directory.

    Returns:
        Path: Absolute path to the data directory (or subdirectory).
    """
    return path_resolver.get_data_dir(subdir)


def get_file(*parts):
    """Return a file path constructed from the data root and the given parts.

    Args:
        *parts: Path components to join after the base data directory.

    Returns:
        Path: Absolute file path under the data directory.
    """
    return path_resolver.get_file(*parts)


def is_global_mode():
    """Return True when the global ~/.claude/memory directory is in use.

    Returns:
        bool: True if mode is 'GLOBAL', False otherwise.
    """
    return path_resolver.is_global_mode()


def is_local_mode():
    """Return True when the local ./data/ directory is in use.

    Returns:
        bool: True if mode is 'LOCAL', False otherwise.
    """
    return path_resolver.is_local_mode()


def get_mode_info():
    """Return a dictionary describing the current path resolver mode.

    Returns:
        dict: With keys:
            mode (str): 'IDE', 'GLOBAL', or 'LOCAL'.
            base_dir (str): String representation of the base directory.
            has_global_memory (bool): Whether global memory is available.
    """
    return path_resolver.get_mode_info()


def get_scripts_dir():
    """Return the scripts directory path from the global PathResolver instance.

    Returns:
        Path: Absolute path to ~/.claude/scripts/.
    """
    return path_resolver.get_scripts_dir()


def get_policies_dir():
    """Return the policies directory path from the global PathResolver instance.

    Returns:
        Path: Absolute path to ~/.claude/policies/.
    """
    return path_resolver.get_policies_dir()


def get_session_logs_dir():
    """Return the per-session logs directory path from the global PathResolver.

    Returns:
        Path: Absolute path to the session logs directory (logs/sessions/).
    """
    return path_resolver.get_session_logs_dir()
