#!/usr/bin/env bash
# Publish the static app to the gh-pages branch for GitHub Pages.
# Serves only index.html + data.json (+ .nojekyll) at the branch ROOT — light and
# fast on mobile. Brochures/images are linked from their remote URLs, so no large
# files are hosted. Run after rebuilding site/data.json.
#
#   bash scripts/publish_pages.sh
#
# One-time (GitHub web → repo → Settings → Pages):
#   Source: "Deploy from a branch" → Branch: gh-pages /(root) → Save
# Or, on the merged main, Source: "GitHub Actions" (uses .github/workflows/pages.yml).
# Site URL: https://<owner>.github.io/<repo>/
set -euo pipefail
cd "$(dirname "$0")/.."

BR="$(git rev-parse --abbrev-ref HEAD)"
IDX="$(git rev-parse "${BR}:site/index.html")"
DAT="$(git rev-parse "${BR}:site/data.json")"

export GIT_INDEX_FILE="$(mktemp)"
git read-tree --empty
git update-index --add --cacheinfo "100644,${IDX},index.html"
git update-index --add --cacheinfo "100644,${DAT},data.json"
NOJEKYLL="$(git hash-object -w --stdin </dev/null)"
git update-index --add --cacheinfo "100644,${NOJEKYLL},.nojekyll"
TREE="$(git write-tree)"
COMMIT="$(git commit-tree "$TREE" -m "Publish static site to GitHub Pages")"
rm -f "$GIT_INDEX_FILE"; unset GIT_INDEX_FILE

git branch -f gh-pages "$COMMIT"
git push -f -u origin gh-pages
echo "Published gh-pages (index.html + data.json). Pages updates in ~1 min."
