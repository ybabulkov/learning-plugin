#!/usr/bin/env python3
"""Record which teaching.md files the learner approved, so a cloned repo can't bring its own.

Approvals live outside every project, in $XDG_CONFIG_HOME/learning/approved.json
(default ~/.config/learning/approved.json). Each entry maps the absolute path of a
teaching.md to the SHA-256 of the bytes the learner approved. Not ~/.learning/:
the session-start hook would mistake that folder for a project's notes.

Commands (all print JSON):
  approve --state DIR   record the current teaching.md as approved
  check --state DIR     {"status": "approved" | "unapproved" | "missing"}
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile


FILENAME = "teaching.md"


class ApprovalError(Exception):
    """A problem the caller should see as a clear message, not a traceback."""


def approvals_path():
    base = os.environ.get("XDG_CONFIG_HOME", "")
    # The XDG spec says relative paths are invalid and must be ignored.
    if not os.path.isabs(base):
        base = Path.home() / ".config"
    return Path(base) / "learning" / "approved.json"


def teaching_key(state):
    # Resolve the folder, so a project reached through a symlinked parent matches.
    return str(Path(state).resolve() / FILENAME)


def fingerprint(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_approvals(path):
    """Approved fingerprints, or {} when the file is missing, linked or unreadable."""
    try:
        if path.is_symlink() or not path.is_file():
            return {}
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def check(state):
    """'approved', 'unapproved' or 'missing'. Anything unknown counts as unapproved."""
    teaching = Path(state) / FILENAME
    if not teaching.exists() and not teaching.is_symlink():
        return "missing"
    try:
        if teaching.is_symlink() or not teaching.is_file():
            return "unapproved"
        approved = load_approvals(approvals_path()).get(teaching_key(state))
        return "approved" if approved == fingerprint(teaching) else "unapproved"
    except (OSError, RuntimeError):
        # RuntimeError: Path.home() found no home folder. Unknown means ask.
        return "unapproved"


def approve(state):
    state = Path(state)
    teaching = state / FILENAME
    if state.is_symlink() or not state.is_dir():
        raise ApprovalError(f"not a notes directory: {state}")
    if teaching.is_symlink() or not teaching.is_file():
        raise ApprovalError(f"no regular {FILENAME} to approve in {state}")
    path = approvals_path()
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise ApprovalError(f"refusing to use {path}: not a regular file")
    # Unreadable approvals are dropped: other projects will simply ask again.
    approvals = load_approvals(path)
    key = teaching_key(state)
    approvals[key] = fingerprint(teaching)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    # Write a temporary file and swap it in, so an interrupted write never leaves
    # a half-written approvals file behind.
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".approved-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(approvals, stream, indent=2, sort_keys=True)
            stream.write("\n")
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return {"approved": key, "fingerprint": approvals[key]}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Learning teaching.md approvals")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("approve", "check"):
        sub.add_parser(name).add_argument(
            "--state", required=True, help="the project's notes directory")
    args = parser.parse_args(argv)
    try:
        if args.command == "approve":
            out = approve(args.state)
        else:
            out = {"status": check(args.state)}
    except (ApprovalError, OSError, RuntimeError) as error:
        print(json.dumps({"error": str(error)}))
        return 1
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
