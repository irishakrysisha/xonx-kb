"""In-place міграція живого шита під розширену таксономію (2026-06-16).

Що робить (безпечно, не перестворює spreadsheet):
  1. Додає нові колонки до існуючих вкладок за TABLES (Тип документа →
     Прецеденти/Шаблони; Форма → Рісьорчі), зберігаючи наявні дані за назвою колонки.
  2. Повністю перезаписує вкладку _Taxonomy з оновленого TAXONOMY_VALUES.
  3. Знімає стару валідацію і накладає свіжі дропдауни (нові колонки +
     розширені списки значень).
Після — запусти `python3 kb_polish.py` для стилю/ширин/ховання.

    python3 migrate_taxonomy.py
"""
from kb_api import KB
from kb_schema import (TABLES, TAXONOMY, TAXONOMY_VALUES, INBOX, INBOX_COLUMNS,
                       COLUMN_VALIDATION, SOFT_DROPDOWNS)


def _clear_validation(sid, ncols):
    # зняти будь-яку валідацію з усієї робочої зони (колонки могли зсунутись)
    return [{"setDataValidation": {
        "range": {"sheetId": sid, "startRowIndex": 1, "endRowIndex": 1000,
                  "startColumnIndex": 0, "endColumnIndex": ncols + 2}}}]


def _validation(sid, cols):
    reqs = []
    for idx, c in enumerate(cols):
        key = COLUMN_VALIDATION.get(c) or SOFT_DROPDOWNS.get(c)
        if not key:
            continue
        vals = TAXONOMY_VALUES[key]
        reqs.append({"setDataValidation": {
            "range": {"sheetId": sid, "startRowIndex": 1, "endRowIndex": 1000,
                      "startColumnIndex": idx, "endColumnIndex": idx + 1},
            "rule": {"condition": {"type": "ONE_OF_LIST",
                                   "values": [{"userEnteredValue": v} for v in vals]},
                     "showCustomUi": True, "strict": False}}})
    return reqs


def main():
    kb = KB()
    reqs = []

    for name, spec in TABLES.items():
        ws = kb.ss.worksheet(name)
        new_cols = spec["columns"]
        # ВАЖЛИВО: читаємо ФОРМУЛИ (не відображення), щоб не розплющити HYPERLINK
        # (Файл / Папка на Drive) у текст «Файл ↗» і не втратити URL.
        vals = ws.get("A1:CZ1000", value_render_option="FORMULA")
        old_header = vals[0] if vals else []
        # перекласти кожен наявний рядок у нову розкладку колонок за назвою;
        # ALIAS = перейменовані колонки (нова назва → стара, звідки тягнути дані)
        ALIAS = {"Право": "Юрисдикція"}
        records = []
        for row in vals[1:]:
            if not any(str(c).strip() for c in row):
                continue
            rec = {old_header[i]: (row[i] if i < len(row) else "")
                   for i in range(len(old_header))}
            records.append([rec.get(c) or rec.get(ALIAS.get(c, ""), "")
                            for c in new_cols])

        ncols_old = max(len(old_header), len(new_cols))
        ws.batch_clear([f"A1:{_col(ncols_old + 2)}1000"])
        # USER_ENTERED — щоб формули (=HYPERLINK) лишались формулами, а не текстом
        ws.update("A1", [new_cols] + records, value_input_option="USER_ENTERED")

        sid = ws.id
        reqs += _clear_validation(sid, ncols_old)
        reqs += _validation(sid, new_cols)
        print(f"{name}: {len(new_cols)} колонок, {len(records)} рядків даних")

    # Inbox — лише оновити валідацію (структура без змін)
    inbox = kb.ss.worksheet(INBOX)
    reqs += _clear_validation(inbox.id, len(INBOX_COLUMNS))
    reqs += _validation(inbox.id, INBOX_COLUMNS)

    # _Taxonomy — повний перезапис
    tax = kb.ss.worksheet(TAXONOMY)
    tax_cols = list(TAXONOMY_VALUES.keys())
    maxlen = max(len(v) for v in TAXONOMY_VALUES.values())
    tax_rows = [tax_cols]
    for i in range(maxlen):
        tax_rows.append([TAXONOMY_VALUES[c][i] if i < len(TAXONOMY_VALUES[c]) else ""
                         for c in tax_cols])
    tax.clear()
    tax.update("A1", tax_rows, value_input_option="RAW")
    print(f"_Taxonomy: {len(tax_cols)} колонок, до {maxlen} значень")

    kb.ss.batch_update({"requests": reqs})
    print("DONE — таксономію розширено. Далі: python3 kb_polish.py")


def _col(n):
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


if __name__ == "__main__":
    main()
