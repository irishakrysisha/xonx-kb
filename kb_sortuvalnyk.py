"""Сортувальник — AI, що розбирає кинуте і кладе чернетку в Inbox.

Роль (з дизайну): людина кидає сирий артефакт; Сортувальник визначає тип,
категорію, юрисдикцію, пише короткий опис і пропонує картку через kb_api.propose()
→ вона лягає в Inbox (staging = needs-review), поки сеньйор не гляне.

Два режими:
  * LLM (Anthropic Claude) — якщо є ANTHROPIC_API_KEY і пакет anthropic;
  * fallback за маркерами — детермінований розбір без ключа (працює завжди).

    from kb_sortuvalnyk import Sortuvalnyk
    s = Sortuvalnyk()
    s.intake("Іван Петренко, нотаріус, Київ, +380...")   # -> INB-XXXX у Inbox
"""
import os
import re

from kb_api import KB
from kb_schema import (NAME_COL, SUMMARY_COL, RELATED_COL, TAXONOMY_VALUES,
                       COLUMN_VALIDATION)

CATS = TAXONOMY_VALUES["Категорія"]
JURS = TAXONOMY_VALUES["Юрисдикція"]
SERVICE_TYPES = TAXONOMY_VALUES["Тип послуги"]
SPHERES = TAXONOMY_VALUES["Сфера"]

# --- маркери для fallback-класифікації --------------------------------------
_CAT_KEYWORDS = {
    "1.1 Договірні":         ["nda", "договір", "угод", "contract", "mou", "term sheet", "ліценз"],
    "1.2 Корпоративні":      ["статут", "засновник", "корпоратив", "довірен", "реорганіз", "протокол збор"],
    "1.3 Інвестиційні":      ["safe", "інвест", "sha", "spa", "share", "vesting", "cap table", "convertible", "subscription"],
    "1.4 Трудові / HR":      ["трудов", "employment", "цпд", "esop", "опціон", "наказ",
                              "працівник", "звільн", "кзпп", "non-compete", "non compete"],
    "1.5 Внутрішні політики": ["privacy", "policy", "cookie", "gdpr", "dpa", "політик"],
    "1.6 Регулятори / Суди": ["позов", "претензі", "demand", "суд", "податков", "регулятор", "апеляц", "звернення"],
}
# сфери права для рісьорчів (свій набір, не документні 1.1–1.6)
_SPHERE_KEYWORDS = {
    "Податкове":               ["податок", "пдв", "єдиний податок", "пку", "оподатк", "tax", "акциз"],
    "Валютне / ЗЕД":           ["валют", "зед", "нерезидент", "експорт послуг", "нбу", "конверт"],
    "Корпоративне":            ["статут", "частк", "акці", "корпоратив", "засновник", "реорганіз"],
    "Інвестиційне":            ["safe", "інвест", "vesting", "share", "convertible", "раунд"],
    "Трудове / HR":            ["трудов", "звільн", "employment", "non-compete", "кзпп", "esop", "опціон"],
    "IP / IT":                 ["інтелектуальн", "торгов марк", "патент", "it-послуг", "софт", "ліцензійн", "копірайт"],
    "Регуляторне / комплаєнс": ["ліценз", "регулятор", "gdpr", "комплаєнс", "дозвіл", "санкц"],
    "Судова практика":         ["позов", "апеляц", "касац", "судов практик", "оскарж"],
    "Міжнародне":              ["конвенц", "подвійн оподаткув", "brussels", "hague", "міжнародн", "транскордон"],
    "Договірне":               ["договір", "угод", "nda", "клоз", "контракт"],
}
_JUR_TOKENS = {
    "UA": ["україн", "київ", "ukrain", "ua", "+380"],
    "DE": ["німеч", "germany", "deutsch", "münchen", "munich", "berlin", " de "],
    "UK": ["британ", "london", "united kingdom", " uk "],
    "EU": ["європ", "brussels", "eu ", "brussels ia"],
    "US-DE": ["delaware", " us", "сша", "united states"],
}
_SERVICE_KEYWORDS = {
    "Нотаріус":               ["нотар", "notary"],
    "Перекладач":             ["переклад", "translat"],
    "Зовнішній юрист":        ["юрист", "counsel", "law firm", "адвокат", "partner"],
    "Айпішник":               ["патент", "ip ", "trademark", "айпі"],
    "Аудитор":                ["аудит", "audit"],
    "Податковий консультант": ["податков", "tax advis", "tax consult"],
    "Сервіс-провайдер":       ["реєстрац", "апостиль", "легаліз", "подач"],
    "Індустріальний":         ["логіст", "ріелтор", "банкір", "broker"],
}
_CONTACT_RE = re.compile(r"(\+?\d[\d\s()\-]{6,}\d)|([\w.\-]+@[\w.\-]+\.\w+)")
_PLACEHOLDER_RE = re.compile(r"\[[^\]]{1,40}\]|_{3,}|\{\{.*?\}\}|<[A-ZА-ЯІЇЄ_ ]{2,}>")


