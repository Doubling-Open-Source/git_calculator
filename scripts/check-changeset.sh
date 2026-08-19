#!/usr/bin/env bash
# Fail when a PR changes product code/metadata without a new changeset file.
# Usage: scripts/check-changeset.sh [base-ref]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

BASE="${1:-origin/main}"

CHANGED="$(git diff --name-only "$BASE"...HEAD)"
if ! echo "$CHANGED" | grep -Eq '^(src/|pyproject\.toml$)'; then
  exit 0
fi

if echo "$CHANGED" | grep -E '^\.changeset/.+\.md$' | grep -v '^\.changeset/README\.md$' | grep -q .; then
  exit 0
fi

echo "product files changed without a changeset. Run: npx changeset" >&2
echo "or label the PR skip-changeset" >&2
exit 1
