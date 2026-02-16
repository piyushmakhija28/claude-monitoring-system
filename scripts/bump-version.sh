#!/bin/bash
# Automatic Version Bump, Tag, and Release Script

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Run Python version bumper
python "$SCRIPT_DIR/bump-version.py" "$@"

# If successful and version was bumped
if [ $? -eq 0 ] && [ -n "$1" ]; then
    NEW_VERSION=$(cat "$PROJECT_ROOT/VERSION")

    cd "$PROJECT_ROOT"

    # Commit version change
    git add VERSION src/app.py templates/base.html
    git commit -m "chore: bump version to ${NEW_VERSION}"

    # Create and push tag
    git tag "v${NEW_VERSION}"
    git push origin main --tags

    echo "✅ Version ${NEW_VERSION} tagged and pushed!"
    echo ""

    # Auto-create GitHub Release using gh CLI
    echo "📦 Creating GitHub Release..."

    # Generate simple release notes
    PREV_TAG=$(git describe --tags --abbrev=0 HEAD^ 2>/dev/null || echo "")

    if [ -z "$PREV_TAG" ]; then
        NOTES="🎉 Initial release of Claude Insight v${NEW_VERSION}"
    else
        NOTES=$(cat <<EOF
🚀 Claude Insight v${NEW_VERSION}

## What's Changed
$(git log ${PREV_TAG}..HEAD --pretty=format:"- %s" --no-merges | head -20)

**Full Changelog**: https://github.com/piyushmakhija28/claude-insight/compare/${PREV_TAG}...v${NEW_VERSION}
EOF
)
    fi

    # Create release
    gh release create "v${NEW_VERSION}" \
        --title "Release v${NEW_VERSION}" \
        --notes "$NOTES"

    echo ""
    echo "🎉 Release created successfully!"
    echo "🔗 https://github.com/piyushmakhija28/claude-insight/releases/tag/v${NEW_VERSION}"
fi
