#!/usr/bin/env bash
###############################################################################
# ERP SOLUTION — Deployment Notification Script
# Usage: ./scripts/notify.sh [event] [environment] [version] [status] [details]
###############################################################################

set -euo pipefail

EVENT="${1:-deploy_started}"
ENVIRONMENT="${2:-production}"
VERSION="${3:-latest}"
STATUS="${4:-info}"
DETAILS="${5:-}"

SLACK_WEBHOOK_URL="${SLACK_WEBHOOK_URL:-}"
DISCORD_WEBHOOK_URL="${DISCORD_WEBHOOK_URL:-}"
TEAMS_WEBHOOK_URL="${TEAMS_WEBHOOK_URL:-}"
EMAIL_RECIPIENTS="${EMAIL_RECIPIENTS:-}"

# Color mapping
case "${STATUS}" in
    success) COLOR="good"; EMOJI="✅" ;;
    failure) COLOR="danger"; EMOJI="❌" ;;
    warning) COLOR="warning"; EMOJI="⚠️" ;;
    *) COLOR="#439FE0"; EMOJI="ℹ️" ;;
esac

TIMESTAMP=$(date -u '+%Y-%m-%d %H:%M:%S UTC')
HOSTNAME=$(hostname)
COMMIT_SHA="${GITHUB_SHA:-$(git rev-parse --short HEAD 2>/dev/null || echo 'unknown')}"
REPO_URL="https://github.com/${GITHUB_REPOSITORY:-unknown}"

send_slack() {
    local webhook_url="$1"
    local payload
    
    payload=$(cat <<EOF
{
  "attachments": [{
    "color": "${COLOR}",
    "title": "${EMOJI} ERP Deployment: ${EVENT}",
    "fields": [
      {"title": "Environment", "value": "${ENVIRONMENT}", "short": true},
      {"title": "Version", "value": "${VERSION}", "short": true},
      {"title": "Status", "value": "${STATUS}", "short": true},
      {"title": "Commit", "value": "<${REPO_URL}/commit/${COMMIT_SHA}|${COMMIT_SHA}>", "short": true},
      {"title": "Time", "value": "${TIMESTAMP}", "short": true},
      {"title": "Host", "value": "${HOSTNAME}", "short": true}
    ],
    "footer": "ERP SOLUTION Deploy Bot",
    "ts": $(date +%s)
  }]
}
EOF
)
    
    if [ -n "${DETAILS}" ]; then
        payload=$(echo "${payload}" | jq --arg details "${DETAILS}" '.attachments[0].fields += [{"title": "Details", "value": $details, "short": false}]')
    fi
    
    curl -s -X POST -H 'Content-type: application/json' --data "${payload}" "${webhook_url}" > /dev/null
}

send_discord() {
    local webhook_url="$1"
    local payload
    
    payload=$(cat <<EOF
{
  "embeds": [{
    "title": "${EMOJI} ERP Deployment: ${EVENT}",
    "color": $(printf '%d' 0x${COLOR//good/2ECC71} 2>/dev/null || printf '%d' 0x${COLOR//danger/E74C3C} 2>/dev/null || printf '%d' 0x${COLOR//warning/F39C12} 2>/dev/null || echo 4436192),
    "fields": [
      {"name": "Environment", "value": "${ENVIRONMENT}", "inline": true},
      {"name": "Version", "value": "${VERSION}", "inline": true},
      {"name": "Status", "value": "${STATUS}", "inline": true},
      {"name": "Commit", "value": "[${COMMIT_SHA}](${REPO_URL}/commit/${COMMIT_SHA})", "inline": true},
      {"name": "Time", "value": "${TIMESTAMP}", "inline": true},
      {"name": "Host", "value": "${HOSTNAME}", "inline": true}
    ],
    "footer": {"text": "ERP SOLUTION Deploy Bot"},
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%S.000Z)"
  }]
}
EOF
)
    
    if [ -n "${DETAILS}" ]; then
        payload=$(echo "${payload}" | jq --arg details "${DETAILS}" '.embeds[0].fields += [{"name": "Details", "value": $details, "inline": false}]')
    fi
    
    curl -s -X POST -H 'Content-type: application/json' --data "${payload}" "${webhook_url}" > /dev/null
}

send_teams() {
    local webhook_url="$1"
    local payload
    
    payload=$(cat <<EOF
{
  "@type": "MessageCard",
  "@context": "http://schema.org/extensions",
  "themeColor": "${COLOR//good/2ECC71}",
  "summary": "ERP Deployment: ${EVENT}",
  "sections": [{
    "activityTitle": "${EMOJI} ERP Deployment: ${EVENT}",
    "activitySubtitle": "Environment: ${ENVIRONMENT} | Version: ${VERSION}",
    "facts": [
      {"name": "Status", "value": "${STATUS}"},
      {"name": "Commit", "value": "${COMMIT_SHA}"},
      {"name": "Time", "value": "${TIMESTAMP}"},
      {"name": "Host", "value": "${HOSTNAME}"}
    ],
    "markdown": true
  }]
}
EOF
)
    
    if [ -n "${DETAILS}" ]; then
        payload=$(echo "${payload}" | jq --arg details "${DETAILS}" '.sections[0].facts += [{"name": "Details", "value": $details}]')
    fi
    
    curl -s -X POST -H 'Content-type: application/json' --data "${payload}" "${webhook_url}" > /dev/null
}

send_email() {
    local recipients="$1"
    local subject="ERP Deployment: ${EVENT} - ${ENVIRONMENT} - ${STATUS}"
    local body="ERP Deployment Notification

Event: ${EVENT}
Environment: ${ENVIRONMENT}
Version: ${VERSION}
Status: ${STATUS}
Commit: ${COMMIT_SHA}
Time: ${TIMESTAMP}
Host: ${HOSTNAME}
Repository: ${REPO_URL}

${DETAILS}

---
This is an automated message from ERP SOLUTION Deploy Bot.
"
    
    if command -v sendmail &> /dev/null; then
        echo -e "Subject: ${subject}\n\n${body}" | sendmail "${recipients}"
    elif command -v mail &> /dev/null; then
        echo "${body}" | mail -s "${subject}" "${recipients}"
    else
        echo "No email client available (sendmail/mail)"
        return 1
    fi
}

main() {
    echo "Sending deployment notification..."
    echo "  Event: ${EVENT}"
    echo "  Environment: ${ENVIRONMENT}"
    echo "  Version: ${VERSION}"
    echo "  Status: ${STATUS}"
    
    local sent=false
    
    if [ -n "${SLACK_WEBHOOK_URL}" ]; then
        send_slack "${SLACK_WEBHOOK_URL}"
        echo "  ✓ Slack notification sent"
        sent=true
    fi
    
    if [ -n "${DISCORD_WEBHOOK_URL}" ]; then
        send_discord "${DISCORD_WEBHOOK_URL}"
        echo "  ✓ Discord notification sent"
        sent=true
    fi
    
    if [ -n "${TEAMS_WEBHOOK_URL}" ]; then
        send_teams "${TEAMS_WEBHOOK_URL}"
        echo "  ✓ Teams notification sent"
        sent=true
    fi
    
    if [ -n "${EMAIL_RECIPIENTS}" ]; then
        if send_email "${EMAIL_RECIPIENTS}"; then
            echo "  ✓ Email notification sent"
            sent=true
        fi
    fi
    
    if [ "${sent}" = "false" ]; then
        echo "  ⚠ No notification channels configured"
    fi
}

main "$@"