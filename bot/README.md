# X-ON-X KB bot

Telegram bot: drop a file → it lands in the Knowledge Base `_Inbox` folder on
Drive. Classification is done downstream by the hourly cloud routine
(`kb_sortuvalnyk` → Inbox tab of the catalog spreadsheet), not by the bot.

## What it does

- Accepts **documents** and **photos** (scans) from whitelisted team members.
- Uploads to the `_Inbox` Drive folder (shared drive «X-ON-X Legal»),
  keeping the original filename (` (2)` suffix on collision).
- The Telegram caption + sender + date go into the Drive file *description* —
  visible to the reviewer, ignored by the sorter.
- Replies with a confirmation + Drive link.
- Telegram limit: bots can download files up to **20 MB**; bigger files must
  go to Drive directly.

## Layout

- `src/config.py` — env settings (`BOT_TOKEN`, `ALLOWED_USERNAMES`,
  `KB_INBOX_FOLDER_ID`, `GOOGLE_TOKEN_JSON`)
- `src/drive.py` — Drive auth + upload (`supportsAllDrives` everywhere)
- `src/bot.py` — handlers, polling entry point (`python -m src.bot`)
- `tests/` — pure-logic tests (`python3 -m pytest tests/ -q`)

## Deploy (Railway)

```
./railway_deploy.sh        # once: create service, set non-secret vars
./set_token_vars.sh <BOT_TOKEN>   # run yourself: secrets
```

Local run: copy `.env.example` → `.env`, fill `BOT_TOKEN`, then
`python -m src.bot` (uses `~/.claude-sheets/token.json` for Google).
