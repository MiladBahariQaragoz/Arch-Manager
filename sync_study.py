#!/usr/bin/env python3
"""Regenerate the ## Exams section of study.md from the SS26 course files.

Sources (read-only):
  - SS26/Exams.md                 -> exam names + dates (no year; assumed 2026)
  - SS26/course-progress-report.md-> per-course completion %

Course names differ slightly between the two files (e.g. "Basics Sustainability"
vs "Basic Sustainability"), so progress is matched with normalisation + fuzzy
fallback. The ## Tasks section of study.md is left untouched.

Pure standard library — no third-party dependencies.
"""

import datetime
import difflib
import re
from pathlib import Path

DRIVE = Path("/home/sudo/GoogleDrive")
SS26 = DRIVE / "SS26"
EXAMS_SRC = SS26 / "Exams.md"
PROGRESS_SRC = SS26 / "course-progress-report.md"
STUDY = DRIVE / "Planner" / "study.md"

EXAM_YEAR = 2026
FUZZY_CUTOFF = 0.85

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
}


def norm(text):
    """Normalise a course name for matching: drop parens, keep [a-z0-9]."""
    text = re.sub(r"\(.*?\)", "", text)
    return re.sub(r"[^a-z0-9]", "", text.lower())


def parse_progress():
    """Return {course_name: percent_int} from the progress report table."""
    out = {}
    if not PROGRESS_SRC.exists():
        return out
    for line in PROGRESS_SRC.read_text().splitlines():
        # | [Name](path) | Type | Credits | 54% (21/39) |
        m = re.match(r"^\|\s*\[(.+?)\]", line)
        if not m:
            continue
        pct = re.search(r"(\d+)\s*%", line)
        if pct:
            out[m.group(1).strip()] = int(pct.group(1))
    return out


def parse_exams():
    """Return list of (name, date) for exams with a parseable date."""
    out = []
    if not EXAMS_SRC.exists():
        return out
    for line in EXAMS_SRC.read_text().splitlines():
        # - **Name**: Month DD (optional note)
        m = re.match(r"^\s*-\s+\*\*(.+?)\*\*\s*:\s*(.+)$", line)
        if not m:
            continue
        name = m.group(1).strip()
        dm = re.search(r"([A-Za-z]+)\s+(\d{1,2})", m.group(2))
        if not dm:
            continue
        month = MONTHS.get(dm.group(1).lower())
        if not month:
            continue
        try:
            date = datetime.date(EXAM_YEAR, month, int(dm.group(2)))
        except ValueError:
            continue
        out.append((name, date))
    return out


def match_progress(exam_name, progress):
    ne = norm(exam_name)
    best_pct, best_score = None, 0.0
    for cname, pct in progress.items():
        nc = norm(cname)
        if not nc:
            continue
        if ne == nc or ne in nc or nc in ne:
            return pct
        score = difflib.SequenceMatcher(None, ne, nc).ratio()
        if score > best_score:
            best_score, best_pct = score, pct
    return best_pct if best_score >= FUZZY_CUTOFF else None


def build_exam_lines():
    progress = parse_progress()
    exams = sorted(parse_exams(), key=lambda e: e[1])
    lines = [
        "<!-- Auto-generated from SS26/Exams.md + course-progress-report.md. "
        "Edits here are overwritten each run. -->"
    ]
    for name, date in exams:
        pct = match_progress(name, progress)
        pct = pct if pct is not None else 0
        lines.append(f"- {name} | date: {date.isoformat()} | progress: {pct}%")
    return lines


def write_exams_section(exam_lines):
    if STUDY.exists():
        text = STUDY.read_text()
    else:
        text = "# Study\n\n## Tasks\n"
    lines = text.splitlines()

    out, i, replaced = [], 0, False
    while i < len(lines):
        header = re.match(r"^##\s+(.*)$", lines[i])
        if header and header.group(1).strip().lower().startswith("exam"):
            out.append(lines[i])  # keep the "## Exams" header
            i += 1
            while i < len(lines) and not re.match(r"^##\s+", lines[i]):
                i += 1  # drop old section body
            out.extend(exam_lines)
            out.append("")
            replaced = True
            continue
        out.append(lines[i])
        i += 1

    if not replaced:
        if out and out[-1].strip():
            out.append("")
        out.append("## Exams")
        out.extend(exam_lines)
        out.append("")

    STUDY.write_text("\n".join(out).rstrip("\n") + "\n")


def main():
    write_exams_section(build_exam_lines())


if __name__ == "__main__":
    main()
