"""kb_api — the one contract people and AI agents use to read and fill the KB.

    from kb_api import KB
    kb = KB()
    kb.search("warranty cap")              # find published records
    kb.get("PRE-0001")                     # one record + its linked records
    tmp = kb.propose("Templates", {...})   # add a draft to the Inbox
    kb.promote(tmp, reviewer="Iryna")      # approve it into the Templates table
    kb.link("PRE-0001", "PRV-0002")        # bidirectional link
    kb.update("RES-0001", {"Status": "archived"})

Design rules enforced here (not in the sheet):
  * every published/proposed record MUST have a non-empty Summary,
  * Practice / typed dropdown fields are validated against _Taxonomy,
  * IDs are generated centrally (PRE-/TPL-/RES-/PRV-),
  * links are always written on BOTH sides.
"""
import json
import os
from datetime import datetime

from kb_client import get_clients
from kb_schema import (INBOX, INBOX_COLUMNS, PREFIX_TO_TABLE, TABLES, TAXONOMY,
                       TAXONOMY_VALUES, ID_WIDTH, COLUMN_VALIDATION,
                       NAME_COL, SUMMARY_COL, STATUS_COL, RELATED_COL,
                       CREATED_BY, CREATED_AT, UPDATED_AT)

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "kb_config.json")
FOLDER_MIME = "application/vnd.google-apps.folder"
SECTION_OF = {"Прецеденти": "Precedents", "Шаблони": "Templates",
              "Рісьорчі": "Researches", "Провайдери": "Providers"}


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _file_id_from_link(link):
    """Extract a Drive file/folder id from a share link, or return as-is."""
    if not link:
        return None
    for marker in ("/folders/", "/d/", "id="):
        if marker in link:
            tail = link.split(marker, 1)[1]
            return tail.split("/")[0].split("?")[0].split("&")[0]
    return link


class KBError(Exception):
    pass


