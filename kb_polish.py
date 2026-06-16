"""Косметика KB у фірмовому стилі X-ON-X — охайно і зручно для людей.

- ховає службові колонки (HIDDEN_COLUMNS) — лишається тільки потрібне користувачу
- сирі Drive-URL (Файл / Папка на Drive) → клікабельне «↗» (HYPERLINK)
- кольорове кодування Статусу й Оцінки фірмовими тонами (lime/amber/pink/warm)
- підігнані ширини, перенос тексту, світлі бордюри

Безпечно перезапускати. `python3 kb_polish.py`
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sheets"))
import brand_palette as bp

from kb_api import KB
from kb_schema import TABLES, HIDDEN_COLUMNS, SUMMARY_COL, CHECKBOX_COLUMNS

# чистий «людський» вигляд: лишаємо видимим лише суттєве, решту ховаємо
# (дані не зникають — лишаються для пошуку/AI, просто не муляють)
EXTRA_HIDDEN = {
    "Прецеденти": {"Перевірений локалом", "Власник", "Джерело"},
    "Шаблони":    {"Власник", "Джерело"},
    "Рісьорчі":   {"Питання / тригер", "Підтверджено локалом", "Власник", "Джерело"},
    "Провайдери": {SUMMARY_COL, "Партнер", "Поінт оф контакт"},
}

URL_COLS = {"Файл", "Папка на Drive"}
URL_LABEL = {"Файл": "Файл ↗", "Папка на Drive": "Папка ↗"}

WIDTHS = {
    "ID": 84, "Назва": 240, "Опис": 420, "Послуги": 340,
    "Питання / тригер": 280, "Категорія": 130, "Юрисдикція": 90,
    "Юрисдикція / регіон": 120, "Тип послуги": 150, "Контакти": 180,
    "Поінт оф контакт": 120, "Оцінка": 120, "Партнер": 80,
    "Файл": 90, "Папка на Drive": 90, "Статус": 110,
    "Перевірений локалом": 130, "Підтверджено локалом": 140, "Власник": 110,
    "Джерело": 200,
}

# фірмові тони (bg + text) для статус/оцінка
STATUS_COLORS = {
    "active": (bp.LIME_BG, bp.LIME_TEXT),
    "pending-PII": (bp.AMBER_BG, bp.AMBER_TEXT),
    "needs-review": (bp.PINK_BG, bp.PINK_TEXT),
    "archived": (bp.WARM, bp.TEXT_SEC),
}
RATING_COLORS = {
    "Recommended": (bp.LIME_BG, bp.LIME_TEXT),
    "Okay": (bp.WARM, bp.TEXT_SEC),
    "Avoid": (bp.PINK_BG, bp.PINK_TEXT),
}


def _cf_rule(sid, ci, value, bg, fg):
    return {"addConditionalFormatRule": {"index": 0, "rule": {
        "ranges": [{"sheetId": sid, "startRowIndex": 1, "endRowIndex": 1000,
                    "startColumnIndex": ci, "endColumnIndex": ci + 1}],
        "booleanRule": {
            "condition": {"type": "TEXT_EQ", "values": [{"userEnteredValue": value}]},
            "format": {"backgroundColor": bg,
                       "textFormat": {"foregroundColor": fg, "bold": True}}}}}}


def _existing_cf_counts(ss, titles):
    meta = ss.fetch_sheet_metadata(
        {"fields": "sheets(properties(sheetId,title),conditionalFormats)"})
    out = {}
    for s in meta["sheets"]:
        t = s["properties"]["title"]
        if t in titles:
            out[t] = (s["properties"]["sheetId"], len(s.get("conditionalFormats", [])))
    return out


def main():
    kb = KB()
    titles = list(TABLES.keys())
    cf_counts = _existing_cf_counts(kb.ss, titles)

    for name, spec in TABLES.items():
        ws = kb.ss.worksheet(name)
        cols = spec["columns"]
        vals = ws.get_all_values()
        sid = ws.id
        nrows = sum(1 for r in vals[1:] if r and r[0].strip()) + 1
        reqs = []

        # 0) видалити старі CF-правила (щоб не накладались generic поверх бренду)
        _, cnt = cf_counts.get(name, (sid, 0))
        for i in range(cnt - 1, -1, -1):
            reqs.append({"deleteConditionalFormatRule": {"sheetId": sid, "index": i}})

        # 1) ширини + ховання службових (глобальні + пер-вкладкові)
        hide = HIDDEN_COLUMNS | EXTRA_HIDDEN.get(name, set())
        for idx, c in enumerate(cols):
            reqs.append({"updateDimensionProperties": {
                "range": {"sheetId": sid, "dimension": "COLUMNS",
                          "startIndex": idx, "endIndex": idx + 1},
                "properties": {"pixelSize": WIDTHS.get(c, 150),
                               "hiddenByUser": c in hide},
                "fields": "pixelSize,hiddenByUser"}})

        # 2) фірмове кольорове кодування
        if "Статус" in cols:
            ci = cols.index("Статус")
            for v, (bg, fg) in STATUS_COLORS.items():
                reqs.append(_cf_rule(sid, ci, v, bg, fg))
        if "Оцінка" in cols:
            ci = cols.index("Оцінка")
            for v, (bg, fg) in RATING_COLORS.items():
                reqs.append(_cf_rule(sid, ci, v, bg, fg))

        # 3) чекбокси ТІЛЬКИ на рядках з даними (інакше порожні рядки рябіють FALSE)
        for idx, c in enumerate(cols):
            if c in CHECKBOX_COLUMNS:
                # прибрати будь-яку валідацію з усієї колонки…
                reqs.append({"setDataValidation": {
                    "range": {"sheetId": sid, "startRowIndex": 1, "endRowIndex": 1000,
                              "startColumnIndex": idx, "endColumnIndex": idx + 1}}})
                # …і повернути BOOLEAN лише там, де є дані
                if nrows > 1:
                    reqs.append({"setDataValidation": {
                        "range": {"sheetId": sid, "startRowIndex": 1, "endRowIndex": nrows,
                                  "startColumnIndex": idx, "endColumnIndex": idx + 1},
                        "rule": {"condition": {"type": "BOOLEAN"}}}})

        # 4) світлі бордюри тільки по даних
        reqs.append(bp.border_req(sid, 0, nrows, len(cols)))

        # очистити все нижче даних (FALSE-буфер, артефакти валідації)
        if nrows < 999:
            ws.batch_clear([f"A{nrows + 1}:Z1000"])

        kb.ss.batch_update({"requests": reqs})

        # 4) сирі URL → HYPERLINK «↗»
        link_updates = []
        header = vals[0]
        for c in URL_COLS:
            if c not in header:
                continue
            ci = header.index(c)
            for r in range(1, len(vals)):
                cell = vals[r][ci] if ci < len(vals[r]) else ""
                if cell.startswith("http"):
                    link_updates.append({
                        "range": f"{name}!{_a1(r + 1, ci + 1)}",
                        "values": [[f'=HYPERLINK("{cell}","{URL_LABEL[c]}")']]})
        if link_updates:
            kb.ss.values_batch_update(
                {"valueInputOption": "USER_ENTERED", "data": link_updates})

        vis = [c for c in cols if c not in hide]
        print(f"{name}: brand style applied | visible: {vis}")

    print("DONE — KB у фірмовому стилі")


def _a1(row, col):
    s = ""
    while col:
        col, rem = divmod(col - 1, 26)
        s = chr(65 + rem) + s
    return f"{s}{row}"


if __name__ == "__main__":
    main()
