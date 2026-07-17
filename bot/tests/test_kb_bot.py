import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import datetime

from src.bot import build_description, format_entry, forward_label, text_filename
from src.config import Settings
from src.drive import unique_name


def _settings(**kw):
    kw.setdefault("BOT_TOKEN", "x")
    return Settings(_env_file=None, **kw)


# ---- whitelist -----------------------------------------------------------

def test_allowed_usernames_parsing_and_gate():
    s = _settings(ALLOWED_USERNAMES="@Iryna_O, oleg_kotliar , ,Viktoriia_Kotliar")
    assert s.allowed_usernames == ["iryna_o", "oleg_kotliar", "viktoriia_kotliar"]
    assert s.is_allowed("iryna_o")
    assert s.is_allowed("@IRYNA_O")
    assert not s.is_allowed("stranger")
    assert not s.is_allowed(None)


def test_empty_whitelist_rejects_everyone():
    s = _settings()
    assert s.allowed_usernames == []
    assert not s.is_allowed("anyone")


# ---- name collisions -----------------------------------------------------

def test_unique_name_no_collision():
    assert unique_name("a.docx", {"b.docx"}) == "a.docx"


def test_unique_name_suffixes():
    assert unique_name("a.docx", {"a.docx"}) == "a (2).docx"
    assert unique_name("a.docx", {"a.docx", "a (2).docx"}) == "a (3).docx"


def test_unique_name_already_suffixed():
    assert unique_name("a (2).docx", {"a (2).docx"}) == "a (3).docx"


def test_unique_name_no_extension():
    assert unique_name("scan", {"scan"}) == "scan (2)"


# ---- reviewer note -------------------------------------------------------

def test_description_with_caption():
    d = build_description("iryna_o", "07.07.2026 12:00 UTC", " договір для KB ")
    assert d == "Від @iryna_o через KB bot, 07.07.2026 12:00 UTC\nНотатка: договір для KB"


def test_description_without_username_or_caption():
    d = build_description(None, "07.07.2026 12:00 UTC", None)
    assert d == "Від невідомий користувач через KB bot, 07.07.2026 12:00 UTC"


# ---- text batches --------------------------------------------------------

class _Obj:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def test_forward_label_variants():
    assert forward_label(_Obj(forward_origin=None)) is None
    assert forward_label(_Obj(forward_origin=_Obj(
        sender_user=_Obj(full_name="Іван Клієнт")))) == "Іван Клієнт"
    assert forward_label(_Obj(forward_origin=_Obj(
        sender_user=None, sender_user_name="Hidden Guy"))) == "Hidden Guy"
    assert forward_label(_Obj(forward_origin=_Obj(
        sender_user=None, sender_user_name=None,
        chat=_Obj(title="Робочий чат", username=None)))) == "Робочий чат"


def test_format_entry():
    assert format_entry(None, "привіт") == "привіт"
    assert format_entry("Іван", "привіт") == "[Переслано від Іван]\nпривіт"


def test_text_filename():
    when = datetime(2026, 7, 7, 15, 30)
    name = text_filename("Питання по SPA: чи можна закрити угоду без нотаріуса?", when)
    assert name == "Питання по SPA- чи можна закрити угоду — TG 2026-07-07 1530.txt"
    assert text_filename("коротке", when) == "коротке — TG 2026-07-07 1530.txt"
    assert text_filename("   ", when) == "Повідомлення — TG 2026-07-07 1530.txt"
