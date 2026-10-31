#!/usr/bin/env bash
set -euo pipefail

# Publish the verified bundle and its individual Electron release assets.
# Authentication is supplied by gh (for example GH_TOKEN); never put a token
# in this script or in the repository.
root=$(cd -- "$(dirname -- "$0")/.." && pwd)
repo=${GH_REPO:?Set GH_REPO to your GitHub owner/name}
tag=${RELEASE_TAG:-v37.2.2-uos-loong64}
title=${RELEASE_TITLE:-Electron 37.2.2 UOS Loong64}
bundle=${BUNDLE_ZIP:-$root/../electron37-attempt/electron37.2.2-linux-loong64-bundle.zip}
sha=${BUNDLE_SHA256:-$bundle.sha256}
asset_dir=${ASSET_DIR:-$root/../electron37-attempt/release-assets-fixed}
notes=${RELEASE_NOTES:-$root/release-notes/v37.2.2-uos-loong64.md}

for f in "$bundle" "$sha" "$notes"; do
    [[ -f "$f" ]] || { echo "Missing required file: $f" >&2; exit 2; }
done
assets=("$bundle" "$sha")
if [[ -d "$asset_dir" ]]; then
    while IFS= read -r -d '' f; do assets+=("$f"); done < <(find "$asset_dir" -maxdepth 1 -type f -print0 | sort -z)
fi

if gh release view "$tag" --repo "$repo" >/dev/null 2>&1; then
    gh release upload "$tag" "${assets[@]}" --repo "$repo" --clobber
else
    gh release create "$tag" "${assets[@]}" --repo "$repo" --title "$title" --notes-file "$notes"
fi
