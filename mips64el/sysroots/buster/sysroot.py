#!/usr/bin/env python3
"""Resolve, fetch, and extract a pinned Debian target sysroot without installing it.

Requires Python 3, curl, dpkg, and dpkg-deb on the x86_64 build host. No target
program, Debian maintainer script, apt hook, or package installation is executed.
"""

import argparse
import concurrent.futures
import functools
import hashlib
import json
import lzma
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import time


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    # JSON state enters the sysroot archive; make it independent of host umask.
    temporary.chmod(0o644)
    temporary.replace(path)


def paragraphs(path):
    opener = lzma.open if path.suffix == ".xz" else open
    with opener(path, "rt", encoding="utf-8") as stream:
        fields, previous = {}, None
        for line in stream:
            line = line.rstrip("\n")
            if not line:
                if fields:
                    yield fields
                fields, previous = {}, None
            elif line[0].isspace():
                if previous is None:
                    raise ValueError("Unexpected continuation in Packages index")
                fields[previous] += " " + line.strip()
            else:
                previous, value = line.split(":", 1)
                fields[previous] = value.strip()
        if fields:
            yield fields


def split_top_level(text, separator):
    depth, start, result = 0, 0, []
    for index, character in enumerate(text):
        if character in "([":
            depth += 1
        elif character in ")]":
            depth -= 1
        elif character == separator and depth == 0:
            result.append(text[start:index].strip())
            start = index + 1
    if depth:
        raise ValueError("Unbalanced dependency expression: " + text)
    result.append(text[start:].strip())
    return [item for item in result if item]


@functools.lru_cache(maxsize=None)
def version_matches(version, operator, required):
    if not operator:
        return True
    return subprocess.run(
        ["dpkg", "--compare-versions", version, operator, required],
        check=False,
    ).returncode == 0


@functools.lru_cache(maxsize=None)
def arch_matches(architecture, pattern):
    return subprocess.run(
        ["dpkg-architecture", "-a", architecture, "-i", pattern],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
    ).returncode == 0


def parse_atom(expression, architecture):
    expression = expression.strip()
    match = re.fullmatch(
        r"([a-z0-9][a-z0-9+.-]*)(?::([a-z0-9-]+))?"
        r"\s*(?:\((<<|<=|=|>=|>>)\s*([^()]+)\))?"
        r"\s*(?:\[([^\]]+)\])?", expression,
    )
    if not match:
        raise ValueError("Unsupported dependency atom: " + expression)
    name, qualifier, operator, version, restrictions = match.groups()
    if qualifier not in (None, "any", "native", architecture):
        raise ValueError("Foreign architecture dependency: " + expression)
    if restrictions:
        positive = [x for x in restrictions.split() if not x.startswith("!")]
        negative = [x[1:] for x in restrictions.split() if x.startswith("!")]
        if any(arch_matches(architecture, x) for x in negative):
            return None
        if positive and not any(arch_matches(architecture, x) for x in positive):
            return None
    return {"name": name, "operator": operator, "version": version,
            "expression": expression}