class Sortuvalnyk:
    def __init__(self):
        self.kb = KB()
        self.llm = _try_llm()

    # -- публічне ----------------------------------------------------------- #
    def classify(self, raw, hint_type=None):
        """Повертає {table, fields, confidence, reasons}. LLM або fallback."""
        c = None
        if self.llm:
            try:
                c = self.llm(raw, hint_type)
            except Exception:
                c = None  # деградуємо до маркерів
        if c is None:
            c = _heuristic(raw, hint_type)
        c["table"] = _canon_table(c.get("table", ""))  # LLM інколи дає однину
        c["fields"] = _sanitize(c.get("fields", {}))   # списки/off-vocab від LLM
        return c

    def intake(self, raw, proposed_by="sortuvalnyk", drive_link="", hint_type=None):
        """Розібрати і покласти чернетку в Inbox. Повертає (temp_id, c)."""
        c = self.classify(raw, hint_type)
        temp_id = self.kb.propose(c["table"], c["fields"],
                                  drive_link=drive_link, proposed_by=proposed_by,
                                  details=c["fields"])
        return temp_id, c

    # -- обробка Drive-папки Inbox ------------------------------------------ #
    def process_inbox(self):
        """Прочитати всі файли з Drive-папки _Inbox, класифікувати → Inbox-вкладка.

        Підтримує PDF / DOCX / Google Docs / текст. Оброблені файли переїжджають
        у підпапку _processed (щоб не обробляти двічі). Повертає список результатів.
        """
        drive = self.kb.drive
        inbox = self.kb.cfg["folders"]["_Inbox"]
        done = self._subfolder(inbox, "_processed")
        q = (f"'{inbox}' in parents and trashed=false "
             "and mimeType!='application/vnd.google-apps.folder'")
        files = drive.files().list(
            q=q, fields="files(id,name,mimeType,webViewLink)",
            supportsAllDrives=True, includeItemsFromAllDrives=True
        ).execute().get("files", [])
        out = []
        for f in files:
            text = self._extract(f)
            if not text or not text.strip():
                out.append((f["name"], None, "(не вдалось прочитати текст)"))
                continue
            try:
                tid, c = self.intake(text[:6000], proposed_by="sortuvalnyk:drive",
                                     drive_link=f.get("webViewLink", ""))
                out.append((f["name"], tid, f"{c['table']} (conf={c['confidence']})"))
                self._move(f["id"], done)
            except Exception as e:
                out.append((f["name"], None, f"ПОМИЛКА: {e}"))
        return out

    def _subfolder(self, parent, name):
        drive = self.kb.drive
        q = (f"'{parent}' in parents and name='{name}' and trashed=false "
             "and mimeType='application/vnd.google-apps.folder'")
        r = drive.files().list(q=q, fields="files(id)", supportsAllDrives=True,
                               includeItemsFromAllDrives=True).execute().get("files", [])
        if r:
            return r[0]["id"]
        return drive.files().create(
            body={"name": name, "mimeType": "application/vnd.google-apps.folder",
                  "parents": [parent]}, fields="id", supportsAllDrives=True
        ).execute()["id"]

    def _move(self, fid, dest):
        drive = self.kb.drive
        meta = drive.files().get(fileId=fid, fields="parents",
                                 supportsAllDrives=True).execute()
        drive.files().update(fileId=fid, addParents=dest,
                             removeParents=",".join(meta.get("parents", [])),
                             supportsAllDrives=True, fields="id").execute()

    def _extract(self, f):
        drive = self.kb.drive
        mt, fid = f["mimeType"], f["id"]
        try:
            if mt == "application/vnd.google-apps.document":
                return drive.files().export(
                    fileId=fid, mimeType="text/plain").execute().decode("utf-8", "ignore")
            data = drive.files().get_media(fileId=fid, supportsAllDrives=True).execute()
            if mt == "application/pdf":
                import io, pypdf
                rd = pypdf.PdfReader(io.BytesIO(data))
                return "\n".join((p.extract_text() or "") for p in rd.pages)
            if mt.endswith("wordprocessingml.document"):
                import io, docx
                d = docx.Document(io.BytesIO(data))
                return "\n".join(p.text for p in d.paragraphs)
            if mt.endswith("presentationml.presentation"):
                import io, pptx
                pr = pptx.Presentation(io.BytesIO(data))
                out = []
                for sl in pr.slides:
                    for sh in sl.shapes:
                        if sh.has_text_frame:
                            out.append(sh.text_frame.text)
                return "\n".join(out)
            if mt.startswith("text/"):
                return data.decode("utf-8", "ignore")
        except Exception:
            return ""
        return ""


