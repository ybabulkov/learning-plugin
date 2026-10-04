#!/usr/bin/env python3
"""Track which terms a learner has seen explained, and when to quiz them.

The registry lives in <state dir>/terms.json. Claude runs this script instead of
editing the JSON by hand, so showing counts and quiz dates stay exact. The rules
it enforces are described in terms.md next to this file.

Commands (all print JSON):
  define FILE|-            add or update term definitions from a JSON list
  plan --page P ID...      which terms still get a tooltip on page P
  record-page --page P ID...  record that page P explained these terms
  due [--limit N]          terms due for a quiz today
  result ID right|wrong    record one quiz answer
  exclude ID... [--reason]  never explain or quiz these terms
  include ID...            undo exclude
  quiz-done                record that a quiz ran today
  status                   counts for a quick overview
"""

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import re
import sys
import tempfile


MAX_SHOWINGS = 3
# Leitner box -> days until the next quiz. A right answer moves a term up one box;
# a wrong answer sends it back to box 1.
INTERVALS = {1: 1, 2: 3, 3: 7, 4: 21, 5: 60}
PAGES_PER_QUIZ = 2
FIELDS = ("term", "kind", "short", "match", "prose")
ID_PATTERN = re.compile(r"[a-z0-9][a-z0-9-]*")


class RegistryError(Exception):
    """A problem the caller should see as a clear message, not a traceback."""


def empty():
    return {
        "version": 1, "max_showings": MAX_SHOWINGS, "last_quiz": None,
        "pages_since_quiz": 0, "pages": {}, "terms": {},
    }


def load(path):
    path = Path(path)
    # A linked registry could point at another project's learning history.
    if path.is_symlink():
        raise RegistryError(f"refusing to use a symlinked registry: {path}")
    if not path.exists():
        return empty()
    data = empty()
    data.update(json.loads(path.read_text(encoding="utf-8")))
    return data


