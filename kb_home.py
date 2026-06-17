"""Інтерактивна стартова сторінка (вкладка Home) — усе на формулах, живе.

Фічі:
  • ЖИВИЙ ПОШУК прямо в шиті — пишеш слово в комірку, нижче спливають картки
    з усіх полиць (QUERY по прихованому _Index, оновлюється сам).
  • ЖИВА СТАТИСТИКА — лічильники + міні-бари (REPT) по полицях і по governing law.
  • Картки полиць із переходами, кнопка Inbox, інструкція.

Будує також прихований аркуш _Index = зведення [Тип|ID|Назва|Право/Сфера|Опис]
з усіх чотирьох таблиць (джерело для пошуку). Фірмові кольори X-ON-X.
Безпечно перезапускати: `python3 kb_home.py`
"""
import os
import sys
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sheets"))
import brand_palette as bp

from kb_api import KB
from kb_schema import TABLES

CFG = json.load(open(os.path.join(os.path.dirname(__file__), "kb_config.json")))
SSID = CFG["spreadsheet_id"]
INBOX_URL = "https://drive.google.com/drive/folders/" + CFG["folders"]["_Inbox"]

SHELVES = [
    ("Прецеденти", "Реальні кейси й документи з проєктів", "Прецедент", "Право"),
    ("Шаблони", "Готові документи для повторного використання", "Шаблон", "Право"),
    ("Рісьорчі", "Меморандуми, аналіз, відповіді на питання", "Рісьорч", "Сфера"),
    ("Провайдери", "Зовнішні юристи, нотаріуси, сервіси — контакти", "Провайдер", "Тип послуги"),
]
LAWS = ["UA", "UK", "DE", "EU", "US"]   # для міні-чарту governing law
NC = 5


def _letter(n):
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def _col(table, name):
    return _letter(TABLES[table]["columns"].index(name) + 1)


def _link(gid, label):
    return f'=HYPERLINK("https://docs.google.com/spreadsheets/d/{SSID}/edit#gid={gid}","{label}")'


def _index_formula():
    """Зведення карток: Тип | ID | Назва | Facet | Опис | Ключові слова.
    Колонка F (ключові слова) — лише для пошуку, у видачі не показується."""
    blocks = []
    for tname, _desc, label, facet in SHELVES:
        naz = _col(tname, "Назва")
        fac = _col(tname, facet)
        opy = _col(tname, "Опис")
        kw = _col(tname, "Ключові слова")
        blocks.append(
            f'ARRAYFORMULA(IF(LEN(\'{tname}\'!{naz}2:{naz}),"{label}","")), '
            f'\'{tname}\'!A2:A, \'{tname}\'!{naz}2:{naz}, '
            f'\'{tname}\'!{fac}2:{fac}, \'{tname}\'!{opy}2:{opy}, '
            f'\'{tname}\'!{kw}2:{kw}')
    return "=IFERROR({" + " ; ".join(blocks) + "},)"


def _ensure_index(kb):
    try:
        ws = kb.ss.worksheet("_Index")
    except Exception:
        ws = kb.ss.add_worksheet(title="_Index", rows=4000, cols=6)
    ws.batch_clear(["A1:F4000"])
    ws.update("A1", [[_index_formula()]], value_input_option="USER_ENTERED")
    # сховати службовий аркуш
    kb.ss.batch_update({"requests": [{"updateSheetProperties": {
        "properties": {"sheetId": ws.id, "hidden": True}, "fields": "hidden"}}]})
    return ws


