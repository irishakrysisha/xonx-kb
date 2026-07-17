"""X-ON-X KB bot — drop a file in Telegram, it lands in the Knowledge Base _Inbox.

Flow: whitelist gate -> download from Telegram -> upload to Drive _Inbox ->
confirmation. Classification is NOT done here — the hourly cloud routine
(kb_sortuvalnyk) picks new files up from _Inbox as usual.
"""
import asyncio
import html
import logging
import re

from telegram import Message, Update
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import (
    Application, CommandHandler, ContextTypes, MessageHandler, filters,
)

from .config import load_settings
from .drive import DriveInbox

logging.basicConfig(format="%(asctime)s %(name)s %(levelname)s %(message)s",
                    level=logging.INFO)
log = logging.getLogger("kb_bot")

MAX_FILE_BYTES = 20 * 1024 * 1024  # Telegram Bot API download ceiling
FLUSH_SECONDS = 45  # silence gap that closes a text batch

WELCOME = (
    "Це бот X-ON-X Knowledge Base.\n\n"
    "Кидай сюди файл (документ або фото-скан) або пересилай повідомлення — "
    "я збережу все в KB Inbox. Протягом години Сортувальник класифікує "
    "і додасть чернетку в каталог.\n\n"
    "Серія переслених повідомлень підряд склеюється в один документ. "
    "Підпис до файлу (caption) збережеться як нотатка для рев'ю."
)
NO_ACCESS = "Немає доступу. Якщо ти з команди X-ON-X — напиши Ірині, щоб додала тебе."
TOO_BIG = ("Файл завеликий: Telegram дозволяє ботам скачувати до 20 MB. "
           "Залий його, будь ласка, напряму в Drive-папку KB _Inbox.")


def build_description(username: str | None, when: str, caption: str | None) -> str:
    """Drive file description shown to the reviewer, ignored by the sorter."""
    who = f"@{username}" if username else "невідомий користувач"
    desc = f"Від {who} через KB bot, {when}"
    if caption and caption.strip():
        desc += f"\nНотатка: {caption.strip()}"
    return desc


def forward_label(msg: Message) -> str | None:
    """Human label of where a forwarded message came from, else None."""
    origin = getattr(msg, "forward_origin", None)
    if origin is None:
        return None
    user = getattr(origin, "sender_user", None)
    if user is not None:
        return user.full_name
    hidden = getattr(origin, "sender_user_name", None)
    if hidden:
        return hidden
    chat = getattr(origin, "chat", None) or getattr(origin, "sender_chat", None)
    if chat is not None:
        return chat.title or chat.username or "чат"
    return "невідоме джерело"


def format_entry(label: str | None, text: str) -> str:
    """One message inside a batched .txt: forwarded ones keep their origin."""
    return f"[Переслано від {label}]\n{text}" if label else text


def text_filename(first_text: str, when) -> str:
    """Readable .txt name from the first message + timestamp."""
    stem = " ".join(first_text.split())
    if len(stem) > 40:
        stem = stem[:40]
        if " " in stem[20:]:  # cut at a word boundary when one is near
            stem = stem[:stem.rindex(" ")]
    stem = re.sub(r'[\\/:*?"<>|]', "-", stem.strip(" .")) or "Повідомлення"
    return f"{stem} — TG {when:%Y-%m-%d %H%M}.txt"