def save(path, data):
    path = Path(path)
    if path.is_symlink():
        raise RegistryError(f"refusing to write a symlinked registry: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    # Write a temporary file and swap it in, so an interrupted write never leaves
    # a half-written registry behind.
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".terms-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def day(value):
    return dt.date.fromisoformat(value)


def define(data, items):
    """Add or update definitions. Showing history and quiz state are kept."""
    if not isinstance(items, list):
        raise RegistryError("definitions must be a JSON list of objects")
    changed = []
    for item in items:
        if not isinstance(item, dict):
            raise RegistryError("each definition must be a JSON object")
        term_id = item.get("id", "")
        if not ID_PATTERN.fullmatch(term_id):
            raise RegistryError(f"bad id {term_id!r}: use lowercase letters, digits and dashes")
        for field in ("term", "kind", "short"):
            if not isinstance(item.get(field), str) or not item[field].strip():
                raise RegistryError(f"{term_id}: '{field}' is required")
        patterns = item.get("match", [])
        if not isinstance(patterns, list) or not all(isinstance(p, str) and p for p in patterns):
            raise RegistryError(f"{term_id}: 'match' must be a list of regex strings")
        for pattern in patterns:
            try:
                # Pages use these as JavaScript regexes. Python's syntax overlaps
                # enough to catch typos before they silently match nothing.
                re.compile(pattern)
            except re.error as error:
                raise RegistryError(f"{term_id}: bad pattern {pattern!r}: {error}") from None
        entry = data["terms"].setdefault(term_id, {
            "shown_in": [], "first_shown": None,
            "quiz": {"box": 0, "due": None, "history": []},
        })
        for field in FIELDS:
            if field in item:
                entry[field] = item[field]
        entry.setdefault("match", [])
        entry["prose"] = bool(entry.get("prose", False))
        entry.setdefault("excluded", False)
        changed.append(term_id)
    return {"defined": changed}


def plan(data, page, ids):
    """Return the tooltip data a page should embed, plus the terms it must not explain."""
    out = {"page": page, "max_showings": data["max_showings"], "terms": {},
           "retired": [], "excluded": [], "unknown": []}
    for term_id in ids:
        entry = data["terms"].get(term_id)
        if entry is None:
            out["unknown"].append(term_id)
            continue
        if entry.get("excluded"):
            out["excluded"].append(term_id)
            continue
        shown = entry["shown_in"]
        if page in shown:
            # Republishing a page keeps its tooltips and doesn't count again.
            nth = shown.index(page) + 1
        elif len(shown) < data["max_showings"]:
            nth = len(shown) + 1
        else:
            out["retired"].append(term_id)
            continue
        out["terms"][term_id] = {field: entry.get(field) for field in FIELDS}
        out["terms"][term_id]["nth"] = nth
    return out


def due(data, today, limit=None):
    items = []
    for term_id, entry in data["terms"].items():
        when = entry["quiz"]["due"]
        if entry.get("excluded"):
            continue
        if entry["shown_in"] and when and day(when) <= today:
            items.append((entry["quiz"]["box"], when, term_id))
    items.sort()
    if limit:
        items = items[:limit]
    return [{
        "id": term_id, "term": data["terms"][term_id]["term"],
        "kind": data["terms"][term_id]["kind"], "short": data["terms"][term_id]["short"],
        "box": box, "due": when,
    } for box, when, term_id in items]


def record_page(data, page, ids, today, title=None, url=None):
    """Count one showing per term for this page, never past the limit."""
    if page not in data["pages"]:
        data["pages"][page] = {"title": title, "url": url, "first_recorded": today.isoformat()}
        data["pages_since_quiz"] += 1
    else:
        if title:
            data["pages"][page]["title"] = title
        if url:
            data["pages"][page]["url"] = url
    recorded, retired, excluded, unknown = [], [], [], []
    for term_id in ids:
        entry = data["terms"].get(term_id)
        if entry is None:
            unknown.append(term_id)
            continue
        if entry.get("excluded"):
            excluded.append(term_id)
            continue
        if page in entry["shown_in"]:
            continue
        if len(entry["shown_in"]) >= data["max_showings"]:
            retired.append(term_id)
            continue
        entry["shown_in"].append(page)
        if entry["first_shown"] is None:
            entry["first_shown"] = today.isoformat()
            # Never quiz a term on the day it was first explained.
            entry["quiz"]["due"] = (today + dt.timedelta(days=1)).isoformat()
        recorded.append(term_id)
    suggested = (data["pages_since_quiz"] >= PAGES_PER_QUIZ
                 and data["last_quiz"] != today.isoformat()
                 and bool(due(data, today)))
    return {"recorded": recorded, "retired": retired, "excluded": excluded, "unknown": unknown,
            "pages_since_quiz": data["pages_since_quiz"], "quiz_suggested": suggested}


def result(data, term_id, outcome, today):
    entry = data["terms"].get(term_id)
    if entry is None:
        raise RegistryError(f"unknown term {term_id!r}")
    if outcome not in ("right", "wrong"):
        raise RegistryError("outcome must be 'right' or 'wrong'")
    quiz = entry["quiz"]
    quiz["box"] = min(quiz["box"] + 1, max(INTERVALS)) if outcome == "right" else 1
    quiz["due"] = (today + dt.timedelta(days=INTERVALS[quiz["box"]])).isoformat()
    quiz["history"].append({"date": today.isoformat(), "result": outcome})
    return {"id": term_id, "box": quiz["box"], "next_due": quiz["due"]}


def set_excluded(data, ids, excluded, reason=None):
    """Mark terms the learner doesn't need explained. History is kept either way."""
    missing = [term_id for term_id in ids if term_id not in data["terms"]]
    if missing:
        raise RegistryError(f"unknown term(s): {', '.join(missing)}")
    for term_id in ids:
        data["terms"][term_id]["excluded"] = excluded
        if excluded and reason:
            data["terms"][term_id]["excluded_reason"] = reason
        elif not excluded:
            data["terms"][term_id].pop("excluded_reason", None)
    return {"excluded" if excluded else "included": list(ids)}


def quiz_done(data, today):
    data["last_quiz"] = today.isoformat()
    data["pages_since_quiz"] = 0
    return {"last_quiz": data["last_quiz"]}


def status(data, today):
    active = [t for t in data["terms"].values() if not t.get("excluded")]
    return {
        "terms": len(active),
        "excluded": len(data["terms"]) - len(active),
        "shown": sum(1 for t in active if t["shown_in"]),
        "retired": sum(1 for t in active if len(t["shown_in"]) >= data["max_showings"]),
        "due": len(due(data, today)),
        "pages": len(data["pages"]),
        "pages_since_quiz": data["pages_since_quiz"],
        "last_quiz": data["last_quiz"],
    }


def session_summary(path, today=None):
    """Small, content-free summary for the SessionStart hook."""
    today = today or dt.date.today()
    data = load(path)
    return {"due": len(due(data, today)), "quizzed_today": data["last_quiz"] == today.isoformat()}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Learning term registry")
    parser.add_argument("--state", required=True, help="the project's .learning directory")
    parser.add_argument("--today", help="override today's date (YYYY-MM-DD), for tests")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("define"); p.add_argument("file")
    p = sub.add_parser("plan"); p.add_argument("--page", required=True); p.add_argument("ids", nargs="+")
    p = sub.add_parser("record-page"); p.add_argument("--page", required=True); p.add_argument("ids", nargs="+")
    p.add_argument("--title"); p.add_argument("--url")
    p = sub.add_parser("due"); p.add_argument("--limit", type=int)
    p = sub.add_parser("result"); p.add_argument("id"); p.add_argument("outcome")
    p = sub.add_parser("exclude"); p.add_argument("ids", nargs="+"); p.add_argument("--reason")
    p = sub.add_parser("include"); p.add_argument("ids", nargs="+")
    sub.add_parser("quiz-done")
    sub.add_parser("status")
    args = parser.parse_args(argv)

    state = Path(args.state)
    if state.is_symlink() or not state.is_dir():
        print(json.dumps({"error": f"not a state directory: {state}"}))
        return 2
    path = state / "terms.json"
    today = day(args.today) if args.today else dt.date.today()
    try:
        data = load(path)
        if args.command == "define":
            raw = sys.stdin.read() if args.file == "-" else Path(args.file).read_text(encoding="utf-8")
            out = define(data, json.loads(raw))
            save(path, data)
        elif args.command == "plan":
            out = plan(data, args.page, args.ids)
        elif args.command == "record-page":
            out = record_page(data, args.page, args.ids, today, args.title, args.url)
            save(path, data)
        elif args.command == "due":
            out = due(data, today, args.limit)
        elif args.command == "result":
            out = result(data, args.id, args.outcome, today)
            save(path, data)
        elif args.command in ("exclude", "include"):
            out = set_excluded(data, args.ids, args.command == "exclude", getattr(args, "reason", None))
            save(path, data)
        elif args.command == "quiz-done":
            out = quiz_done(data, today)
            save(path, data)
        else:
            out = status(data, today)
    except (RegistryError, ValueError, OSError) as error:
        print(json.dumps({"error": str(error)}))
        return 1
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
