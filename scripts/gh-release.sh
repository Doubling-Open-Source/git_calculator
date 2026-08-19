#!/usr/bin/env bash
# Create a GitHub Release for the version in pyproject.toml.
# Usage: scripts/gh-release.sh [--dry-run]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

DRY_RUN=0
if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=1
elif [[ "${1:-}" != "" ]]; then
  echo "Usage: scripts/gh-release.sh [--dry-run]" >&2
  exit 2
fi

need() {
  command -v "$1" >/dev/null || {
    echo "missing required command: $1" >&2
    exit 2
  }
}

need gh
need git
need python3

if [[ "$DRY_RUN" -eq 0 ]]; then
  gh auth status >/dev/null
fi

VERSION="$(python3 - <<'PY'
import tomllib
from pathlib import Path

data = tomllib.loads(Path("pyproject.toml").read_text())
print(data["project"]["version"])
PY
)"
TAG="v${VERSION}"

NOTES="$(VERSION="$VERSION" python3 - <<'PY'
import os
from pathlib import Path

version = os.environ["VERSION"]
heading = f"## {version}"
path = Path("CHANGELOG.md")
if not path.is_file():
    print(f"Release {version}")
    raise SystemExit(0)
lines = path.read_text().splitlines()
start = None
for i, line in enumerate(lines):
    if line.strip() == heading:
        start = i + 1
        break
if start is None:
    print(f"Release {version}")
    raise SystemExit(0)
body = []
for line in lines[start:]:
    if line.startswith("## "):
        break
    body.append(line)
text = "\n".join(body).strip()
print(text if text else f"Release {version}")
PY
)"

echo "version: ${VERSION}"
echo "tag:     ${TAG}"

run() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf '+'
    printf ' %q' "$@"
    printf '\n'
  else
    "$@"
  fi
}

if [[ "$DRY_RUN" -eq 0 ]]; then
  if [[ -n "$(git status --porcelain)" ]]; then
    echo "working tree is not clean" >&2
    exit 1
  fi
  if git rev-parse "$TAG" >/dev/null 2>&1; then
    echo "tag already exists: ${TAG}" >&2
    exit 1
  fi
fi

NOTES_FILE="$(mktemp)"
trap 'rm -f "$NOTES_FILE"' EXIT
printf '%s\n' "$NOTES" >"$NOTES_FILE"

run python3 -m build
shopt -s nullglob
ASSETS=(dist/"git_calculator-${VERSION}"-*.whl dist/"git-calculator-${VERSION}.tar.gz" dist/"git_calculator-${VERSION}.tar.gz")
if [[ ${#ASSETS[@]} -eq 0 ]]; then
  if [[ "$DRY_RUN" -eq 1 ]]; then
    ASSETS=("dist/git_calculator-${VERSION}-*.whl" "dist/git_calculator-${VERSION}.tar.gz")
  else
    echo "no dist artifacts for ${VERSION}" >&2
    exit 1
  fi
fi

run git tag -a "$TAG" -m "$TAG"
run git push origin "$TAG"
run gh release create "$TAG" \
  --title "$TAG" \
  --notes-file "$NOTES_FILE" \
  "${ASSETS[@]}"