def main():
    kb = KB()
    _ensure_index(kb)
    home = kb.ss.worksheet("Home")
    gid = {ws.title: ws.id for ws in kb.ss.worksheets()}
    sid = home.id

    rows, idx = [], {}
    def add(row):
        rows.append(row + [""] * (NC - len(row)))
        return len(rows) - 1

    idx["title"] = add(["X-ON-X Knowledge Base"])
    idx["sub"] = add(["Юридична база знань — шукай, відкривай, користуйся"])
    add([])
    idx["sec_stat"] = add(["ЖИВА СТАТИСТИКА"])
    stat_rows = []
    for tname, *_ in SHELVES:
        r = add([tname, f"=COUNTA('{tname}'!A2:A)",
                 f'=IF(B{0}=0,"—",REPT("▮",MIN(30,B{0})))'])  # B{r} підставимо нижче
        stat_rows.append(r)
    add([])
    idx["sec_law"] = add(["ЗА ПРАВОМ (governing law)"])
    law_rows = []
    docres = ["Прецеденти", "Шаблони", "Рісьорчі"]
    for law in LAWS:
        cnt = "+".join(f"COUNTIF('{t}'!{_col(t, 'Право')}2:{_col(t, 'Право')},\"{law}\")"
                       for t in docres)
        r = add([law, "=" + cnt, ""])  # бар нижче
        law_rows.append(r)
    add([])
    idx["sec_cards"] = add(["ПОЛИЦІ"])
    card_rows = []
    for tname, desc, *_ in SHELVES:
        r = add([tname, f"=COUNTA('{tname}'!A2:A)", desc, _link(gid[tname], "Відкрити →")])
        card_rows.append(r)
    add([])
    idx["sec_add"] = add(["ДОДАТИ НОВЕ"])
    idx["inbox"] = add(["Кинь файл (PDF / DOCX / PPTX / текст) у папку Inbox — раз на "
                        "день бот сам розкласифікує його в потрібну полицю.", "", "", "",
                        f'=HYPERLINK("{INBOX_URL}","Inbox →")'])
    add([])
    idx["sec_find"] = add(["ПОШУК ПО БАЗІ"])
    idx["search"] = add(["🔎 Шукати:", "", "", "пиши слово — картки нижче оновлюються самі"])
    idx["res_head"] = add(["Тип", "ID", "Назва", "Право / Сфера", "Опис"])
    idx["res"] = add([])  # сюди формула
    foot = idx["res"] + 13
    while len(rows) <= foot:
        add([])
    rows[foot] = ["X-ON-X Legal · каталог і пошук оновлюються автоматично", "", "", "", ""]

    # --- формули, що залежать від власного номера рядка ---
    for r in stat_rows:
        rows[r][2] = f'=IF(B{r+1}=0,"—",REPT("▮",MIN(30,B{r+1})))'
    for r in law_rows:
        rows[r][2] = f'=IF(B{r+1}=0,"—",REPT("▮",MIN(30,B{r+1})))'
    s1 = idx["search"] + 1               # 1-based рядок поля пошуку
    inp = f"B{s1}"
    res1 = idx["res"] + 1
    rows[idx["res"]][0] = (
        f'=IFERROR(QUERY(_Index!A:F,"select A,B,C,D,E where B <> \'\' and '
        f'(lower(C) contains \'"&LOWER({inp})&"\' or lower(D) contains \'"&LOWER({inp})'
        f'&"\' or lower(E) contains \'"&LOWER({inp})&"\' or lower(F) contains \'"'
        f'&LOWER({inp})&"\') limit 12 label A \'\', B \'\', C \'\', D \'\', E \'\'",0),'
        f'"Нічого не знайдено")')

    home.clear()
    home.update("A1", rows, value_input_option="USER_ENTERED")

    # ---------- стиль ----------
    def rng(r0, r1, c0=0, c1=NC):
        return {"sheetId": sid, "startRowIndex": r0, "endRowIndex": r1,
                "startColumnIndex": c0, "endColumnIndex": c1}
    def merge(r, c0=0, c1=NC):
        return {"mergeCells": {"range": rng(r, r + 1, c0, c1), "mergeType": "MERGE_ALL"}}
    def fmt(r0, r1, c0, c1, cell, fields):
        return {"repeatCell": {"range": rng(r0, r1, c0, c1),
                "cell": {"userEnteredFormat": cell}, "fields": fields}}

    reqs = []
    # зняти старі merge з попередньої версії Home (clear() їх не прибирає)
    reqs.append({"unmergeCells": {"range": {"sheetId": sid, "startRowIndex": 0,
                "endRowIndex": len(rows) + 50, "startColumnIndex": 0, "endColumnIndex": NC}}})
    reqs.append(fmt(0, len(rows), 0, NC,
                    {"backgroundColor": bp.CREAM,
                     "textFormat": {"fontFamily": "Inter", "foregroundColor": bp.TEXT}},
                    "userEnteredFormat(backgroundColor,textFormat)"))
    # title / subtitle
    reqs += [merge(idx["title"]), fmt(idx["title"], idx["title"] + 1, 0, NC,
             {"backgroundColor": bp.GRAPHITE, "verticalAlignment": "MIDDLE",
              "padding": {"left": 18}, "textFormat": {"bold": True, "fontSize": 20,
              "foregroundColor": bp.CREAM, "fontFamily": "Inter"}},
             "userEnteredFormat(backgroundColor,verticalAlignment,padding,textFormat)")]
    reqs += [merge(idx["sub"]), fmt(idx["sub"], idx["sub"] + 1, 0, NC,
             {"backgroundColor": bp.GRAPHITE, "padding": {"left": 18},
              "textFormat": {"fontSize": 11, "foregroundColor": bp.WARM, "fontFamily": "Inter"}},
             "userEnteredFormat(backgroundColor,padding,textFormat)")]
    # section headers
    for key in ("sec_stat", "sec_law", "sec_cards", "sec_add", "sec_find"):
        r = idx[key]
        reqs += [merge(r), fmt(r, r + 1, 0, NC,
                 {"backgroundColor": bp.LIME_BG, "padding": {"left": 16},
                  "verticalAlignment": "MIDDLE", "textFormat": {"bold": True, "fontSize": 11,
                  "foregroundColor": bp.LIME_TEXT, "fontFamily": "Inter"}},
                 "userEnteredFormat(backgroundColor,padding,verticalAlignment,textFormat)")]
    # stat + law rows: name(A) bold, count(B) center lime, bar(C:E) lime text
    for r in stat_rows + law_rows:
        reqs.append(fmt(r, r + 1, 0, 1, {"verticalAlignment": "MIDDLE", "padding": {"left": 16},
                    "textFormat": {"bold": True, "fontSize": 11, "foregroundColor": bp.TEXT,
                    "fontFamily": "Inter"}}, "userEnteredFormat(verticalAlignment,padding,textFormat)"))
        reqs.append(fmt(r, r + 1, 1, 2, {"horizontalAlignment": "CENTER", "verticalAlignment": "MIDDLE",
                    "textFormat": {"bold": True, "fontSize": 12, "foregroundColor": bp.LIME_TEXT,
                    "fontFamily": "Inter"}}, "userEnteredFormat(horizontalAlignment,verticalAlignment,textFormat)"))
        reqs += [merge(r, 2, NC), fmt(r, r + 1, 2, NC, {"verticalAlignment": "MIDDLE",
                 "textFormat": {"fontSize": 12, "foregroundColor": bp.LIME_TEXT, "fontFamily": "Inter"}},
                 "userEnteredFormat(verticalAlignment,textFormat)")]
    # cards
    for r in card_rows:
        reqs.append(fmt(r, r + 1, 0, 1, {"backgroundColor": bp.WARM, "verticalAlignment": "MIDDLE",
                    "padding": {"left": 16}, "textFormat": {"bold": True, "fontSize": 13,
                    "foregroundColor": bp.TEXT, "fontFamily": "Inter"}},
                    "userEnteredFormat(backgroundColor,verticalAlignment,padding,textFormat)"))
        reqs.append(fmt(r, r + 1, 1, 2, {"backgroundColor": bp.LIME_BG, "horizontalAlignment": "CENTER",
                    "verticalAlignment": "MIDDLE", "textFormat": {"bold": True, "fontSize": 16,
                    "foregroundColor": bp.LIME_TEXT, "fontFamily": "Inter"}},
                    "userEnteredFormat(backgroundColor,horizontalAlignment,verticalAlignment,textFormat)"))
        reqs.append(fmt(r, r + 1, 2, 3, {"backgroundColor": bp.WARM, "verticalAlignment": "MIDDLE",
                    "textFormat": {"fontSize": 10, "foregroundColor": bp.TEXT_SEC, "fontFamily": "Inter"}},
                    "userEnteredFormat(backgroundColor,verticalAlignment,textFormat)"))
        reqs += [merge(r, 3, NC), fmt(r, r + 1, 3, NC, {"backgroundColor": bp.WARM,
                 "horizontalAlignment": "CENTER", "verticalAlignment": "MIDDLE",
                 "textFormat": {"bold": True, "fontSize": 11, "foregroundColor": bp.LIME_TEXT,
                 "fontFamily": "Inter"}},
                 "userEnteredFormat(backgroundColor,horizontalAlignment,verticalAlignment,textFormat)")]
    # inbox row: text A:D + button E
    ir = idx["inbox"]
    reqs += [merge(ir, 0, 4), fmt(ir, ir + 1, 0, 4, {"backgroundColor": bp.CREAM, "wrapStrategy": "WRAP",
             "verticalAlignment": "MIDDLE", "padding": {"left": 16},
             "textFormat": {"fontSize": 10, "foregroundColor": bp.TEXT, "fontFamily": "Inter"}},
             "userEnteredFormat(backgroundColor,wrapStrategy,verticalAlignment,padding,textFormat)")]
    reqs.append(fmt(ir, ir + 1, 4, NC, {"backgroundColor": bp.GRAPHITE, "horizontalAlignment": "CENTER",
                "verticalAlignment": "MIDDLE", "textFormat": {"bold": True, "fontSize": 11,
                "foregroundColor": bp.CREAM, "fontFamily": "Inter"}},
                "userEnteredFormat(backgroundColor,horizontalAlignment,verticalAlignment,textFormat)"))
    # search row: label A, input B:C (поле), hint D:E
    sr = idx["search"]
    reqs.append(fmt(sr, sr + 1, 0, 1, {"verticalAlignment": "MIDDLE", "padding": {"left": 16},
                "textFormat": {"bold": True, "fontSize": 12, "foregroundColor": bp.TEXT, "fontFamily": "Inter"}},
                "userEnteredFormat(verticalAlignment,padding,textFormat)"))
    reqs += [merge(sr, 1, 3), fmt(sr, sr + 1, 1, 3, {"backgroundColor": {"red": 1, "green": 1, "blue": 1},
             "verticalAlignment": "MIDDLE", "padding": {"left": 10},
             "textFormat": {"fontSize": 12, "foregroundColor": bp.TEXT, "fontFamily": "Inter"}},
             "userEnteredFormat(backgroundColor,verticalAlignment,padding,textFormat)")]
    reqs.append({"updateBorders": {"range": rng(sr, sr + 1, 1, 3),
                 "top": bp.BORDER_STYLE, "bottom": bp.BORDER_STYLE,
                 "left": bp.BORDER_STYLE, "right": bp.BORDER_STYLE}})
    reqs += [merge(sr, 3, NC), fmt(sr, sr + 1, 3, NC, {"verticalAlignment": "MIDDLE", "padding": {"left": 8},
             "textFormat": {"italic": True, "fontSize": 9, "foregroundColor": bp.DIM, "fontFamily": "Inter"}},
             "userEnteredFormat(verticalAlignment,padding,textFormat)")]
    # results header
    rh = idx["res_head"]
    reqs.append(fmt(rh, rh + 1, 0, NC, {"backgroundColor": bp.WARM,
                "textFormat": {"bold": True, "fontSize": 9, "foregroundColor": bp.TEXT, "fontFamily": "Inter"}},
                "userEnteredFormat(backgroundColor,textFormat)"))
    # footer
    reqs += [merge(foot), fmt(foot, foot + 1, 0, NC, {"padding": {"left": 18},
             "textFormat": {"italic": True, "fontSize": 9, "foregroundColor": bp.DIM, "fontFamily": "Inter"}},
             "userEnteredFormat(padding,textFormat)")]
    # widths + heights + freeze + gridlines
    widths = [(0, 1, 160), (1, 2, 80), (2, 3, 300), (3, 4, 150), (4, 5, 340)]
    for c0, c1, px in widths:
        reqs.append({"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "COLUMNS",
                    "startIndex": c0, "endIndex": c1}, "properties": {"pixelSize": px}, "fields": "pixelSize"}})
    reqs.append({"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "ROWS",
                "startIndex": 0, "endIndex": 1}, "properties": {"pixelSize": 46}, "fields": "pixelSize"}})
    for r in card_rows:
        reqs.append({"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "ROWS",
                    "startIndex": r, "endIndex": r + 1}, "properties": {"pixelSize": 38}, "fields": "pixelSize"}})
    reqs.append({"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "ROWS",
                "startIndex": sr, "endIndex": sr + 1}, "properties": {"pixelSize": 34}, "fields": "pixelSize"}})
    reqs.append({"updateSheetProperties": {"properties": {"sheetId": sid,
                "gridProperties": {"hideGridlines": True, "frozenRowCount": 2}},
                "fields": "gridProperties(hideGridlines,frozenRowCount)"}})

    kb.ss.batch_update({"requests": reqs})
    print("Home rebuilt — live search + live stats")


if __name__ == "__main__":
    main()
