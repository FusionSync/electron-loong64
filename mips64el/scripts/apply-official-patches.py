#!/usr/bin/env python3
"""Apply pinned Electron official patches with resumable per-repository state.

No LoongArch patch is used. Interrupted git-am operations require manual review;
this helper never aborts, resets, skips, or edits a conflict automatically.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PINS = json.loads((ROOT / "metadata/source-pins.json").read_text())


def git_output(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def write_json(path, data):
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(data, indent=2) + "\n")
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path)
    args = parser.parse_args()
    workspace = args.workspace.expanduser().resolve()
    marker = workspace / ".mips64el-source.json"
    if not marker.is_file() or json.loads(marker.read_text()) != PINS:
        raise SystemExit("Use a workspace created by bootstrap-source.py at the pinned revisions.")
    electron = workspace / "src/electron"
    if git_output(electron, "rev-parse", "HEAD") != PINS["electron_commit"]:
        raise SystemExit("Electron HEAD differs from its official source pin.")
    if git_output(electron, "status", "--porcelain", "--", "patches"):
        raise SystemExit("Official Electron patch inputs were modified; review before continuing.")
    os.chdir(workspace)
    sys.path.insert(0, str(electron / "script"))
    from lib import git
    from lib.patches import patch_from_dir

    logs = workspace / "logs"
    logs.mkdir(exist_ok=True)
    state_path = logs / "official-patches.json"
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    targets = json.loads((electron / "patches/config.json").read_text())
    for target in targets:
        relative = target["repo"]
        repo = workspace / relative
        if not (repo / ".git").exists():
            raise SystemExit(f"Patch repository missing: {relative}; finish gclient sync first.")
        head = git_output(repo, "rev-parse", "HEAD")
        am_path = Path(git_output(repo, "rev-parse", "--git-path", "rebase-apply"))
        if not am_path.is_absolute():
            am_path = repo / am_path
        if am_path.exists():
            raise SystemExit(f"Interrupted git am in {relative}; resolve it manually before resuming.")
        if git_output(repo, "status", "--porcelain", "--untracked-files=no", "--ignore-submodules=all"):
            raise SystemExit(f"Tracked source changes in {relative}; apply official patches before local adaptations.")
        patch_data = patch_from_dir(target["patch_dir"])
        digest = hashlib.sha256(patch_data.encode("utf-8")).hexdigest()
        previous = state.get(relative)
        if previous and previous["status"] == "complete":
            if previous["patch_sha256"] != digest or previous["head"] != head:
                raise SystemExit(f"Completed patch inputs or HEAD changed in {relative}.")
            print(f"Already complete: {relative}", flush=True)
            continue
        if previous and (previous["base"] != head or previous["patch_sha256"] != digest):
            raise SystemExit(f"Interrupted patch state differs in {relative}; review manual recovery.")
        upstream = subprocess.run(["git", "-C", str(repo), "rev-parse", "--verify",
                                   "refs/patches/upstream-head"], text=True, capture_output=True)
        if not previous and upstream.returncode == 0 and upstream.stdout.strip() != head:
            raise SystemExit(f"Unrecorded patches already applied in {relative}; use a clean workspace.")
        state[relative] = {"status": "applying", "base": head, "patch_sha256": digest}
        write_json(state_path, state)
        print(f"Applying official patches: {relative}", flush=True)
        git.import_patches(repo=str(repo), patch_data=patch_data, threeway=True,
                           committer_name="Electron Scripts", committer_email="scripts@electron")
        state[relative].update(status="complete", head=git_output(repo, "rev-parse", "HEAD"))
        write_json(state_path, state)
    (logs / "official-patches.complete").write_text(PINS["electron_commit"] + "\n")
    print("Complete official Electron patch stack applied.")


if __name__ == "__main__":
    main()
