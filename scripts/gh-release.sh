#!/usr/bin/env bash
# Apply pending changesets (or publish the current version), then tag and create a GitHub Release.
# Re-running is safe: if the GitHub Release is missing, the vX.Y.Z tag is moved to HEAD and reused.
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
need npm

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
import tomllib
from pathlib import Path

pkg = Path("package.json")
if pkg.is_file():
    print(json.loads(pkg.read_text())["version"])
else:
    print(tomllib.loads(Path("pyproject.toml").read_text())["project"]["version"])
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

changelog_notes() {
  VERSION="$1" python3 - <<'PY'
import os
import re
from pathlib import Path

version = os.environ["VERSION"]
path = Path("CHANGELOG.md")
if not path.is_file():
    print(f"Release {version}")
    raise SystemExit(0)
heading = re.compile(
    rf"^## \[?{re.escape(version)}\]?(?:\s+-\s+\d{{4}}-\d{{2}}-\d{{2}})?\s*$"
)
lines = path.read_text().splitlines()
start = None
for i, line in enumerate(lines):
    if heading.match(line.strip()):
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

changeset_bin() {
  echo "$ROOT/node_modules/.bin/changeset"
}

ensure_changeset_cli() {
  local bin
  bin="$(changeset_bin)"
  if [[ -x "$bin" ]]; then
    return 0
  fi
  echo "running npm install so @changesets/cli is available" >&2
  npm install
  if [[ ! -x "$bin" ]]; then
    echo "npm install did not provide ${bin}" >&2
    exit 2
  fi
}

venv_python() {
  echo "$ROOT/.venv/bin/python"
}

ensure_python_build() {
  local py
  py="$(venv_python)"
  if [[ ! -x "$py" ]]; then
    echo "creating .venv for python -m build" >&2
    python3 -m venv "$ROOT/.venv"
  fi
  if ! "$py" -c "import build" >/dev/null 2>&1; then
    echo "installing build into .venv" >&2
    "$ROOT/.venv/bin/pip" install -q build
  fi
}

github_release_exists() {
  gh release view "$1" >/dev/null 2>&1
}

only_release_paths_changed() {
  git status --porcelain | python3 - <<'PY'
import sys

allowed_prefixes = (".changeset/",)
allowed_exact = {
    "package.json",
    "pyproject.toml",
    "CHANGELOG.md",
}
for raw in sys.stdin:
    path = raw[3:].strip()
    if " -> " in path:
        path = path.split(" -> ", 1)[1]
    if path in allowed_exact or path.startswith(allowed_prefixes):
        continue
    sys.exit(1)
sys.exit(0)
PY
}

assert_tree_ok() {
  if [[ -z "$(git status --porcelain)" ]]; then
    return 0
  fi
  if ! only_release_paths_changed; then
    echo "working tree has non-release changes" >&2
    git status --porcelain >&2
    exit 1
  fi
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

collect_dist_assets() {
  local version="$1"
  local f
  shopt -u failglob
  shopt -s nullglob
  DIST_ASSETS=()
  for f in \
    dist/git_calculator-"${version}"-*.whl \
    dist/git_calculator-"${version}".tar.gz \
    dist/git-calculator-"${version}".tar.gz
  do
    if [[ -f "$f" ]]; then
      DIST_ASSETS+=("$f")
    fi
  done
}

place_tag() {
  local tag="$1"
  run git tag -f -a "$tag" -m "$tag"
  run git push --force origin "refs/tags/${tag}"
}

publish_tag() {
  local version="$1"
  local tag="v${version}"

  echo "version: ${version}"
  echo "tag:     ${tag}"

  if github_release_exists "$tag"; then
    echo "GitHub Release ${tag} already exists; nothing to do"
    exit 0
  fi

  run "$(venv_python)" -m build
  collect_dist_assets "$version"
  if [[ ${#DIST_ASSETS[@]} -eq 0 ]]; then
    if [[ "$DRY_RUN" -eq 1 ]]; then
      DIST_ASSETS=("dist/git_calculator-${version}-*.whl" "dist/git_calculator-${version}.tar.gz")
    else
      echo "no dist artifacts for ${version}" >&2
      exit 1
    fi
  fi

  if [[ -n "$(git status --porcelain)" ]]; then
    run git add package.json pyproject.toml CHANGELOG.md .changeset
    run git commit -m "chore: release ${tag}"
  fi

  if git rev-parse "$tag" >/dev/null 2>&1; then
    echo "moving unpublished tag ${tag} to $(git rev-parse --short HEAD)"
  fi
  run git push origin HEAD
  place_tag "$tag"

  local notes_file
  notes_file="$(mktemp)"
  trap 'rm -f "$notes_file"' RETURN
  if [[ "$DRY_RUN" -eq 1 ]]; then
    run gh release create "$tag" --title "$tag" --notes-file CHANGELOG.md "${DIST_ASSETS[@]}"
  else
    changelog_notes "$version" >"$notes_file"
    gh release create "$tag" --title "$tag" --notes-file "$notes_file" "${DIST_ASSETS[@]}"
  fi
}

if [[ "$CURRENT" -eq 1 && ${#CHANGESET_FILES[@]} -gt 0 ]]; then
  echo "pending changesets exist; omit --current so they can bump the version" >&2
  exit 1
fi

ensure_python_build
assert_tree_ok

if [[ "$CURRENT" -eq 0 && ${#CHANGESET_FILES[@]} -gt 0 ]]; then
  ensure_changeset_cli
  echo "pending changesets: ${#CHANGESET_FILES[@]}"
  echo "current version:    $(read_current_version)"
  echo "next version:       $(preview_next_version)"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    run "$(changeset_bin)" version
    run python3 scripts/format_changelog.py
    run python3 scripts/sync_pep440_version.py
    publish_tag "$(preview_next_version)"
    exit 0
  fi
  "$(changeset_bin)" version
  python3 scripts/format_changelog.py
  python3 scripts/sync_pep440_version.py
fi

publish_tag "$(read_current_version)"