class Resolver:
    def __init__(self, records, architecture, preferred):
        self.architecture = architecture
        self.preferred = preferred
        self.packages, self.providers, self.selected = {}, {}, {}
        self.edges = []
        for record in records:
            if record.get("Architecture") not in (architecture, "all"):
                continue
            name = record["Package"]
            previous = self.packages.get(name)
            if not previous or version_matches(record["Version"], ">>", previous["Version"]):
                self.packages[name] = record
        for name, record in self.packages.items():
            for expression in split_top_level(record.get("Provides", ""), ","):
                atom = parse_atom(expression, architecture)
                if atom:
                    self.providers.setdefault(atom["name"], []).append(
                        (name, atom["version"] if atom["operator"] == "=" else None))

    def candidates(self, atom):
        name = atom["name"]
        result = []
        record = self.packages.get(name)
        if record and version_matches(record["Version"], atom["operator"], atom["version"]):
            result.append(name)
        provided = self.providers.get(name, [])
        provided = sorted(provided, key=lambda p: (p[0] not in self.selected,
                          p[0] not in self.preferred, p[0]))
        for provider, version in provided:
            if atom["operator"] and (version is None or not version_matches(
                    version, atom["operator"], atom["version"])):
                continue
            if provider not in result:
                result.append(provider)
        return result

    def choose(self, group, parent, field):
        possibilities = []
        for alternative in split_top_level(group, "|"):
            atom = parse_atom(alternative, self.architecture)
            if atom:
                possibilities.extend((name, alternative) for name in self.candidates(atom))
        if not possibilities:
            atoms = [parse_atom(x, self.architecture) for x in split_top_level(group, "|")]
            if not any(atoms):
                return None
            raise ValueError(f"Unresolved {field} from {parent}: {group}")
        chosen = next((x for x in possibilities if x[0] in self.selected), None)
        chosen = chosen or next((x for x in possibilities if x[0] in self.preferred), None)
        chosen = chosen or possibilities[0]
        self.edges.append({"from": parent, "field": field, "requirement": group,
                           "selected": chosen[0], "alternative": chosen[1]})
        return chosen[0]

    def resolve(self, seeds):
        pending = []
        for seed in seeds:
            chosen = self.choose(seed, "<seed>", "seed")
            if chosen and chosen not in self.selected:
                self.selected[chosen] = self.packages[chosen]
                pending.append(chosen)
        position = 0
        while position < len(pending):
            name = pending[position]
            position += 1
            record = self.selected[name]
            for field in ("Pre-Depends", "Depends"):
                for group in split_top_level(record.get(field, ""), ","):
                    chosen = self.choose(group, name, field)
                    if chosen and chosen not in self.selected:
                        self.selected[chosen] = self.packages[chosen]
                        pending.append(chosen)
        return self.selected


def resolve(args):
    actual = sha256(args.index)
    if actual != args.index_sha256:
        raise ValueError(f"Packages index SHA256 mismatch: {actual}")
    seeds = [line.split("#", 1)[0].strip() for line in args.seeds.read_text().splitlines()]
    seeds = [line for line in seeds if line]
    if not seeds:
        raise ValueError("Seeds file is empty")
    resolver = Resolver(paragraphs(args.index), args.architecture, set(args.prefer))
    selected = resolver.resolve(seeds)
    files = []
    for name, record in sorted(selected.items()):
        filename = PurePosixPath(record["Filename"])
        if filename.is_absolute() or ".." in filename.parts:
            raise ValueError("Unsafe package filename: " + str(filename))
        if not re.fullmatch("[0-9a-f]{64}", record.get("SHA256", "")):
            raise ValueError("Package has no SHA256: " + name)
        files.append({"package": name, "version": record["Version"],
                      "architecture": record["Architecture"],
                      "filename": str(filename), "size": int(record["Size"]),
                      "sha256": record["SHA256"],
                      "url": args.base_url.rstrip("/") + "/" + str(filename),
                      "depends": record.get("Depends", ""),
                      "pre_depends": record.get("Pre-Depends", ""),
                      "provides": record.get("Provides", "")})
    manifest = {"schema": 1, "suite": "buster", "architecture": args.architecture,
                "index": {"url": args.index_url, "sha256": actual},
                "seeds": seeds, "preferred_providers": sorted(args.prefer),
                "files": files, "dependency_resolution": resolver.edges,
                "notes": ["Depends and Pre-Depends closure; Recommends/Suggests excluded.",
                          "No package installation or maintainer scripts executed.",
                          "Deterministic provider selection, not a general apt SAT solver."]}
    write_json(args.manifest, manifest)
    print(f"Resolved {len(files)} packages; {sum(x['size'] for x in files)/1048576:.1f} MiB compressed")
    print(args.manifest)


def load_manifest(path):
    value = json.loads(path.read_text())
    if value.get("schema") != 1 or value.get("architecture") != "mips64el":
        raise ValueError("Expected schema 1 mips64el manifest")
    names = set()
    for record in value["files"]:
        path = PurePosixPath(record["filename"])
        if path.is_absolute() or ".." in path.parts or path.name in names:
            raise ValueError("Unsafe or duplicate cache filename: " + str(path))
        names.add(path.name)
    return value


def cache_path(cache, record):
    return cache / PurePosixPath(record["filename"]).name


def verify_file(path, record):
    return path.is_file() and path.stat().st_size == record["size"] and sha256(path) == record["sha256"]


