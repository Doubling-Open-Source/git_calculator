#!/usr/bin/env bash
# Apply pending changesets, then tag and create a GitHub Release.
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
need npx

if [[ "$DRY_RUN" -eq 0 ]]; then
  gh auth status >/dev/null
fi

changeset_files() {
  find .changeset -maxdepth 1 -type f -name '*.md' ! -name 'README.md' 2>/dev/null | sort
}

mapfile -t CHANGESET_FILES < <(changeset_files)
if [[ ${#CHANGESET_FILES[@]} -eq 0 ]]; then
  echo "no pending changesets; add one with: npx changeset" >&2
  exit 1
fi

read_current_version() {
  python3 - <<'PY'
import json
from pathlib import Path

print(json.loads(Path("package.json").read_text())["version"])
PY
}

preview_next_version() {
  python3 - <<'PY'
import json
import re
from pathlib import Path

pkg = json.loads(Path("package.json").read_text())
name = pkg["name"]
major, minor, patch = (int(p) for p in pkg["version"].split(".", 2))
rank = {"patch": 1, "minor": 2, "major": 3}
bump = 0
frontmatter = re.compile(r"^---\n(.*?)\n---", re.S)
for path in Path(".changeset").glob("*.md"):
    if path.name == "README.md":
        continue
    match = frontmatter.match(path.read_text())
    if not match:
        raise SystemExit(f"changeset missing frontmatter: {path}")
    for line in match.group(1).splitlines():
        line = line.strip().strip(",")
        if f'"{name}":' not in line and f"'{name}':" not in line:
            continue
        kind = line.split(":", 1)[1].strip().strip("'\"").lower()
        bump = max(bump, rank.get(kind, 0))
if bump == 0:
    raise SystemExit(f"no {name} bump in pending changesets")
if bump == 3:
    major, minor, patch = major + 1, 0, 0
elif bump == 2:
    minor, patch = minor + 1, 0
else:
    patch += 1
print(f"{major}.{minor}.{patch}")
PY
}

sync_pyproject_version() {
  python3 - <<'PY'
import json
import re
from pathlib import Path

version = json.loads(Path("package.json").read_text())["version"]
path = Path("pyproject.toml")
text = path.read_text()
updated, n = re.subn(
    r'(?m)^version = "[^"]+"',
    f'version = "{version}"',
    text,
    count=1,
)
if n != 1:
    raise SystemExit("could not update pyproject.toml version")
path.write_text(updated)
print(version)
PY
}

changelog_notes() {
  VERSION="$1" python3 - <<'PY'
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
}

CURRENT="$(read_current_version)"
NEXT="$(preview_next_version)"
echo "pending changesets: ${#CHANGESET_FILES[@]}"
echo "current version:    ${CURRENT}"
echo "next version:       ${NEXT}"

run() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf '+'
    printf ' %q' "$@"
    printf '\n'
  else
    "$@"
  fi
}

if [[ "$DRY_RUN" -eq 1 ]]; then
  TAG="v${NEXT}"
  run npx changeset version
  run python3 -m build
  run git add package.json pyproject.toml CHANGELOG.md .changeset
  run git commit -m "chore: release ${TAG}"
  run git tag -a "$TAG" -m "$TAG"
  run git push origin HEAD
  run git push origin "$TAG"
  run gh release create "$TAG" --title "$TAG" --notes-file CHANGELOG.md \
    "dist/git_calculator-${NEXT}-*.whl" "dist/git_calculator-${NEXT}.tar.gz"
  exit 0
fi

if [[ -n "$(git status --porcelain)" ]]; then
  echo "working tree is not clean" >&2
  exit 1
fi

npx changeset version
VERSION="$(sync_pyproject_version)"
TAG="v${VERSION}"

if git rev-parse "$TAG" >/dev/null 2>&1; then
  echo "tag already exists: ${TAG}" >&2
  exit 1
fi

python3 -m build
shopt -s nullglob
ASSETS=(dist/"git_calculator-${VERSION}"-*.whl dist/"git-calculator-${VERSION}.tar.gz" dist/"git_calculator-${VERSION}.tar.gz")
if [[ ${#ASSETS[@]} -eq 0 ]]; then
  echo "no dist artifacts for ${VERSION}" >&2
  exit 1
fi

NOTES_FILE="$(mktemp)"
trap 'rm -f "$NOTES_FILE"' EXIT
changelog_notes "$VERSION" >"$NOTES_FILE"

git add package.json pyproject.toml CHANGELOG.md .changeset
git commit -m "chore: release ${TAG}"
git tag -a "$TAG" -m "$TAG"
git push origin HEAD
git push origin "$TAG"
gh release create "$TAG" \
  --title "$TAG" \
  --notes-file "$NOTES_FILE" \
  "${ASSETS[@]}"
