# Arch Daily Plan Startup Task

On every KDE Plasma login this:

1. Runs `sync_study.py`, which rebuilds the `## Exams` section of `study.md`
   from the SS26 course files (`SS26/Exams.md` + `SS26/course-progress-report.md`).
2. Runs `aggregate.py`, which reads your three source files
   (`study.md`, `work.md`, `others.md`), archives finished items to `done.md`,
   and writes a sorted `plan.md` (overdue tasks and at-risk exams float to top).
3. Sends `plan.md` to the Groq API and shows a short daily plan
   (top 3 priorities + warnings) in a `kdialog` popup.

If you're offline or the API fails, it shows the raw (freshly aggregated)
`plan.md` instead.

## Files

| File | Purpose |
|------|---------|
| `daily-plan.sh` | Orchestrator (bash + curl + jq): sync → aggregate → Groq → popup. |
| `sync_study.py` | Rebuilds `study.md` exams from the SS26 course files. Stdlib only. |
| `aggregate.py` | Parses source files, archives done items, writes `plan.md`. Stdlib only. |
| `groq.env` | Holds `GROQ_API_KEY`. **Gitignored — never commit.** |
| `daily-plan.desktop` | XDG autostart entry. |

## Source files (in `/home/sudo/GoogleDrive/Planner/`)

You edit these; everything else is generated.

- **`study.md`** — `## Tasks` (one-off `- [ ]` items, optional `| due: DATE`).
  The `## Exams` section is **auto-generated** from the SS26 files each run —
  don't hand-edit it (changes are overwritten).
- **`work.md`** — `## Tasks` with `| due: DATE`.
- **`others.md`** — `## Recurring` (`- Name | freq: ...`, never archived) and
  `## Tasks`.
- **`plan.md`** — *generated* rollup (do not edit; overwritten each run).
- **`done.md`** — *generated* archive of completed items, tagged with date.

## SS26 exam sync

`sync_study.py` reads two read-only files in `/home/sudo/GoogleDrive/SS26/`:

- `Exams.md` — exam names + dates (no year; assumed 2026).
- `course-progress-report.md` — per-course completion %.

It matches course names across the two (normalised + fuzzy, so
"Basics Sustainability" ↔ "Basic Sustainability" and short names like
"Vibe Coding" resolve), then writes `study.md`'s `## Exams` section. Exams with
no matching progress entry default to `progress: 0%`; TBA/undated exams are
skipped.

### Rules

- Mark a task `- [x]` → it moves to `done.md` with today's date on the next run.
- An exam moves to `done.md` automatically once its `date` has passed.
- An exam is flagged **at risk** when it's within 7 days and below 70% progress.
- Wrap lines in `<!-- ... -->` to disable them without deleting.
- Dates are ISO format: `YYYY-MM-DD`.

## Install

1. Install the dialog tool (curl and jq are already present on most systems):

   ```bash
   sudo pacman -S kdialog
   ```

2. Make the script executable:

   ```bash
   chmod +x "daily-plan.sh"
   ```

3. Lock down the credentials file:

   ```bash
   chmod 600 groq.env
   ```

4. Enable autostart on login:

   ```bash
   cp daily-plan.desktop ~/.config/autostart/
   ```

## Configuration

Edit the variables at the top of `daily-plan.sh`:

- `PLAN_FILE` — path to your plan (default `/home/sudo/GoogleDrive/plan.md`).
- `GROQ_MODEL` — default `llama-3.3-70b-versatile`.
- `NET_RETRIES` / `NET_INTERVAL` — how long to wait for network at boot.

The API key lives only in `groq.env`:

```
GROQ_API_KEY=your_key_here
```

## Test

Run it manually from a terminal:

```bash
./daily-plan.sh
```

- **Offline fallback:** disconnect the network → expect the raw-plan popup.
- **Empty plan:** with an empty `plan.md` → expect the "nothing to plan" popup.

## Security

- `groq.env` is gitignored and should be `chmod 600`.
- If your key was ever exposed (e.g. pasted into a chat), **rotate it** at
  <https://console.groq.com>.