# --- нормалізація назви таблиці (LLM інколи дає однину/англійською) ----------
_TABLE_ROOTS = {"прецедент": "Прецеденти", "шаблон": "Шаблони", "templat": "Шаблони",
                "precedent": "Прецеденти", "рісьорч": "Рісьорчі", "ресерч": "Рісьорчі",
                "research": "Рісьорчі", "memo": "Рісьорчі", "провайдер": "Провайдери",
                "provider": "Провайдери", "vendor": "Провайдери"}


def _sanitize(fields):
    """Звести значення від LLM до того, що приймає шит: списки → рядок (для
    одно-значних дропдаунів беремо перше валідне), off-vocab значення відкидаємо."""
    out = {}
    for k, v in (fields or {}).items():
        controlled = k in COLUMN_VALIDATION
        if isinstance(v, list):
            v = (v[0] if v else "") if controlled else ", ".join(str(x) for x in v)
        v = "" if v is None else str(v).strip()
        if controlled and v and v not in TAXONOMY_VALUES.get(COLUMN_VALIDATION[k], []):
            v = ""  # off-vocab → не валимо валідацію, лишаємо порожнім
        out[k] = v
    return out


def _canon_table(t):
    t = (t or "").strip().lower()
    for tbl in ("Прецеденти", "Шаблони", "Рісьорчі", "Провайдери"):
        if t == tbl.lower():
            return tbl
    for root, tbl in _TABLE_ROOTS.items():
        if root in t:
            return tbl
    return "Рісьорчі"  # безпечний дефолт


# --- fallback-розбір ---------------------------------------------------------
def _heuristic(raw, hint_type=None):
    text = raw.strip()
    low = " " + text.lower() + " "
    reasons = []

    # 1) тип
    has_contact = bool(_CONTACT_RE.search(text))
    has_ph = bool(_PLACEHOLDER_RE.search(text))
    is_qa = ("?" in text or "питанн" in low) and any(
        w in low for w in ["висновок", "аналіз", "тому", "отже", "позиці"])
    short = len(text) < 240

    if hint_type in ("Прецеденти", "Шаблони", "Рісьорчі", "Провайдери"):
        table = hint_type; reasons.append(f"тип задано: {hint_type}")
    elif has_contact and short:
        table = "Провайдери"; reasons.append("короткий текст + контакт → провайдер")
    elif has_ph:
        table = "Шаблони"; reasons.append("плейсхолдери → шаблон")
    elif is_qa:
        table = "Рісьорчі"; reasons.append("питання + аналіз/висновок → рісьорч")
    else:
        table = "Рісьорчі"; reasons.append("за замовч.: інсайт-рісьорч")

    # 2) опис/ключові — перше речення + стиснення
    summary = _summarise(text)

    title = _title(text)
    fields = {NAME_COL: title, SUMMARY_COL: summary}

    # 3) юрисдикція
    jur = _detect_one(low, _JUR_TOKENS) or "UA"
    reasons.append(f"юрисдикція: {jur}")

    if table == "Провайдери":
        svc = _detect_one(low, _SERVICE_KEYWORDS) or "Сервіс-провайдер"
        fields.update({"Тип послуги": svc, "Юрисдикція / регіон": jur,
                       "Контакти": _contacts(text), "Партнер": "FALSE"})
        reasons.append(f"тип послуги: {svc}")
    elif table == "Рісьорчі":
        sph = _detect_one(low, _SPHERE_KEYWORDS) or "Договірне"
        fields.update({"Сфера": sph, "Юрисдикція": jur,
                       "Питання / тригер": _question(text)})
        reasons.append(f"сфера: {sph}")
    else:  # Прецеденти / Шаблони — документні категорії 1.1–1.6
        cat = _detect_cat(low) or "1.1 Договірні"
        fields.update({"Категорія": cat, "Юрисдикція": jur})
        reasons.append(f"категорія: {cat}")

    # 4) впевненість: скільки сигналів спрацювало
    has_class = _detect_cat(low) is not None or _detect_one(low, _SPHERE_KEYWORDS) is not None
    strong = sum([has_contact, has_ph, is_qa,
                  has_class, _detect_one(low, _JUR_TOKENS) is not None])
    confidence = round(min(0.95, 0.4 + 0.13 * strong), 2)

    return {"table": table, "fields": fields, "confidence": confidence,
            "reasons": reasons}


