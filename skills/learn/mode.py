"""Read or switch this project's learning mode without loading teaching notes."""

import argparse
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile


STATE_NAMES = (".learning", ".vibe-wise", ".sensible-vibes")
MODE_LINE = re.compile(r"^Learning mode:\s*([^\r\n]*?)[ \t]*$", re.I)


def profile_is_active(path):
    """Legacy profiles are active; any Off/paused or unknown marker disables them."""
    if path.is_symlink() or not path.is_file():
        return False
    has_content = False
    try:
        with path.open(encoding="utf-8") as stream:
            for line in stream:
                has_content = has_content or bool(line.strip())
                match = MODE_LINE.fullmatch(line.rstrip("\r\n"))
                if match and match.group(1).strip().lower() not in ("active", "on"):
                    return False
    except (OSError, UnicodeError):
        return False
    return has_content


def state_directory(cwd, strict=False):
    """Find nearest notes, respecting legacy names and Git/worktree boundaries."""
    for directory in (cwd, *cwd.parents):
        for name in STATE_NAMES:
            state = directory / name
            if state.exists() or state.is_symlink():
                if state.is_dir() and not state.is_symlink():
                    return state
                if strict:
                    raise ValueError(f"not a regular notes directory: {state}")
                return None
        if (directory / ".git").exists():
            break
    return None


def switch(cwd, command):
    """Change only profile.md's mode; status never creates files or directories."""
    cwd = Path(cwd)
    if not cwd.is_absolute() or not cwd.is_dir():
        raise ValueError("Use an existing absolute project working directory.")
    if command not in ("on", "off", "status"):
        raise ValueError("Choose on, off or status.")
    cwd = cwd.resolve()
    state = state_directory(cwd, strict=True)
    if command == "status":
        return {"mode": "on" if state and profile_is_active(state / "profile.md") else "off",
                "state": str(state) if state else None}
    if state is None:
        root = next((p for p in (cwd, *cwd.parents) if (p / ".git").exists()), cwd)
        state = root / ".learning"
    profile = state / "profile.md"
    if profile.is_symlink() or (profile.exists() and not profile.is_file()):
        raise ValueError(f"not a regular profile: {profile}")
    if profile.exists():
        text = profile.read_bytes().decode("utf-8")
        permissions = stat.S_IMODE(profile.stat().st_mode)
    else:
        text = "# Learner Profile\n\nOnboarding: incomplete\n"
        permissions = 0o600
    marker = "Learning mode: " + ("active" if command == "on" else "off")
    pattern = re.compile(r"^Learning mode:[^\r\n]*(\r?\n|$)", re.I | re.M)
    if pattern.search(text):
        updated = pattern.sub(lambda match: marker + match.group(1), text)
    else:
        updated = marker + "\n" + text
    if updated != text:
        state.mkdir(mode=0o700, parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=state, prefix=".mode-")
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(updated.encode("utf-8"))
                os.fchmod(stream.fileno(), permissions)
            os.replace(tmp, profile)
        finally:
            Path(tmp).unlink(missing_ok=True)
    return {"mode": command, "state": str(state)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("on", "off", "status"))
    parser.add_argument("--cwd", required=True)
    args = parser.parse_args(argv)
    try:
        result = switch(args.cwd, args.command)
    except (OSError, ValueError) as error:
        print(json.dumps({"error": str(error)}))
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
