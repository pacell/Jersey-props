#!/usr/bin/env bash
# Publish the static site (site/) to the gh-pages branch for GitHub Pages.
# Puts site/ contents at the branch ROOT (+ .nojekyll) without touching your
# working tree or current branch. Run after rebuilding site/data.json.
#
#   bash scripts/publish_pages.sh
#
# One-time setup (GitHub web → repo → Settings → Pages):
#   Source: "Deploy from a branch"  →  Branch: gh-pages  /(root)  →  Save
# Site URL: https://<owner>.github.io/<repo>/
set -euo pipefail
cd "$(dirname "$0")/.."

SRC_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
SITE_TREE="$(git rev-parse "${SRC_BRANCH}:site")"

export GIT_INDEX_FILE="$(mktemp)"
git read-tree "$SITE_TREE"
BLOB="$(git hash-object -w --stdin </dev/null)"
git update-index --add --cacheinfo 100644,"$BLOB",.nojekyll
TREE="$(git write-tree)"
COMMIT="$(git commit-tree "$TREE" -m "Publish static site to GitHub Pages")"
rm -f "$GIT_INDEX_FILE"; unset GIT_INDEX_FILE

git branch -f gh-pages "$COMMIT"
git push -f -u origin gh-pages
echo "Published gh-pages. Pages will update in ~1 minute."