def _summarise(text):
    s = re.sub(r"\s+", " ", text).strip()
    first = re.split(r"(?<=[.!?])\s", s)[0]
    out = first if len(first) >= 30 else s
    return (out[:300]).strip()


def _title(text):
    s = re.sub(r"\s+", " ", text).strip()
    return s[:70] + ("…" if len(s) > 70 else "")


def _question(text):
    for part in re.split(r"(?<=[.!?])\s", text):
        if "?" in part:
            return part.strip()[:200]
    return _title(text)


def _contacts(text):
    found = [m.group(0).strip() for m in _CONTACT_RE.finditer(text)]
    return ", ".join(dict.fromkeys(found))[:200]


def _detect_one(low, table):
    """Найкращий збіг = найбільше влучань ключових слів (не перший-ліпший)."""
    best, best_n = None, 0
    for key, toks in table.items():
        n = sum(1 for t in toks if t in low)
        if n > best_n:
            best, best_n = key, n
    return best


def _detect_cat(low):
    return _detect_one(low, _CAT_KEYWORDS)


# --- LLM-режим (опційно) -----------------------------------------------------
def _try_llm():
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None
    try:
        import anthropic
    except ImportError:
        return None
    client = anthropic.Anthropic(api_key=key)

    model = os.environ.get("KB_LLM_MODEL", "claude-haiku-4-5-20251001")

    def run(raw, hint_type=None):
        import json
        sys_prompt = (
            "Ти — сортувальник юридичної бази знань X-ON-X. Розбери кинутий артефакт "
            "і поверни СТРОГО один JSON-обʼєкт без пояснень:\n"
            '{"table": <Прецеденти|Шаблони|Рісьорчі|Провайдери>, "fields": {...}, "confidence": 0..1}\n\n'
            "Тип: Прецедент = реальний заповнений документ з кейсу; Шаблон = документ "
            "з плейсхолдерами; Рісьорч = питання+аналіз+висновок; Провайдер = контакт "
            "зовнішнього постачальника послуг.\n\n"
            "fields (українські ключі рівно так):\n"
            "- Назва — коротка людська назва, 3–8 слів (НЕ перше речення).\n"
            "- 'Опис + ключові слова' — 1–2 речення суті + ключові слова (обовʼязкове).\n"
            f"- Юрисдикція ∈ {JURS}.\n"
            f"- Прецедент/Шаблон: Категорія ∈ {CATS}.\n"
            f"- Рісьорч: 'Питання / тригер' (що досліджували) + Сфера ∈ {SPHERES}.\n"
            f"- Провайдер: 'Тип послуги' ∈ {SERVICE_TYPES}, 'Юрисдикція / регіон' ∈ {JURS}, "
            "Контакти, Послуги (перелік через кому), Партнер (TRUE/FALSE)."
        )
        msg = client.messages.create(
            model=model, max_tokens=900, system=sys_prompt,
            messages=[{"role": "user", "content": raw[:8000]}])
        txt = msg.content[0].text
        data = json.loads(txt[txt.index("{"):txt.rindex("}") + 1])
        data.setdefault("confidence", 0.85)
        data["reasons"] = [f"LLM ({model})"]
        return data

    return run


# --- демо --------------------------------------------------------------------
if __name__ == "__main__":
    s = Sortuvalnyk()
    samples = [
        "Олена Коваль, перекладач (укр/нім), Львів. olena.koval@translate.ua, +380 67 123 45 67. "
        "Робила нотаріальні переклади для угод DE.",
        "Чи можна в трудовому договорі в Україні встановити non-compete після звільнення? "
        "Аналіз: пряма заборона у ст.43 КЗпП; висновок — non-compete як такий не enforceable, "
        "лише через NDA + компенсацію.",
        "ШАБЛОН: Договір про надання послуг між [ВИКОНАВЕЦЬ] та [ЗАМОВНИК], "
        "юрисдикція України, з полями [предмет], [ціна], [строк].",
    ]
    for raw in samples:
        tid, c = s.intake(raw)
        print(f"\n{tid}  →  {c['table']}  (conf={c['confidence']})")
        print("  reasons:", "; ".join(c["reasons"]))
        print("  fields :", {k: (v[:50] + '…' if isinstance(v, str) and len(v) > 50 else v)
                             for k, v in c["fields"].items()})
