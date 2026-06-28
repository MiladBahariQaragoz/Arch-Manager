#!/usr/bin/env python3
"""Aggregate study/work/others source files into plan.md.

On each run this:
  1. Parses study.md, work.md, others.md (structured markdown).
  2. Archives completed items to done.md (tasks marked [x]; exams whose date has
     passed) and removes them from their source file.
  3. Writes a sorted, sectioned plan.md with computed urgency
     (overdue tasks and at-risk exams float to the top).

Pure standard library — no third-party dependencies.
"""

import datetime
import re
from pathlib import Path

DRIVE = Path("/home/sudo/GoogleDrive/Planner")
SOURCES = {
    "study": DRIVE / "study.md",
    "work": DRIVE / "work.md",
    "others": DRIVE / "others.md",
}
PLAN = DRIVE / "plan.md"
DONE = DRIVE / "done.md"

TODAY = datetime.date.today()
AT_RISK_DAYS = 7        # exam within this many days ...
AT_RISK_PROGRESS = 70   # ... and below this progress % is "at risk"

TASK_RE = re.compile(r"^\s*-\s*\[( |x|X)\]\s*(.*)$")
ITEM_RE = re.compile(r"^\s*-\s+(?!\[)(.*)$")  # "- foo" but not "- [ ] foo"
HEADER_RE = re.compile(r"^##\s+(.*)$")


def parse_date(value):
    try:
        return datetime.date.fromisoformat(value.strip())
    except (ValueError, AttributeError):
        return None


def split_meta(text):
    """'Title | due: 2026-07-03 | progress: 40%' -> ('Title', {'due': ...})."""
    parts = [p.strip() for p in text.split("|")]
    title = parts[0]
    meta = {}
    for part in parts[1:]:
        if ":" in part:
            key, val = part.split(":", 1)
            meta[key.strip().lower()] = val.strip()
    return title, meta


def days_until(date):
    return (date - TODAY).days


def fmt_delta(days):
    if days < 0:
        return f"OVERDUE {abs(days)}d"
    if days == 0:
        return "due today"
    if days == 1:
        return "due tomorrow"
    return f"in {days}d"


# Collected results.
tasks = []      # dict: cat, title, due (date|None), days (int|None)
exams = []      # dict: cat, title, date, progress, days, at_risk
recurring = []  # dict: cat, title, freq
archived = []   # (cat, title) -> written to done.md


def process_source(cat, path):
    """Parse a source file, archive done items, rewrite it, collect the rest."""
    lines = path.read_text().splitlines()
    section = None
    keep = []
    in_comment = False

    for line in lines:
        # Skip parsing of HTML comment blocks; users can comment items out to
        # disable them. Commented lines are preserved verbatim.
        if in_comment:
            keep.append(line)
            if "-->" in line:
                in_comment = False
            continue
        if "<!--" in line:
            keep.append(line)
            if "-->" not in line:
                in_comment = True
            continue

        header = HEADER_RE.match(line)
        if header:
            section = header.group(1).strip().lower()
            keep.append(line)
            continue

        task = TASK_RE.match(line)
        if task:
            checked = task.group(1).lower() == "x"
            title, meta = split_meta(task.group(2))
            if checked:
                archived.append((cat, title))
                continue  # drop from source
            due = parse_date(meta.get("due", "")) if "due" in meta else None
            tasks.append(
                {"cat": cat, "title": title, "due": due,
                 "days": days_until(due) if due else None}
            )
            keep.append(line)
            continue

        item = ITEM_RE.match(line)
        if item and section:
            title, meta = split_meta(item.group(1))
            if section.startswith("exam"):
                date = parse_date(meta.get("date", ""))
                progress = int(re.sub(r"\D", "", meta.get("progress", "0")) or 0)
                if date and date < TODAY:
                    archived.append((cat, f"Exam: {title} (held {date})"))
                    continue  # exam happened -> archive
                days = days_until(date) if date else None
                at_risk = (
                    days is not None
                    and days <= AT_RISK_DAYS
                    and progress < AT_RISK_PROGRESS
                )
                exams.append(
                    {"cat": cat, "title": title, "date": date,
                     "progress": progress, "days": days, "at_risk": at_risk}
                )
                keep.append(line)
                continue
            if section.startswith("recurring"):
                recurring.append(
                    {"cat": cat, "title": title, "freq": meta.get("freq", "")}
                )
                keep.append(line)
                continue

        keep.append(line)

    path.write_text("\n".join(keep) + ("\n" if keep else ""))


def append_done():
    if not archived:
        return
    text = DONE.read_text() if DONE.exists() else "# Done\n"
    # Dedup on the "[cat] title" suffix so an item already archived on an
    # earlier day (with a different date stamp) is not added again.
    existing = set()
    for line in text.splitlines():
        m = re.match(r"^-\s+\S+\s+—\s+(\[.*)$", line)
        if m:
            existing.add(m.group(1).strip())
    text = text.rstrip("\n") + "\n"
    for cat, title in archived:
        key = f"[{cat}] {title}"
        if key in existing:
            continue
        existing.add(key)
        text += f"- {TODAY} — {key}\n"
    DONE.write_text(text)


def write_plan():
    out = [f"# Plan — generated {TODAY:%A %d %b %Y}", ""]

    # Needs attention: overdue tasks + at-risk exams.
    attention = []
    for t in tasks:
        if t["days"] is not None and t["days"] < 0:
            attention.append(
                f"- [{fmt_delta(t['days'])}] [{t['cat']}] {t['title']} (due {t['due']})"
            )
    for e in exams:
        if e["at_risk"]:
            attention.append(
                f"- [AT RISK] [{e['cat']}] {e['title']} exam {fmt_delta(e['days'])}, "
                f"{e['progress']}% ready ({e['date']})"
            )
    if attention:
        out.append("## ⚠️ Needs attention")
        out.extend(attention)
        out.append("")

    # Tasks with deadlines, soonest first; undated last.
    dated = sorted((t for t in tasks if t["due"]), key=lambda t: t["due"])
    undated = [t for t in tasks if not t["due"]]
    if dated or undated:
        out.append("## Tasks")
        for t in dated:
            out.append(
                f"- [{fmt_delta(t['days'])}] [{t['cat']}] {t['title']} ({t['due']})"
            )
        for t in undated:
            out.append(f"- [{t['cat']}] {t['title']}")
        out.append("")

    # Exams, soonest first.
    if exams:
        out.append("## Exams")
        for e in sorted(exams, key=lambda e: (e["date"] is None, e["date"])):
            when = fmt_delta(e["days"]) if e["days"] is not None else "no date"
            out.append(
                f"- [{e['cat']}] {e['title']} — {e['date']} ({when}) "
                f"— {e['progress']}% ready"
            )
        out.append("")

    # Recurring.
    if recurring:
        out.append("## Recurring")
        for r in recurring:
            suffix = f" | {r['freq']}" if r["freq"] else ""
            out.append(f"- [{r['cat']}] {r['title']}{suffix}")
        out.append("")

    if len(out) <= 2:
        out.append("_No active items. Add some to study.md / work.md / others.md._")

    PLAN.write_text("\n".join(out).rstrip("\n") + "\n")


def main():
    for cat, path in SOURCES.items():
        if path.exists():
            process_source(cat, path)
    append_done()
    write_plan()


if __name__ == "__main__":
    main()
