# Arch Daily Plan Startup Task — Design

**Date:** 2026-06-28
**Status:** Approved

## Purpose

On every KDE Plasma login, read the user's `plan.md`, send it to the Groq
chat API, and show a short, actionable daily plan (top priorities + warnings)
in an unmissable popup. If the network is unavailable, fall back to showing
the raw plan so the user always sees something.

## User-Facing Behaviour

1. User logs into KDE Plasma.
2. A `kdialog` popup appears, centered, and must be dismissed.
3. The popup contains: **top 3 priorities for today + any warnings**, derived
   from `plan.md` by Groq.
4. If offline after retries, or the API fails, the popup instead shows the raw
   `plan.md` contents prefixed with an "⚠️ Offline — showing raw plan" header.
5. If `plan.md` is empty, the popup says the plan is empty.

## Architecture

```
KDE login
   │
   ▼
~/.config/autostart/daily-plan.desktop   (XDG autostart entry)
   │  exec
   ▼
daily-plan.sh
   ├─ load GROQ_API_KEY from groq.env
   ├─ read /home/sudo/GoogleDrive/plan.md
   ├─ if empty → kdialog "plan empty" → exit
   ├─ wait for network (retry ~6× / 60s)
   │     └─ still offline → kdialog raw plan (offline header) → exit
   ├─ POST plan + instruction → Groq chat completions
   │     └─ curl/jq error or non-200 → kdialog raw plan (offline header) → exit
   └─ kdialog show Groq result
```

## Components

All live under `~/Documents/Arch Manager/` unless noted.

| File | Purpose |
|------|---------|
| `daily-plan.sh` | Main logic. Bash + `curl` + `jq`. Executable. |
| `groq.env` | `GROQ_API_KEY=...`, `chmod 600`. Sourced by the script. Never committed. |
| `daily-plan.desktop` | XDG autostart entry; copied to `~/.config/autostart/`. |
| `README.md` | Install, test, and rotate-key instructions. |

## Key Logic Details

### Config
- `PLAN_FILE="/home/sudo/GoogleDrive/plan.md"`
- `GROQ_MODEL="llama-3.3-70b-versatile"`
- `GROQ_URL="https://api.groq.com/openai/v1/chat/completions"`
- API key read from `groq.env` (same dir as script).

### Network wait
- Loop up to 6 times, 10s apart, testing connectivity (e.g.
  `curl -sf --max-time 5 https://api.groq.com` or ping a reliable host).
- Break early once reachable.

### Groq request
- System prompt: instruct the model to act as a focused daily planner.
- User content: the contents of `plan.md`.
- Instruction (style A): "Read the plan below. Output the top 3 priorities to
  achieve today as a short numbered list, followed by a short 'Warnings:'
  section noting anything to be careful about or avoid. Be concise — this is a
  startup popup. If the plan implies deadlines or risks, surface them."
- Parse response with `jq -r '.choices[0].message.content'`.
- Build JSON payload safely with `jq` (not string interpolation) to avoid
  breaking on quotes/newlines in `plan.md`.

### Output
- Use `kdialog --title "Daily Plan" --msgbox "<text>"` for normal output.
- For long content, prefer `kdialog --textbox` via a temp file so it scrolls.
- Decision: detect length / default to `--msgbox`; switch to a temp-file
  `--textbox` if output exceeds a threshold (e.g. > 1500 chars).

### Failure / fallback
- Any of: empty key, network unreachable after retries, curl non-zero,
  HTTP non-200, empty/`null` model content → show raw `plan.md` with the
  offline header.

## Dependencies

- `kdialog` — install via `sudo pacman -S kdialog` (missing on this system).
- `curl`, `jq` — already present.

## Security

- API key stored only in `groq.env` with `chmod 600`; not in the script,
  not in the `.desktop` file, not committed to git.
- **Action item:** the key was shared in plain chat and must be rotated at
  console.groq.com.

## Testing

- Run `daily-plan.sh` manually from a terminal (normal path).
- Simulate offline: temporarily point `GROQ_URL` to an unreachable host or
  disable network → verify raw-plan fallback.
- Empty plan: verify the "plan empty" popup.
- Long plan: verify `--textbox` scroll path.

## Out of Scope (YAGNI)

- Scheduling more than once per login (no cron/timer).
- Editing or writing back to `plan.md`.
- Multiple LLM providers / model fallback.
- Logging/history of past daily plans.
