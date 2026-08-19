#!/usr/bin/env bash
# Apply pending changesets (or publish the current version), then tag and create a GitHub Release.
# Usage: scripts/gh-release.sh [--dry-run] [--current]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

DRY_RUN=0
CURRENT=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    --current) CURRENT=1 ;;
    *)
      echo "Usage: scripts/gh-release.sh [--dry-run] [--current]" >&2
      exit 2
      ;;
  esac
done

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

run() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf '+'
    printf ' %q' "$@"
    printf '\n'
  else
    "$@"
  fi
}

publish_tag() {
  local version="$1"
  local tag="v${version}"
  local commit_bump="$2"

  if [[ "$DRY_RUN" -eq 0 ]]; then
    if git rev-parse "$tag" >/dev/null 2>&1; then
      echo "tag already exists: ${tag}" >&2
      exit 1
    fi
  fi

  echo "version: ${version}"
  echo "tag:     ${tag}"

  run python3 -m build
  shopt -s nullglob
  local assets=(dist/"git_calculator-${version}"-*.whl dist/"git-calculator-${version}.tar.gz" dist/"git_calculator-${version}.tar.gz")
  if [[ ${#assets[@]} -eq 0 ]]; then
    if [[ "$DRY_RUN" -eq 1 ]]; then
      assets=("dist/git_calculator-${version}-*.whl" "dist/git_calculator-${version}.tar.gz")
    else
      echo "no dist artifacts for ${version}" >&2
      exit 1
    fi
  fi

  if [[ "$commit_bump" -eq 1 ]]; then
    run git add package.json pyproject.toml CHANGELOG.md .changeset
    run git commit -m "chore: release ${tag}"
  fi
  run git tag -a "$tag" -m "$tag"
  if [[ "$commit_bump" -eq 1 ]]; then
    run git push origin HEAD
  fi
  run git push origin "$tag"

  local notes_file
  notes_file="$(mktemp)"
  trap 'rm -f "$notes_file"' RETURN
  if [[ "$DRY_RUN" -eq 1 ]]; then
    run gh release create "$tag" --title "$tag" --notes-file CHANGELOG.md "${assets[@]}"
  else
    changelog_notes "$version" >"$notes_file"
    gh release create "$tag" --title "$tag" --notes-file "$notes_file" "${assets[@]}"
  fi
}

if [[ "$CURRENT" -eq 1 && ${#CHANGESET_FILES[@]} -gt 0 ]]; then
  echo "pending changesets exist; omit --current so they can bump the version" >&2
  exit 1
fi

if [[ "$CURRENT" -eq 0 && ${#CHANGESET_FILES[@]} -eq 0 ]]; then
  echo "no pending changesets." >&2
  echo "first GitHub Release of the version already on main: scripts/gh-release.sh --current" >&2
  echo "later bumps: npx changeset (on the PR), merge, then scripts/gh-release.sh" >&2
  echo "see docs/releasing.md" >&2
  exit 1
fi

if [[ "$DRY_RUN" -eq 0 && -n "$(git status --porcelain)" ]]; then
  echo "working tree is not clean" >&2
  exit 1
fi

if [[ "$CURRENT" -eq 1 ]]; then
  publish_tag "$(read_current_version)" 0
  exit 0
fi

echo "pending changesets: ${#CHANGESET_FILES[@]}"
echo "current version:    $(read_current_version)"
echo "next version:       $(preview_next_version)"

if [[ "$DRY_RUN" -eq 1 ]]; then
  run npx changeset version
  publish_tag "$(preview_next_version)" 1
  exit 0
fi

npx changeset version
publish_tag "$(sync_pyproject_version)" 1