def download_one(record, cache):
    target = cache_path(cache, record)
    if verify_file(target, record):
        return record["package"], "cached"
    partial = target.with_name(target.name + ".part")
    subprocess.run(["curl", "--fail", "--location", "--silent", "--show-error",
                    "--retry", "5", "--retry-all-errors", "--connect-timeout", "30",
                    "--max-time", "900", "--continue-at", "-", "--output",
                    str(partial), record["url"]], check=True)
    if not verify_file(partial, record):
        raise ValueError("SHA256 or size mismatch for " + record["package"])
    partial.replace(target)
    return record["package"], "downloaded"


def fetch(args):
    manifest = load_manifest(args.manifest)
    args.cache.mkdir(parents=True, exist_ok=True)
    count, started, previous = 0, time.monotonic(), time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        tasks = [pool.submit(download_one, record, args.cache) for record in manifest["files"]]
        for task in concurrent.futures.as_completed(tasks):
            name, status = task.result()
            count += 1
            now = time.monotonic()
            if now - previous > 5 or count == len(tasks):
                print(f"[{count}/{len(tasks)}] {status}: {name}; {now-started:.0f}s", flush=True)
                previous = now
    print("All package files match pinned SHA256 and size.")


def relativize_links(root):
    changed = 0
    for directory, names, files in os.walk(root, followlinks=False):
        for name in names + files:
            path = Path(directory) / name
            if path.is_symlink():
                target = os.readlink(path)
                if target.startswith("/"):
                    relative = os.path.relpath(root / target.lstrip("/"), path.parent)
                    path.unlink()
                    path.symlink_to(relative)
                    changed += 1
    return changed


def extract(args):
    manifest = load_manifest(args.manifest)
    expected_manifest = sha256(args.manifest)
    root = args.root.absolute()
    stamp = root / ".sysroot-recipe.json"
    if root.is_symlink():
        raise ValueError("Sysroot destination must not be a symlink")
    if root.exists() and any(root.iterdir()):
        if not args.resume or not stamp.is_file():
            raise ValueError("Destination is not empty; use an empty root or --resume for this recipe")
        if json.loads(stamp.read_text()).get("manifest_sha256") != expected_manifest:
            raise ValueError("Destination belongs to a different manifest")
    root.mkdir(parents=True, exist_ok=True)
    state = {"manifest_sha256": expected_manifest, "complete": False, "extracted": []}
    write_json(stamp, state)
    for index, record in enumerate(manifest["files"], 1):
        archive = cache_path(args.cache, record)
        if not verify_file(archive, record):
            raise ValueError("Missing or invalid package cache file: " + str(archive))
        actual = subprocess.check_output(
            ["dpkg-deb", "--show", "--showformat=${Package}\n${Version}\n${Architecture}\n", str(archive)],
            text=True).splitlines()
        expected = [record["package"], record["version"], record["architecture"]]
        if actual != expected:
            raise ValueError(f"Package metadata mismatch for {archive}: {actual}")
        subprocess.run(["dpkg-deb", "-x", str(archive), str(root)], check=True)
        state["extracted"].append(record["package"])
        if index % 25 == 0 or index == len(manifest["files"]):
            write_json(stamp, state)
            print(f"[{index}/{len(manifest['files'])}] extracted {record['package']}", flush=True)
    state["absolute_symlinks_relativized"] = relativize_links(root)
    state["complete"] = True
    write_json(stamp, state)
    print(f"Sysroot ready: {root}; {state['absolute_symlinks_relativized']} absolute links made relative")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("resolve")
    command.add_argument("--index", type=Path, required=True)
    command.add_argument("--index-sha256", required=True)
    command.add_argument("--index-url", required=True)
    command.add_argument("--base-url", default="https://archive.debian.org/debian")
    command.add_argument("--architecture", default="mips64el", choices=["mips64el"])
    command.add_argument("--seeds", type=Path, required=True)
    command.add_argument("--prefer", action="append", default=[])
    command.add_argument("--manifest", type=Path, required=True)
    command.set_defaults(function=resolve)
    for operation, function in (("fetch", fetch), ("extract", extract)):
        command = commands.add_parser(operation)
        command.add_argument("--manifest", type=Path, required=True)
        command.add_argument("--cache", type=Path, required=True)
        if operation == "fetch":
            command.add_argument("--jobs", type=int, default=4)
        else:
            command.add_argument("--root", type=Path, required=True)
            command.add_argument("--resume", action="store_true")
        command.set_defaults(function=function)
    args = parser.parse_args()
    try:
        args.function(args)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"ERROR: {error}\n")


if __name__ == "__main__":
    main()
