#!/usr/bin/env bash
#
# daily-plan.sh
# On KDE login: read plan.md, ask Groq for today's top priorities + warnings,
# show the result in a kdialog popup. Falls back to the raw plan when offline
# or the API fails.

set -uo pipefail

# --- Config ---------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLAN_FILE="/home/sudo/GoogleDrive/plan.md"
ENV_FILE="${SCRIPT_DIR}/groq.env"
GROQ_MODEL="llama-3.3-70b-versatile"
GROQ_URL="https://api.groq.com/openai/v1/chat/completions"

NET_RETRIES=6          # number of connectivity attempts
NET_INTERVAL=10        # seconds between attempts
TEXTBOX_THRESHOLD=1500 # chars above which we use a scrollable textbox

INSTRUCTION="Read the plan below. Output the top 3 priorities to achieve today \
as a short numbered list, followed by a short 'Warnings:' section noting \
anything to be careful about, avoid, or any approaching deadlines/risks. \
Be concise — this is shown in a small startup popup."

# --- Helpers --------------------------------------------------------------

# Show text in a popup. Uses a scrollable textbox for long content.
show_popup() {
    local title="$1" body="$2"
    if (( ${#body} > TEXTBOX_THRESHOLD )); then
        local tmp
        tmp="$(mktemp --suffix=.txt)"
        printf '%s\n' "$body" >"$tmp"
        kdialog --title "$title" --textbox "$tmp" 700 500
        rm -f "$tmp"
    else
        kdialog --title "$title" --msgbox "$body"
    fi
}

# Show the raw plan with an offline header, then exit.
fallback_raw() {
    local reason="$1"
    show_popup "Daily Plan — ⚠️ Offline" \
        "⚠️ ${reason} — showing raw plan.md:

${PLAN_CONTENT}"
    exit 0
}

# Return 0 if Groq is reachable.
net_up() {
    curl -s --max-time 5 -o /dev/null "https://api.groq.com"
}

# --- Main -----------------------------------------------------------------

# Aggregate study/work/others into plan.md and archive done items.
# Runs offline-safe and independent of the API; failures must not abort.
if [[ -f "${SCRIPT_DIR}/aggregate.py" ]]; then
    python3 "${SCRIPT_DIR}/aggregate.py" || true
fi

# Load API key.
if [[ -f "$ENV_FILE" ]]; then
    # shellcheck disable=SC1090
    source "$ENV_FILE"
fi
GROQ_API_KEY="${GROQ_API_KEY:-}"

# Read plan.
if [[ ! -f "$PLAN_FILE" ]]; then
    kdialog --title "Daily Plan" --error "plan.md not found at ${PLAN_FILE}"
    exit 1
fi
PLAN_CONTENT="$(cat "$PLAN_FILE")"

# Empty plan -> nothing to do.
if [[ -z "${PLAN_CONTENT// /}" ]]; then
    kdialog --title "Daily Plan" --msgbox "plan.md is empty — nothing to plan today."
    exit 0
fi

# No key -> fall back to raw plan.
if [[ -z "$GROQ_API_KEY" ]]; then
    fallback_raw "No GROQ_API_KEY configured"
fi

# Wait for network.
online=false
for ((i = 1; i <= NET_RETRIES; i++)); do
    if net_up; then
        online=true
        break
    fi
    sleep "$NET_INTERVAL"
done
$online || fallback_raw "No network after $((NET_RETRIES * NET_INTERVAL))s"

# Build request payload safely with jq.
PAYLOAD="$(jq -n \
    --arg model "$GROQ_MODEL" \
    --arg sys "You are a focused daily planner. ${INSTRUCTION}" \
    --arg plan "$PLAN_CONTENT" \
    '{
        model: $model,
        messages: [
            {role: "system", content: $sys},
            {role: "user", content: $plan}
        ],
        temperature: 0.4
    }')"

# Call Groq.
RESPONSE="$(curl -s --max-time 30 -w '\n%{http_code}' "$GROQ_URL" \
    -H "Authorization: Bearer ${GROQ_API_KEY}" \
    -H "Content-Type: application/json" \
    -d "$PAYLOAD")"
CURL_RC=$?

HTTP_CODE="$(tail -n1 <<<"$RESPONSE")"
BODY="$(sed '$d' <<<"$RESPONSE")"

if (( CURL_RC != 0 )) || [[ "$HTTP_CODE" != "200" ]]; then
    fallback_raw "API request failed (curl=${CURL_RC}, http=${HTTP_CODE})"
fi

CONTENT="$(jq -r '.choices[0].message.content // empty' <<<"$BODY")"
if [[ -z "$CONTENT" ]]; then
    fallback_raw "Empty response from Groq"
fi

show_popup "Daily Plan — $(date '+%A %d %b')" "$CONTENT"
