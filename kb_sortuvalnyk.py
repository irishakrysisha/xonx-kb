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
LAWS = TAXONOMY_VALUES["Право"]          # governing law (документи/рісьорчі)
JURS = TAXONOMY_VALUES["Юрисдикція"]     # регіон провайдера
SERVICE_TYPES = TAXONOMY_VALUES["Тип послуги"]
SPHERES = TAXONOMY_VALUES["Сфера"]
DOCTYPES = TAXONOMY_VALUES["Тип документа"]
FORMS = TAXONOMY_VALUES["Форма"]

# --- маркери для fallback-класифікації --------------------------------------
_CAT_KEYWORDS = {
    "Договірні":          ["nda", "договір", "угод", "contract", "mou", "term sheet", "ліценз"],
    "Корпоративні":       ["статут", "засновник", "корпоратив", "довірен", "реорганіз", "протокол збор"],
    "Інвестиційні":       ["safe", "інвест", "sha", "spa", "share", "vesting", "cap table", "convertible", "subscription"],
    "Трудові / HR":       ["трудов", "employment", "цпд", "esop", "опціон", "наказ",
                           "працівник", "звільн", "кзпп", "non-compete", "non compete"],
    "Внутрішні політики": ["privacy", "policy", "cookie", "gdpr", "dpa", "політик"],
    "Регулятори / Суди":  ["позов", "претензі", "demand", "суд", "податков", "регулятор", "апеляц", "звернення"],
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
# РЕГІОН провайдера (де працює) — з містами
_JUR_TOKENS = {
    "UA-Київ": ["київ", "kyiv", "kiev"],
    "UA-Львів": ["львів", "lviv"],
    "UA": ["україн", "ukrain", "+380"],
    "DE": ["німеч", "germany", "deutsch", "münchen", "munich", "berlin", " de "],
    "UK": ["британ", "london", "united kingdom", " uk "],
    "EU": ["європ", "brussels", "eu ", "brussels ia"],
    "US-DE": ["delaware"],
    "US": [" us", "сша", "united states"],
    "PL": ["польщ", "poland", "warsaw", "варшав"],
    "UAE": ["оае", "uae", "dubai", "дубай", "emirates"],
    "CY": ["кіпр", "cyprus"],
    "EE": ["естон", "estonia", "tallinn"],
}
# ПРАВО, що регулює (governing law) — правові системи, міста зводимо до країни.
# Фрази «governed by … law» / «право …» дають найсильніший сигнал.
_LAW_TOKENS = {
    "UA": ["право україн", "законодавств україн", "за правом україн", "україн",
           "київ", "львів", "кзпп", "цку", "пку", "+380"],
    "DE": ["german law", "право німеч", "за правом німеч", "німеч", "deutsch", "bgb"],
    "UK": ["english law", "law of england", "laws of england", "england and wales",
           "за правом англі", "право англі", "british", "британ", "england"],
    "US-DE": ["delaware law", "law of delaware", "dgcl", "delaware"],
    "US": ["new york law", "laws of new york", "право сша", "united states", "сша"],
    "EU": ["eu law", "право єс", "європейськ законодавств", "gdpr"],
    "PL": ["polish law", "право польщ", "за правом польщ", "польщ", "poland"],
    "UAE": ["uae law", "право оае", "difc", "оае", "dubai law"],
    "CY": ["cyprus law", "право кіпр", "кіпр", "cyprus"],
    "EE": ["estonian law", "право естон", "естон", "estonia"],
}
_SERVICE_KEYWORDS = {
    "Нотаріус":                       ["нотар", "notary"],
    "Перекладач":                     ["переклад", "translat"],
    "Зовнішній юрист":                ["юрист", "counsel", "law firm", "адвокат", "attorney"],
    "Айпішник / патентний повірений": ["патент", "trademark", "айпі", "торгов марк", "патентн повірен"],
    "Аудитор":                        ["аудит", "audit"],
    "Податковий консультант":         ["податков консульт", "tax advis", "tax consult"],
    "Сервіс-провайдер":               ["реєстрац", "апостиль", "легаліз", "подач"],
    "Логіст":                         ["логіст", "logistic", "перевез", "freight", "митн брокер"],
    "Ріелтор":                        ["ріелтор", "realtor", "нерухом", "real estate"],
    "Інвестбанкір":                   ["інвестбанк", "investment bank", "m&a advis", "банкір"],
    "Індустріальний (інше)":          ["індустріальн", "галузев"],
}
# тип документа для прецедентів/шаблонів (підтип усередині категорії)
_DOCTYPE_KEYWORDS = {
    "NDA":                        ["nda", "про нерозголош", "non-disclosure", "конфіденційн"],
    "Договір (сервісний)":        ["договір про надання послуг", "сервісн договір", "service agreement"],
    "Договір (фандінг)":          ["фандінг", "funding agreement", "грант договір"],
    "Договір (комерційний)":      ["договір постач", "договір купівл", "supply agreement", "комерційн договір"],
    "MOU / LoI":                  [" mou ", " loi ", "letter of intent", "memorandum of understanding", "меморандум про намір"],
    "Term sheet":                 ["term sheet", "термшит"],
    "Ліцензійний договір":        ["ліцензійн", "license agreement", "ліценз договір"],
    "Amendment / дод. угода":     ["amendment", "додаткова угода", "дод. угода", "допугод"],
    "RFP / пропозиція":           ["rfp", "комерційна пропозиц", "request for proposal", "тендерн"],
    "Статут / установчі":         ["статут", "установч документ", "articles of association", "charter"],
    "Рішення засновника / протокол": ["рішення засновник", "протокол збор", "shareholder resolution", "board minutes"],
    "Корп. зміни / реорганізація": ["реорганіз", "злиття", "поділ", "merger", "корпоративн зміни"],
    "Довіреність":                ["довірен", "power of attorney", " poa "],
    "SAFE / convertible":         [" safe ", "convertible note", "конвертован"],
    "SHA":                        [" sha ", "shareholders agreement", "акціонерн угод", "корпоративн договір"],
    "SPA":                        [" spa ", "share purchase", "купівлі-продажу частк", "купівлі-продажу акці"],
    "Subscription agreement":     ["subscription agreement", "договір підписк"],
    "Side letter":                ["side letter", "сайд-лист"],
    "Disclosure letter":          ["disclosure letter", "disclosure schedule", "лист про розкриття"],
    "Vesting agreement":          ["vesting", "вестинг"],
    "Cap table":                  ["cap table", "капіталізаційн табл"],
    "Put & Call option":          ["put option", "call option", "put&call", "опціон put", "опціон call"],
    "Трудовий договір":           ["трудовий договір", "employment agreement", "контракт з працівник"],
    "ЦПД":                        ["цпд", "цивільно-правов", "договір з фоп", "gig contract"],
    "Наказ":                      ["наказ"],
    "ESOP / опціони":             ["esop", "опціонн план", "option plan", "опціонн програм"],
    "Privacy policy":             ["privacy policy", "політика конфіденційн"],
    "Cookie policy":              ["cookie policy", "політика cookie", "політика куки"],
    "IP policy":                  ["ip policy", "політика інтелектуальн"],
    "DPA / GDPR":                 ["dpa", "gdpr", "data processing", "обробк персональн дан"],
    "Претензія / demand":         ["претензі", "demand letter", "вимога про"],
    "Запит / відповідь":          ["запит", "відповідь на запит", "request and response"],
    "Звернення в держорган":      ["звернення", "заява до держ", "лист до держоргану"],
    "Позов / апеляція":           ["позов", "апеляц", "касац", "claim form", "позовн заяв"],
    "Заперечення на акт":         ["заперечення на акт", "оскарж акт", "відповідь на акт податков"],
}
# форма рісьорчу
_FORM_KEYWORDS = {
    "Меморандум":     ["меморандум", "memorandum", "аналітичн записк", "memo"],
    "Огляд практики": ["огляд судов практик", "судов практик", "огляд практики", "case law review"],
    "Огляд змін":     ["огляд змін", "зміни законодавств", "законодавч новел", "legislative update"],
    "Lifehack":       ["лайфхак", "lifehack", "фішк", "практичн рад"],
    "Q&A":            ["q&a", "питання-відповідь", "коротке питанн"],
}
# ознаки «це реальний юридичний документ» (коли підтип не розпізнано)
_DOC_SIGNALS = re.compile(
    r"договір|угод[аи]|деед|deed|agreement|contract|статут|довірен|"
    r"претензі|позов|наказ|policy|політик|протокол", re.IGNORECASE)
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
        note = _review_note(c)
        temp_id = self.kb.propose(c["table"], c["fields"],
                                  drive_link=drive_link, proposed_by=proposed_by,
                                  details=c["fields"], note=note)
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
    dtype_guess = _detect_one(low, _DOCTYPE_KEYWORDS)

    if hint_type in ("Прецеденти", "Шаблони", "Рісьорчі", "Провайдери"):
        table = hint_type; reasons.append(f"тип задано: {hint_type}")
    elif has_contact and short:
        table = "Провайдери"; reasons.append("короткий текст + контакт → провайдер")
    elif has_ph:
        table = "Шаблони"; reasons.append("плейсхолдери → шаблон")
    elif is_qa:
        table = "Рісьорчі"; reasons.append("питання + аналіз/висновок → рісьорч")
    elif dtype_guess:
        # реальний заповнений документ відомого типу (без плейсхолдерів) → прецедент
        table = "Прецеденти"; reasons.append(f"тип документа «{dtype_guess}» без плейсхолдерів → прецедент")
    elif _DOC_SIGNALS.search(low):
        # схоже на реальний юридичний документ, хоч підтип і не розпізнано
        table = "Прецеденти"; reasons.append("ознаки юридичного документа → прецедент (тип уточнити)")
    else:
        table = "Рісьорчі"; reasons.append("за замовч.: інсайт-рісьорч")

    # 2) опис/ключові — перше речення + стиснення
    summary = _summarise(text)

    title = _title(text)
    fields = {NAME_COL: title, SUMMARY_COL: summary}

    # 3) право (governing law) — для документів/рісьорчів; регіон — для провайдерів
    law = _detect_one(low, _LAW_TOKENS) or "UA"
    region = _detect_one(low, _JUR_TOKENS) or "UA"

    if table == "Провайдери":
        svc = _detect_one(low, _SERVICE_KEYWORDS) or "Сервіс-провайдер"
        fields.update({"Тип послуги": svc, "Юрисдикція / регіон": region,
                       "Контакти": _contacts(text), "Партнер": "FALSE"})
        reasons.append(f"тип послуги: {svc}; регіон: {region}")
    elif table == "Рісьорчі":
        sph = _detect_one(low, _SPHERE_KEYWORDS) or "Договірне"
        form = _detect_one(low, _FORM_KEYWORDS) or ("Q&A" if is_qa else "Меморандум")
        fields.update({"Сфера": sph, "Форма": form, "Право": law,
                       "Питання / тригер": _question(text)})
        reasons.append(f"сфера: {sph}; форма: {form}; право: {law}")
    else:  # Прецеденти / Шаблони — документні категорії за типом відносин
        cat = _detect_cat(low) or "Договірні"
        dtype = dtype_guess or ""
        fields.update({"Категорія": cat, "Тип документа": dtype, "Право": law})
        reasons.append(f"право: {law}")
        reasons.append(f"категорія: {cat}" + (f"; тип документа: {dtype}" if dtype else ""))

    # 4) впевненість: скільки сигналів спрацювало
    has_class = _detect_cat(low) is not None or _detect_one(low, _SPHERE_KEYWORDS) is not None
    strong = sum([has_contact, has_ph, is_qa,
                  has_class, _detect_one(low, _JUR_TOKENS) is not None])
    confidence = round(min(0.95, 0.4 + 0.13 * strong), 2)

    return {"table": table, "fields": fields, "confidence": confidence,
            "reasons": reasons}


def _review_note(c):
    """Коротка нотатка для рев'ювера: впевненість + на що глянути."""
    conf = c.get("confidence", 0)
    bits = [f"впевненість {conf:.2f}"]
    bits += [r for r in c.get("reasons", []) if r]
    if conf < 0.6:
        bits.insert(0, "⚠ ПЕРЕВІРИТИ")
    return " · ".join(bits)[:300]


def _clean(text):
    """Прибрати шум: плейсхолдери, підкреслення, маркери сторінок/слайдів,
    схлопнути підряд продубльовані слова (типовий артефакт PDF-екстракції)."""
    s = re.sub(r"\s+", " ", text or "").strip()
    s = _PLACEHOLDER_RE.sub(" ", s)            # [Клієнт A], <ВИКОНАВЕЦЬ>, {{x}}
    s = re.sub(r"_{2,}", " ", s)               # ____ підкреслення-заглушки
    s = re.sub(r"\(\s*\d+\s*/\s*\d+\s*\)", " ", s)   # (1/3), (1 / 2) — слайди
    s = re.sub(r"\b(\w{3,})(\s+\1\b)+", r"\1", s, flags=re.IGNORECASE)  # дубль слів
    return re.sub(r"\s+", " ", s).strip(" .;:-—")


def _is_shouty(x):
    letters = [c for c in x if c.isalpha()]
    return bool(letters) and sum(c.isupper() for c in letters) / len(letters) > 0.7


def _summarise(text):
    s = _clean(text)
    sents = re.split(r"(?<=[.!?])\s", s)
    # перше змістовне речення, що не є ALL-CAPS «шапкою» документа
    pick = next((x for x in sents if len(x) >= 30 and not _is_shouty(x)), s)
    return pick[:300].strip()


def _title(text):
    s = _clean(text)
    # не беремо ALL-CAPS бланк як назву — шукаємо перше «нормальне» речення
    for part in re.split(r"(?<=[.!?])\s", s):
        if len(part) >= 12 and not _is_shouty(part):
            s = part
            break
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

    # Sonnet за замовч. — для юридичної класифікації точніший за Haiku
    # (краще розрізняє прецедент/шаблон, витягає governing law, пише назви).
    model = os.environ.get("KB_LLM_MODEL", "claude-sonnet-4-6")

    def run(raw, hint_type=None):
        import json
        sys_prompt = (
            "Ти — Сортувальник юридичної бази знань X-ON-X. Тобі кидають сирий артефакт "
            "(уривок документа / нотатку / контакт). Класифікуй його й поверни СТРОГО "
            "один JSON-обʼєкт без жодного тексту до/після:\n"
            '{"table":"Прецеденти|Шаблони|Рісьорчі|Провайдери","fields":{...},'
            '"confidence":0..1,"uncertain":["<поля, де не впевнений>"]}\n\n'

            "КРОК 1 — ТИП (table), за вирішальними ознаками:\n"
            "• Провайдери — є контакт/ім'я зовнішнього постачальника послуг (телефон, "
            "email, сайт, «нотаріус», «перекладач», «аудитор»). Не документ.\n"
            "• Шаблони — документ із ПЛЕЙСХОЛДЕРАМИ ([_], <ВИКОНАВЕЦЬ>, {{дата}}, "
            "пропуски) — болванка для повторного використання.\n"
            "• Прецеденти — РЕАЛЬНИЙ заповнений документ із кейсу (конкретні сторони, "
            "суми, дати), без плейсхолдерів.\n"
            "• Рісьорчі — інтелектуальний продукт: питання + аналіз + висновок "
            "(меморандум, Q&A, огляд практики). НЕ сам документ.\n"
            "Якщо вагаєшся прецедент vs шаблон — дивись на плейсхолдери; "
            "документ vs рісьорч — чи є позиція/висновок (рісьорч) vs текст угоди (документ).\n\n"

            "КРОК 2 — ПОЛЯ (українські ключі точно так):\n"
            "• Назва — стисла людська назва 3–8 слів, по суті (НЕ перше речення, НЕ "
            "ALL-CAPS шапка). Напр.: «NDA з контрагентом — взаємний» , «SAFE з cap на "
            "оцінку».\n"
            "• Опис — 1–2 речення суті БЕЗ ключових слів. Для рісьорчу включи "
            "КОРОТКИЙ ВИСНОВОК, а не лише питання.\n"
            "• Ключові слова — окреме поле: 5–12 тегів через кому, ДВОМОВНІ "
            "(укр+англ терміни) для пошуку. НЕ речення.\n"
            f"• Прецедент/Шаблон: Категорія (тип відносин) ∈ {CATS}; 'Тип документа' "
            f"(підтип) ∈ {DOCTYPES}; Право (governing law) ∈ {LAWS}.\n"
            f"• Рісьорч: 'Питання / тригер' (що саме досліджували) + Сфера ∈ {SPHERES} "
            f"+ Форма ∈ {FORMS} + Право (яке право аналізується) ∈ {LAWS}.\n"
            f"• Провайдер: 'Тип послуги' ∈ {SERVICE_TYPES}; 'Юрисдикція / регіон' "
            f"(де працює, можна місто) ∈ {JURS}; Контакти; Послуги (через кому); "
            "Партнер (TRUE/FALSE — TRUE лише якщо згадано реф.договір/прайс).\n\n"

            "ПРАВО (governing law) — це НЕ де сторони, а яке право РЕГУЛЮЄ. Шукай "
            "«governed by … law», «applicable law», «за правом …», «регулюється правом …». "
            "Якщо прямо не вказано — обери за мовою/реквізитами, але познач у 'uncertain'.\n\n"

            "ВПЕВНЕНІСТЬ: якщо для контрольованого поля немає чіткого сигналу — НЕ "
            "вгадуй: лиши поле порожнім (\"\") і додай його назву в 'uncertain'. Краще "
            "порожньо, ніж хибно. confidence — загальна (0..1).\n"
            "Усі значення контрольованих полів — РІВНО з наведених списків (інакше "
            "порожньо)."
        )
        if hint_type:
            sys_prompt += f"\n\nПідказка: ймовірний тип — {hint_type}."
        msg = client.messages.create(
            model=model, max_tokens=1000, system=sys_prompt,
            messages=[{"role": "user", "content": raw[:8000]}])
        txt = msg.content[0].text
        data = json.loads(txt[txt.index("{"):txt.rindex("}") + 1])
        data.setdefault("confidence", 0.85)
        unc = data.get("uncertain") or []
        if isinstance(unc, str):
            unc = [unc]
        data["reasons"] = [f"LLM ({model})"]
        if unc:
            data["reasons"].append("не впевнений у полях: " + ", ".join(map(str, unc)))
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
