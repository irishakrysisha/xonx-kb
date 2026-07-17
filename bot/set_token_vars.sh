#!/bin/bash
# Run this YOURSELF (via the `!` prefix in Claude Code or a plain terminal):
#   ./set_token_vars.sh <BOT_TOKEN>
# Sets the two secrets on the Railway service without them passing through chat.
set -e
RAILWAY=~/.npm-global/bin/railway
SERVICE=xonx-kb-bot

if [ -z "$1" ]; then echo "usage: ./set_token_vars.sh <BOT_TOKEN>"; exit 1; fi

$RAILWAY service "$SERVICE"
$RAILWAY variables --set "BOT_TOKEN=$1" \
                   --set "GOOGLE_TOKEN_JSON=$(cat ~/.claude-sheets/token.json)"
echo "Done. Railway redeploys automatically on var change."
