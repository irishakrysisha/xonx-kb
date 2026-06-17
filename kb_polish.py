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
from kb_schema import (TABLES, HIDDEN_COLUMNS, SUMMARY_COL, KEYWORDS_COL,
                       CHECKBOX_COLUMNS, TAXONOMY, TAXONOMY_VALUES, INBOX, INBOX_COLUMNS)

# чистий «людський» вигляд: лишаємо видимим лише суттєве, решту ховаємо
# (дані не зникають — лишаються для пошуку/AI, просто не муляють)
EXTRA_HIDDEN = {
    "Прецеденти": {"Перевірений локалом", "Власник", "Джерело"},
    "Шаблони":    {"Власник", "Джерело"},
    "Рісьорчі":   {"Питання / тригер", "Підтверджено локалом", "Власник", "Джерело"},
    # провайдери: показуємо короткий Опис, ховаємо довгий дамп «Ключові слова»;
    # обов'язкові роль-маркери (Поінт/Хто приніс/Партнер) — видимі
    "Провайдери": {KEYWORDS_COL},
}

URL_COLS = {"Файл", "Папка на Drive"}
URL_LABEL = {"Файл": "Файл ↗", "Папка на Drive": "Папка ↗"}

WIDTHS = {
    "ID": 84, "Назва": 240, "Опис": 360, "Ключові слова": 300, "Послуги": 340,
    "Питання / тригер": 280, "Категорія": 130, "Право": 110, "Юрисдикція": 90,
    "Тип документа": 170, "Форма": 130,
    "Юрисдикція / регіон": 120, "Тип послуги": 175, "Контакти": 180,
    "Поінт оф контакт": 120, "Хто приніс контакт": 130, "Оцінка": 120, "Партнер": 80,
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


def _header_req(sid, ncols):
    """Шапка таблиці — графіт, жирний кремовий Inter (єдиний стиль усюди)."""
    return {"repeatCell": {
        "range": {"sheetId": sid, "startRowIndex": 0, "endRowIndex": 1,
                  "startColumnIndex": 0, "endColumnIndex": ncols},
        "cell": {"userEnteredFormat": {
            "backgroundColor": bp.GRAPHITE, "verticalAlignment": "MIDDLE",
            "wrapStrategy": "WRAP", "padding": {"left": 8, "top": 4, "bottom": 4, "right": 4},
            "textFormat": {"bold": True, "foregroundColor": bp.CREAM,
                           "fontSize": 10, "fontFamily": "Inter"}}},
        "fields": "userEnteredFormat(backgroundColor,verticalAlignment,wrapStrategy,padding,textFormat)"}}


def _clear_below(sid, nrows, ncols):
    """Прибрати будь-яке форматування нижче даних (білий фон, без бордюрів)."""
    reqs = [{"repeatCell": {
        "range": {"sheetId": sid, "startRowIndex": max(nrows, 1), "endRowIndex": 1000,
                  "startColumnIndex": 0, "endColumnIndex": ncols + 2},
        "cell": {"userEnteredFormat": {
            "backgroundColor": bp.rgb("#FFFFFF"),
            "textFormat": {"fontFamily": "Inter", "foregroundColor": bp.TEXT}}},
        "fields": "userEnteredFormat(backgroundColor,textFormat)"}},
        {"updateBorders": {
            "range": {"sheetId": sid, "startRowIndex": max(nrows, 1), "endRowIndex": 1000,
                      "startColumnIndex": 0, "endColumnIndex": ncols + 2},
            "top": {"style": "NONE"}, "bottom": {"style": "NONE"},
            "left": {"style": "NONE"}, "right": {"style": "NONE"},
            "innerHorizontal": {"style": "NONE"}, "innerVertical": {"style": "NONE"}}}]
    return reqs


def _style_reference(ws, cols, widths=None, freeze_col=False):
    """Шапка+тіло+бордюри+ширини+заморозка для довідкових вкладок (_Taxonomy / Inbox)."""
    vals = ws.get_all_values()
    sid = ws.id
    ncols = len(cols)
    nrows = sum(1 for r in vals[1:] if any(c.strip() for c in r)) + 1
    reqs = [_header_req(sid, ncols), bp.data_rows_req(sid, 1, max(nrows, 2), ncols),
            bp.border_req(sid, 0, nrows, ncols)]
    reqs += _clear_below(sid, nrows, ncols)
    for idx, c in enumerate(cols):
        reqs.append({"updateDimensionProperties": {
            "range": {"sheetId": sid, "dimension": "COLUMNS",
                      "startIndex": idx, "endIndex": idx + 1},
            "properties": {"pixelSize": (widths or {}).get(c, 150)}, "fields": "pixelSize"}})
    reqs.append({"updateSheetProperties": {
        "properties": {"sheetId": sid, "gridProperties": {
            "frozenRowCount": 1, "frozenColumnCount": 1 if freeze_col else 0}},
        "fields": "gridProperties(frozenRowCount,frozenColumnCount)"}})
    return reqs, [c for c in cols]


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

        # 0b) єдиний базовий стиль: графіт-шапка + кремове тіло + чистка нижче даних
        #     (важливо після міграції — колонки зсунулись, формат був позиційний)
        reqs.append(_header_req(sid, len(cols)))
        reqs.append(bp.data_rows_req(sid, 1, max(nrows, 2), len(cols)))
        reqs += _clear_below(sid, nrows, len(cols))

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
        cb_value_updates = []
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
                    # нормалізувати значення в СПРАВЖНІ булеві (інакше текст "TRUE"
                    # ламає галочку) — перезаписуємо USER_ENTERED
                    for r in range(1, nrows):
                        raw = (vals[r][idx] if idx < len(vals[r]) else "").strip().upper()
                        cb_value_updates.append({
                            "range": f"{name}!{_a1(r + 1, idx + 1)}",
                            "values": [[True if raw in ("TRUE", "✓", "✔", "ТАК") else False]]})

        # 4) світлі бордюри тільки по даних
        reqs.append(bp.border_req(sid, 0, nrows, len(cols)))

        # очистити все нижче даних (FALSE-буфер, артефакти валідації)
        if nrows < 999:
            ws.batch_clear([f"A{nrows + 1}:Z1000"])

        kb.ss.batch_update({"requests": reqs})

        # 3b) застосувати нормалізовані булеві значення чекбоксів
        if cb_value_updates:
            kb.ss.values_batch_update(
                {"valueInputOption": "USER_ENTERED", "data": cb_value_updates})

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

    # --- довідкові вкладки: _Taxonomy + Inbox (теж у фірмовому стилі) ---
    tax_w = {"Тип документа": 240, "Тип послуги": 230, "Сфера": 180,
             "Цільова полиця": 130, "Категорія": 170, "Юрисдикція": 110,
             "Форма": 140, "Оцінка": 130, "Статус": 130, "Статус ревʼю": 130}
    tax_reqs, tax_cols = _style_reference(
        kb.ss.worksheet(TAXONOMY), list(TAXONOMY_VALUES.keys()),
        widths=tax_w, freeze_col=False)
    kb.ss.batch_update({"requests": tax_reqs})
    print(f"_Taxonomy: brand style applied | {len(tax_cols)} колонок")

    inbox_w = dict(WIDTHS); inbox_w.update(
        {"Temp_ID": 90, "Цільова полиця": 120, "Опис": 360, "Деталі_JSON": 220,
         "Ким запропоновано": 140, "Коли": 150, "Рецензент": 110, "Нотатки": 200,
         "Result_ID": 90})
    inbox_ws = kb.ss.worksheet(INBOX)
    in_reqs, _ = _style_reference(inbox_ws, INBOX_COLUMNS,
                                  widths=inbox_w, freeze_col=True)
    # декluttering: гасимо сірим оброблені рядки (approved/rejected) — у фокусі pending
    sid_in = inbox_ws.id
    st = _a1(2, INBOX_COLUMNS.index("Статус ревʼю") + 1).rstrip("2")  # літера колонки
    # прибрати старі CF на Inbox, тоді додати наше
    meta = kb.ss.fetch_sheet_metadata(
        {"fields": "sheets(properties(title),conditionalFormats)"})
    cnt = next((len(s.get("conditionalFormats", [])) for s in meta["sheets"]
                if s["properties"]["title"] == INBOX), 0)
    for i in range(cnt - 1, -1, -1):
        in_reqs.append({"deleteConditionalFormatRule": {"sheetId": sid_in, "index": i}})
    in_reqs.append({"addConditionalFormatRule": {"index": 0, "rule": {
        "ranges": [{"sheetId": sid_in, "startRowIndex": 1, "endRowIndex": 1000,
                    "startColumnIndex": 0, "endColumnIndex": len(INBOX_COLUMNS)}],
        "booleanRule": {
            "condition": {"type": "CUSTOM_FORMULA", "values": [{"userEnteredValue":
                f'=OR(${st}2="approved",${st}2="rejected")'}]},
            "format": {"backgroundColor": bp.WARM,
                       "textFormat": {"foregroundColor": bp.DIM, "italic": True}}}}}})
    kb.ss.batch_update({"requests": in_reqs})
    print("Inbox: brand style applied + done-rows greyed")

    print("DONE — KB у фірмовому стилі")


def _a1(row, col):
    s = ""
    while col:
        col, rem = divmod(col - 1, 26)
        s = chr(65 + rem) + s
    return f"{s}{row}"


if __name__ == "__main__":
    main()
