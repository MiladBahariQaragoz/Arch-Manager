# Arch Daily Plan Startup Task

On every KDE Plasma login, this reads your `plan.md`, sends it to the Groq API,
and shows a short daily plan (top 3 priorities + warnings) in a `kdialog` popup.
If you're offline or the API fails, it shows the raw `plan.md` instead.

## Files

| File | Purpose |
|------|---------|
| `daily-plan.sh` | Main logic (bash + curl + jq). |
| `groq.env` | Holds `GROQ_API_KEY`. **Gitignored — never commit.** |
| `daily-plan.desktop` | XDG autostart entry. |

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
