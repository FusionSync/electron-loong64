#!/usr/bin/env python3
"""Apply Electron's patch manifests, recording each completed repository."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parent
os.chdir(root)
sys.path.insert(0, str(root / "src/electron/script"))
from lib import git
from lib.patches import patch_from_dir

state_path = root / "logs/patch-state.json"
state = json.loads(state_path.read_text()) if state_path.exists() else {}


def git_output(repo, *args):
    return subprocess.check_output(["git", "-C", repo, *args], text=True).strip()


def save():
    temporary = state_path.with_suffix(".json.tmp")
    with temporary.open("w") as stream:
        json.dump(state, stream, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(state_path)


for target in json.loads((root / "src/electron/patches/config.json").read_text()):
    repo = target["repo"]
    if not (root / repo).exists():
        raise RuntimeError(f"Missing patch repository: {repo}")
    patch_data = patch_from_dir(target["patch_dir"])
    digest = hashlib.sha256(patch_data.encode("utf-8")).hexdigest()
    head = git_output(repo, "rev-parse", "HEAD")
    git_output(repo, "cat-file", "-e", head + "^{commit}")
    am_path = git_output(repo, "rev-parse", "--git-path", "rebase-apply")
    if (root / repo / am_path).exists() or Path(am_path).is_absolute() and Path(am_path).exists():
        raise RuntimeError(f"Interrupted git am in {repo}; recover it before resuming")
    # Child repositories receive their own patch commits and HEAD checks below.
    # Those commits legitimately differ from the parent's recorded gitlinks.
    if git_output(repo, "status", "--porcelain", "--untracked-files=no",
                  "--ignore-submodules=all"):
        raise RuntimeError(f"Tracked files changed in {repo}; review before applying patches")
    previous = state.get(repo)
    if previous and previous["status"] == "complete":
        if previous["patch_sha256"] != digest or previous["head"] != head:
            raise RuntimeError(f"Patch inputs or HEAD changed in completed repository {repo}")
        print(f"Already complete: {repo} {head}", flush=True)
        continue
    if previous:
        if previous["patch_sha256"] != digest or previous["base"] != head:
            raise RuntimeError(f"Interrupted patch state changed in {repo}; review recovery")
    else:
        upstream = subprocess.run(
            ["git", "-C", repo, "rev-parse", "--verify", "refs/patches/upstream-head"],
            text=True, capture_output=True)
        if upstream.returncode == 0 and upstream.stdout.strip() != head:
            raise RuntimeError(f"Unrecorded earlier patch application in {repo}")
    state[repo] = {"status": "applying", "base": head, "patch_sha256": digest}
    save()
    print(f"Applying: {repo} from {head}", flush=True)
    git.import_patches(repo=repo, patch_data=patch_data,
                       committer_name="Electron Scripts",
                       committer_email="scripts@electron")
    state[repo].update(status="complete", head=git_output(repo, "rev-parse", "HEAD"))
    save()
    print(f"Completed: {repo} {state[repo]['head']}", flush=True)
