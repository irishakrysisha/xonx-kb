#!/bin/bash
# One-time Railway setup for the KB bot (run from bot/).
# NOTE: the free plan refused a second PROJECT ("resource provision limit"),
# so the bot lives as a second SERVICE inside the existing xonx-sales-bot
# project. Gotchas (learned on the sales bot):
#   * link the service first or `railway variables --set` hangs on a prompt
set -e
RAILWAY=~/.npm-global/bin/railway
SERVICE=xonx-kb-bot

$RAILWAY link --project xonx-sales-bot
$RAILWAY add --service "$SERVICE" || true   # no-op if it already exists
$RAILWAY service "$SERVICE"
$RAILWAY variables --set "ALLOWED_USERNAMES=irynaoliinykk" \
                   --set "KB_INBOX_FOLDER_ID=18qyoKX44Nk4UZK5To25P3DyiLJwUz2kH"
$RAILWAY up --service "$SERVICE" --detach

echo "Now run ./set_token_vars.sh <BOT_TOKEN> yourself (secrets must not pass through Claude)."