class KBBot:
    def __init__(self, settings, inbox: DriveInbox):
        self.settings = settings
        self.inbox = inbox
        # chat_id -> {"entries": [str], "job": Job, "first": str,
        #             "date": datetime, "username": str|None, "count": int}
        self._pending: dict[int, dict] = {}

    def _gate(self, update: Update) -> bool:
        user = update.effective_user
        return self.settings.is_allowed(user.username if user else None)

    async def start(self, update: Update, _: ContextTypes.DEFAULT_TYPE):
        if not self._gate(update):
            await update.message.reply_text(NO_ACCESS)
            return
        await update.message.reply_text(WELCOME)

    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Collect texts (typed or forwarded) into a per-chat batch; a pause of
        FLUSH_SECONDS closes the batch and saves it as one .txt in _Inbox."""
        msg = update.message
        if msg is None or not msg.text:
            return
        if not self._gate(update):
            await msg.reply_text(NO_ACCESS)
            return
        chat_id = msg.chat_id
        user = update.effective_user
        pend = self._pending.setdefault(chat_id, {
            "entries": [], "job": None, "first": msg.text, "date": msg.date,
            "username": user.username if user else None, "count": 0,
        })
        pend["entries"].append(format_entry(forward_label(msg), msg.text))
        pend["count"] += 1
        if pend["job"]:
            pend["job"].schedule_removal()
        pend["job"] = context.job_queue.run_once(
            self._flush_texts, FLUSH_SECONDS, chat_id=chat_id)

    async def _flush_texts(self, context: ContextTypes.DEFAULT_TYPE):
        chat_id = context.job.chat_id
        pend = self._pending.pop(chat_id, None)
        if not pend:
            return
        name = text_filename(pend["first"], pend["date"])
        content = "\n\n".join(pend["entries"])
        description = build_description(
            pend["username"], f"{pend['date']:%d.%m.%Y %H:%M} UTC",
            f"{pend['count']} повідомлень" if pend["count"] > 1 else None)
        try:
            final, link = await asyncio.to_thread(
                self.inbox.upload, content.encode("utf-8"), name,
                "text/plain", description)
        except Exception:
            log.exception("Drive upload failed for text batch %s", name)
            await context.bot.send_message(
                chat_id, "Не вдалося зберегти текст у Drive. Спробуй ще раз.")
            return
        log.info("saved text batch %s (%d msgs) from @%s", final,
                 pend["count"], pend["username"] or "?")
        extra = f" ({pend['count']} повідомлень)" if pend["count"] > 1 else ""
        text = (f"Збережено в KB Inbox: <b>{html.escape(final)}</b>{extra}\n"
                "Класифікація — протягом години.")
        if link:
            text += f'\n<a href="{link}">Файл на Drive</a>'
        await context.bot.send_message(chat_id, text, parse_mode=ParseMode.HTML,
                                       disable_web_page_preview=True)

    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        msg = update.message
        if msg is None or msg.document is None:
            return
        doc = msg.document
        name = doc.file_name or f"document_{msg.date:%Y-%m-%d_%H%M%S}"
        await self._save(update, context, doc.file_id, doc.file_size, name,
                         doc.mime_type or "")

    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        msg = update.message
        if msg is None or not msg.photo:
            return
        photo = msg.photo[-1]  # largest size
        name = f"photo_{msg.date:%Y-%m-%d_%H%M%S}.jpg"
        await self._save(update, context, photo.file_id, photo.file_size, name,
                         "image/jpeg")

    async def _save(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                    file_id: str, file_size: int | None, name: str, mime: str):
        msg = update.message
        if not self._gate(update):
            await msg.reply_text(NO_ACCESS)
            return
        if file_size and file_size > MAX_FILE_BYTES:
            await msg.reply_text(TOO_BIG)
            return
        try:
            tg_file = await context.bot.get_file(file_id)
            data = bytes(await tg_file.download_as_bytearray())
        except TelegramError as e:
            log.warning("download failed for %s: %s", name, e)
            if "too big" in str(e).lower():
                await msg.reply_text(TOO_BIG)
            else:
                await msg.reply_text("Не вдалося скачати файл із Telegram. Спробуй ще раз.")
            return
        user = update.effective_user
        description = build_description(user.username if user else None,
                                        f"{msg.date:%d.%m.%Y %H:%M} UTC", msg.caption)
        try:
            final, link = await asyncio.to_thread(
                self.inbox.upload, data, name, mime, description)
        except Exception:
            log.exception("Drive upload failed for %s", name)
            await msg.reply_text("Не вдалося зберегти в Drive. Спробуй ще раз "
                                 "або залий файл у _Inbox вручну.")
            return
        log.info("saved %s (%d bytes) from @%s", final, len(data),
                 user.username if user else "?")
        text = (f"Збережено в KB Inbox: <b>{html.escape(final)}</b>\n"
                "Класифікація — протягом години.")
        if link:
            text += f'\n<a href="{link}">Файл на Drive</a>'
        await msg.reply_text(text, parse_mode=ParseMode.HTML,
                             disable_web_page_preview=True)


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE):
    log.exception("Unhandled error", exc_info=context.error)


def main():
    settings = load_settings()
    if not settings.allowed_usernames:
        log.warning("ALLOWED_USERNAMES is empty — the bot will reject everyone")
    inbox = DriveInbox(settings.inbox_folder_id, settings.google_token_json)
    app = Application.builder().token(settings.bot_token).build()
    bot = KBBot(settings, inbox)
    app.add_handler(CommandHandler("start", bot.start))
    app.add_handler(MessageHandler(filters.Document.ALL, bot.handle_document))
    app.add_handler(MessageHandler(filters.PHOTO, bot.handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_text))
    app.add_error_handler(on_error)
    log.info("KB bot polling; inbox folder %s; %d allowed users",
             settings.inbox_folder_id, len(settings.allowed_usernames))
    app.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()
