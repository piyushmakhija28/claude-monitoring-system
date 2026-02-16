#!/usr/bin/env python
"""
Version Bumping Script for Claude Insight
Supports semantic versioning (MAJOR.MINOR.PATCH)
"""

import sys
import re
from pathlib import Path


def read_version():
    """Read current version from VERSION file"""
    version_file = Path(__file__).parent.parent / "VERSION"
    if not version_file.exists():
        return "0.0.0"
    return version_file.read_text().strip()


def parse_version(version_str):
    """Parse version string into (major, minor, patch)"""
    match = re.match(r'^(\d+)\.(\d+)\.(\d+)$', version_str)
    if not match:
        raise ValueError(f"Invalid version format: {version_str}")
    return tuple(map(int, match.groups()))


def format_version(major, minor, patch):
    """Format version tuple as string"""
    return f"{major}.{minor}.{patch}"


def bump_version(bump_type):
    """Bump version based on type (major, minor, patch)"""
    current = read_version()
    major, minor, patch = parse_version(current)

    if bump_type == "major":
        major += 1
        minor = 0
        patch = 0
    elif bump_type == "minor":
        minor += 1
        patch = 0
    elif bump_type == "patch":
        patch += 1
    else:
        raise ValueError(f"Invalid bump type: {bump_type}. Use major, minor, or patch")

    new_version = format_version(major, minor, patch)

    # Write new version
    version_file = Path(__file__).parent.parent / "VERSION"
    version_file.write_text(new_version)

    return current, new_version


def main():
    """Main entry point"""
    if len(sys.argv) != 2:
        print("Usage: python bump-version.py [major|minor|patch]")
        print(f"Current version: {read_version()}")
        sys.exit(1)

    bump_type = sys.argv[1].lower()

    try:
        old_version, new_version = bump_version(bump_type)
        print(f"✅ Version bumped: {old_version} → {new_version}")
        print(f"📝 Next steps:")
        print(f"   1. git add VERSION")
        print(f"   2. git commit -m \"chore: bump version to {new_version}\"")
        print(f"   3. git tag v{new_version}")
        print(f"   4. git push origin main --tags")
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
