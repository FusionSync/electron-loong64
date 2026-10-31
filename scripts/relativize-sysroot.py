#!/usr/bin/env python3
"""Keep absolute target symlinks inside the copied sysroot."""
import os
import pathlib
import sys

root = pathlib.Path(sys.argv[1]).resolve()
changed = 0
for directory, dirs, files in os.walk(str(root), followlinks=False):
    for name in dirs + files:
        path = pathlib.Path(directory) / name
        if path.is_symlink():
            target = os.readlink(str(path))
            if target.startswith("/"):
                relative = os.path.relpath(str(root / target.lstrip("/")), str(path.parent))
                path.unlink()
                path.symlink_to(relative)
                changed += 1
print("Relativized {} sysroot symlinks".format(changed))