class KB:
    def __init__(self, config_path=CONFIG_PATH):
        with open(config_path) as f:
            self.cfg = json.load(f)
        self.gc, self.drive = get_clients()
        self.ss = self.gc.open_by_key(self.cfg["spreadsheet_id"])
        self._ws = {}

    # -- low level ---------------------------------------------------------- #
    def ws(self, name):
        if name not in self._ws:
            self._ws[name] = self.ss.worksheet(name)
        return self._ws[name]

    def _rows(self, table):
        """Return (header, list-of-dict-records, raw_values)."""
        vals = self.ws(table).get_all_values()
        header = vals[0]
        records = [dict(zip(header, r)) for r in vals[1:] if any(r)]
        return header, records, vals

    def _table_of(self, rec_id):
        prefix = rec_id.split("-")[0]
        table = PREFIX_TO_TABLE.get(prefix)
        if not table:
            raise KBError(f"unknown ID prefix in {rec_id!r}")
        return table

    def _locate(self, rec_id):
        """Return (table, row_index_1based, header, record_dict)."""
        table = self._table_of(rec_id)
        header, _, vals = self._rows(table)
        idcol = header.index("ID")
        for i, r in enumerate(vals[1:], start=2):
            if len(r) > idcol and r[idcol] == rec_id:
                return table, i, header, dict(zip(header, r))
        raise KBError(f"{rec_id} not found in {table}")

    def _next_id(self, table):
        prefix = TABLES[table]["prefix"]
        _, recs, _ = self._rows(table)
        nums = [int(r["ID"].split("-")[1]) for r in recs if r.get("ID", "").startswith(prefix + "-")]
        n = (max(nums) + 1) if nums else 1
        return f"{prefix}-{n:0{ID_WIDTH}d}"

    def _validate(self, table, fields):
        if not fields.get(SUMMARY_COL, "").strip():
            raise KBError(f"{SUMMARY_COL!r} is required (it is what humans and agents search on)")
        for col, val in fields.items():
            key = COLUMN_VALIDATION.get(col)
            if key and val and val not in TAXONOMY_VALUES[key]:
                raise KBError(f"{col}={val!r} not in _Taxonomy {key}: {TAXONOMY_VALUES[key]}")

    # -- read --------------------------------------------------------------- #
    def search(self, query="", table=None, status="active", limit=10):
        """Знайти картки, відранжовані за релевантністю (kb_search).

        Вектор (embeddings), якщо колонка Embedding заповнена і є провайдер;
        інакше lexical TF-IDF. За замовч. лише status='active' (чисте ядро).
        """
        import kb_search
        tables = [table] if table else list(TABLES.keys())
        cand = []
        for t in tables:
            _, recs, _ = self._rows(t)
            for r in recs:
                if status and r.get(STATUS_COL) != status:
                    continue
                cand.append({"table": t, **r})
        if not query:
            return cand[:limit]
        return kb_search.rank(query, cand, limit=limit)

    def embed_all(self, status="active"):
        """Порахувати і записати вектори в колонку Embedding (потрібен провайдер).

        Без VOYAGE_API_KEY / OPENAI_API_KEY — нічого не робить (повертає 0).
        """
        import kb_search
        if kb_search.embed_text("ping") is None:
            return 0
        n = 0
        for t in TABLES:
            header, recs, vals = self._rows(t)
            col = header.index(EMBEDDING_COL) + 1
            for i, r in enumerate(vals[1:], start=2):
                rec = dict(zip(header, r))
                if status and rec.get(STATUS_COL) != status:
                    continue
                vec = kb_search.embed_text(kb_search.record_text(rec))
                if vec:
                    self.ws(t).update_cell(i, col, json.dumps(vec))
                    n += 1
        return n

    def get(self, rec_id, resolve=True):
        _, _, _, rec = self._locate(rec_id)
        out = dict(rec)
        if resolve:
            related = []
            for rid in [x.strip() for x in rec.get(RELATED_COL, "").split(",") if x.strip()]:
                try:
                    _, _, _, rr = self._locate(rid)
                    related.append({"ID": rid, "Title": rr.get(NAME_COL, ""),
                                    "table": self._table_of(rid)})
                except KBError:
                    related.append({"ID": rid, "Title": "(missing)", "table": "?"})
            out["_related"] = related
        return out

    # -- write: intake ------------------------------------------------------ #
    def propose(self, table, fields, drive_link="", proposed_by="agent", details=None):
        """Add a draft to the Inbox. Returns the Temp_ID."""
        if table not in TABLES:
            raise KBError(f"unknown table {table!r}")
        self._validate(table, fields)
        inbox = self.ws(INBOX)
        existing = [r for r in inbox.get_all_values()[1:] if any(r)]
        temp_id = f"INB-{len(existing) + 1:04d}"
        row = {
            "Temp_ID": temp_id, "Цільова полиця": table,
            NAME_COL: fields.get(NAME_COL, ""), "Категорія": fields.get("Категорія", ""),
            SUMMARY_COL: fields.get(SUMMARY_COL, ""),
            "Файл": drive_link or fields.get("Файл", ""),
            "Деталі_JSON": json.dumps(details or fields, ensure_ascii=False),
            RELATED_COL: fields.get(RELATED_COL, ""),
            "Ким запропоновано": proposed_by, "Коли": _now(),
            "Статус ревʼю": "pending", "Рецензент": "", "Нотатки": "", "Result_ID": "",
        }
        inbox.append_row([row.get(c, "") for c in INBOX_COLUMNS],
                         value_input_option="RAW")
        return temp_id

    def _inbox_locate(self, temp_id):
        vals = self.ws(INBOX).get_all_values()
        idcol = INBOX_COLUMNS.index("Temp_ID")
        for i, r in enumerate(vals[1:], start=2):
            if len(r) > idcol and r[idcol] == temp_id:
                return i, dict(zip(INBOX_COLUMNS, r + [""] * (len(INBOX_COLUMNS) - len(r))))
        raise KBError(f"{temp_id} not in Inbox")

    def promote(self, temp_id, reviewer, status="active", pii_ok=False):
        """Approve an Inbox draft into its target table with a real ID.

        Двошвидкісний PII-флоу: Прецеденти (реальні документи) лягають як
        'pending-PII' — поки людина не підтвердить анонімізацію (pii_ok=True
        або згодом clear_pii()). Решта типів — одразу 'active'.
        """
        row_i, draft = self._inbox_locate(temp_id)
        if draft["Статус ревʼю"] == "approved":
            raise KBError(f"{temp_id} already promoted as {draft['Result_ID']}")
        table = draft["Цільова полиця"]
        if table == "Прецеденти" and status == "active" and not pii_ok:
            status = "pending-PII"
        fields = json.loads(draft["Деталі_JSON"]) if draft["Деталі_JSON"] else {}
        # merge top-level Inbox columns over the JSON payload
        for c in (NAME_COL, "Категорія", SUMMARY_COL, RELATED_COL):
            if draft.get(c):
                fields[c] = draft[c]
        if draft.get("Файл"):
            fields["Файл"] = draft["Файл"]
        self._validate(table, fields)

        new_id = self._next_id(table)
        fields.update({"ID": new_id, STATUS_COL: status,
                       CREATED_BY: draft.get("Ким запропоновано", "agent"),
                       CREATED_AT: _now(), UPDATED_AT: _now()})
        cols = TABLES[table]["columns"]
        # explicit placement (gspread append_row mis-detects the table when empty
        # rows carry checkbox/validation artifacts) — write at col A, first row
        # after the last ID-bearing row.
        ws = self.ws(table)
        header, _, vals = self._rows(table)
        idcol = header.index("ID")
        last = 1
        for i, r in enumerate(vals[1:], start=2):
            if len(r) > idcol and r[idcol].strip():
                last = i
        ws.update(f"A{last + 1}", [[fields.get(c, "") for c in cols]],
                  value_input_option="RAW")

        # файл лишається там, де його поклав sortuvalnyk (_processed); каталог
        # просто посилається на нього через поле «Файл». Окремих секційних
        # папок нема — тип картки задає сам каталог.

        # write back any pre-existing links bidirectionally
        for rid in [x.strip() for x in fields.get(RELATED_COL, "").split(",") if x.strip()]:
            try:
                self._add_link_side(rid, new_id)
            except KBError:
                pass

        # close the Inbox row
        self._inbox_set(row_i, {"Статус ревʼю": "approved", "Рецензент": reviewer,
                                "Result_ID": new_id})
        return new_id

    def reject(self, temp_id, reviewer, notes=""):
        row_i, _ = self._inbox_locate(temp_id)
        self._inbox_set(row_i, {"Статус ревʼю": "rejected", "Рецензент": reviewer,
                                "Нотатки": notes})

    def clear_pii(self, rec_id):
        """Підтвердити, що PII прибрано: pending-PII → active."""
        _, _, _, rec = self._locate(rec_id)
        if rec.get(STATUS_COL) != "pending-PII":
            raise KBError(f"{rec_id} is not pending-PII (status={rec.get(STATUS_COL)!r})")
        return self.update(rec_id, {STATUS_COL: "active"})

    def _inbox_set(self, row_i, updates):
        ws = self.ws(INBOX)
        for col, val in updates.items():
            ws.update_cell(row_i, INBOX_COLUMNS.index(col) + 1, val)

    # -- write: edit + link ------------------------------------------------- #
    def update(self, rec_id, fields):
        table, row_i, header, rec = self._locate(rec_id)
        self._validate(table, {**rec, **fields})
        ws = self.ws(table)
        for col, val in fields.items():
            if col not in header:
                raise KBError(f"{table} has no column {col!r}")
            ws.update_cell(row_i, header.index(col) + 1, val)
        ws.update_cell(row_i, header.index(UPDATED_AT) + 1, _now())
        return self.get(rec_id, resolve=False)

    def _add_link_side(self, rec_id, other_id):
        table, row_i, header, rec = self._locate(rec_id)
        current = [x.strip() for x in rec.get(RELATED_COL, "").split(",") if x.strip()]
        if other_id in current:
            return False
        current.append(other_id)
        col = header.index(RELATED_COL) + 1
        self.ws(table).update_cell(row_i, col, ", ".join(current))
        self.ws(table).update_cell(row_i, header.index(UPDATED_AT) + 1, _now())
        return True

    def link(self, id_a, id_b):
        """Create a bidirectional link between two records."""
        a = self._add_link_side(id_a, id_b)
        b = self._add_link_side(id_b, id_a)
        return {"added": [x for x, ok in ((id_a, a), (id_b, b)) if ok]}
