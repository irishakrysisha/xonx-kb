"""Будує гарну інтерактивну стартову сторінку (вкладка Home).

Hero + картки полиць із живими лічильниками (COUNTA, автооновлення) і
клікабельними переходами на вкладки + кнопка Inbox + коротка інструкція.
Фірмові кольори X-ON-X. Безпечно перезапускати: `python3 kb_home.py`
"""
import os
import sys
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sheets"))
import brand_palette as bp

from kb_api import KB

CFG = json.load(open(os.path.join(os.path.dirname(__file__), "kb_config.json")))
SSID = CFG["spreadsheet_id"]
INBOX_URL = "https://drive.google.com/drive/folders/" + CFG["folders"]["_Inbox"]

SHELVES = [
    ("Прецеденти", "Реальні кейси й документи з проєктів"),
    ("Шаблони", "Готові документи для повторного використання"),
    ("Рісьорчі", "Меморандуми, аналіз, відповіді на питання"),
    ("Провайдери", "Зовнішні юристи, нотаріуси, сервіси — з контактами"),
]


def _link(gid, label):
    return f'=HYPERLINK("https://docs.google.com/spreadsheets/d/{SSID}/edit#gid={gid}","{label}")'


def main():
    kb = KB()
    home = kb.ss.worksheet("Home")
    gid = {ws.title: ws.id for ws in kb.ss.worksheets()}
    sid = home.id

    # --- content grid (A..D) ---
    rows = [
        ["X-ON-X Knowledge Base", "", "", ""],
        ["Юридична база знань — шукай у вкладках, відкривай файли, користуйся", "", "", ""],
        ["", "", "", ""],
        ["ПОЛИЦІ", "", "", ""],
    ]
    card_rows = []
    for name, desc in SHELVES:
        r = len(rows)
        card_rows.append(r)
        rows.append([name, f'=COUNTA(\'{name}\'!A2:A)', desc, _link(gid[name], "Відкрити →")])
    rows += [
        ["", "", "", ""],
        ["ДОДАТИ НОВЕ", "", "", ""],
        ["Кинь файл (PDF / DOCX / PPTX / текст) у папку Inbox — за годину він "
         "сам зʼявиться у потрібній полиці, розкласифікований.", "", "",
         f'=HYPERLINK("{INBOX_URL}","Inbox →")'],
        ["", "", "", ""],
        ["ЯК КОРИСТУВАТИСЬ", "", "", ""],
        ["1.  Відкрий полицю у вкладках знизу або карткою вище.", "", "", ""],
        ["2.  Знайди потрібне — за назвою, категорією/сферою, описом.", "", "", ""],
        ["3.  Клікни «Файл ↗» / «Папка ↗» у рядку, щоб відкрити документ.", "", "", ""],
        ["", "", "", ""],
        ["X-ON-X Legal · каталог оновлюється автоматично", "", "", ""],
    ]
    inbox_row = card_rows[-1] + 3            # ДОДАТИ НОВЕ text row
    sec_add = card_rows[-1] + 2
    sec_use = inbox_row + 2
    foot = len(rows) - 1

    home.clear()
    home.update("A1", rows, value_input_option="USER_ENTERED")

    NC = 4
    def rng(r0, r1, c0=0, c1=NC):
        return {"sheetId": sid, "startRowIndex": r0, "endRowIndex": r1,
                "startColumnIndex": c0, "endColumnIndex": c1}
    def merge(r):
        return {"mergeCells": {"range": rng(r, r + 1), "mergeType": "MERGE_ALL"}}
    def fmt(r0, r1, c0, c1, cell, fields):
        return {"repeatCell": {"range": rng(r0, r1, c0, c1),
                "cell": {"userEnteredFormat": cell}, "fields": fields}}

    reqs = []
    # whole sheet cream bg + Inter
    reqs.append(fmt(0, len(rows), 0, NC,
                    {"backgroundColor": bp.CREAM,
                     "textFormat": {"fontFamily": "Inter", "foregroundColor": bp.TEXT}},
                    "userEnteredFormat(backgroundColor,textFormat)"))
    # title
    reqs += [merge(0), fmt(0, 1, 0, NC,
             {"backgroundColor": bp.GRAPHITE, "verticalAlignment": "MIDDLE",
              "padding": {"left": 18}, "textFormat": {"bold": True, "fontSize": 20,
              "foregroundColor": bp.CREAM, "fontFamily": "Inter"}},
             "userEnteredFormat(backgroundColor,verticalAlignment,padding,textFormat)")]
    # subtitle
    reqs += [merge(1), fmt(1, 2, 0, NC,
             {"backgroundColor": bp.GRAPHITE, "padding": {"left": 18},
              "textFormat": {"fontSize": 11, "foregroundColor": bp.WARM, "fontFamily": "Inter"}},
             "userEnteredFormat(backgroundColor,padding,textFormat)")]
    # section headers
    for r in (3, sec_add, sec_use):
        reqs += [merge(r), fmt(r, r + 1, 0, NC,
                 {"backgroundColor": bp.LIME_BG, "padding": {"left": 16},
                  "verticalAlignment": "MIDDLE",
                  "textFormat": {"bold": True, "fontSize": 11, "foregroundColor": bp.LIME_TEXT,
                  "fontFamily": "Inter"}},
                 "userEnteredFormat(backgroundColor,padding,verticalAlignment,textFormat)")]
    # cards
    for r in card_rows:
        reqs.append(fmt(r, r + 1, 0, 1, {"backgroundColor": bp.WARM, "verticalAlignment": "MIDDLE",
                    "padding": {"left": 16}, "textFormat": {"bold": True, "fontSize": 13,
                    "foregroundColor": bp.TEXT, "fontFamily": "Inter"}},
                    "userEnteredFormat(backgroundColor,verticalAlignment,padding,textFormat)"))
        reqs.append(fmt(r, r + 1, 1, 2, {"backgroundColor": bp.LIME_BG, "horizontalAlignment": "CENTER",
                    "verticalAlignment": "MIDDLE", "textFormat": {"bold": True, "fontSize": 18,
                    "foregroundColor": bp.LIME_TEXT, "fontFamily": "Inter"}},
                    "userEnteredFormat(backgroundColor,horizontalAlignment,verticalAlignment,textFormat)"))
        reqs.append(fmt(r, r + 1, 2, 3, {"backgroundColor": bp.WARM, "verticalAlignment": "MIDDLE",
                    "textFormat": {"fontSize": 10, "foregroundColor": bp.TEXT_SEC, "fontFamily": "Inter"}},
                    "userEnteredFormat(backgroundColor,verticalAlignment,textFormat)"))
        reqs.append(fmt(r, r + 1, 3, 4, {"backgroundColor": bp.WARM, "horizontalAlignment": "CENTER",
                    "verticalAlignment": "MIDDLE", "textFormat": {"bold": True, "fontSize": 11,
                    "foregroundColor": bp.LIME_TEXT, "fontFamily": "Inter"}},
                    "userEnteredFormat(backgroundColor,horizontalAlignment,verticalAlignment,textFormat)"))
    # inbox row: text (A:C) + button (D)
    reqs += [{"mergeCells": {"range": rng(inbox_row, inbox_row + 1, 0, 3), "mergeType": "MERGE_ALL"}}]
    reqs.append(fmt(inbox_row, inbox_row + 1, 0, 3, {"backgroundColor": bp.CREAM, "wrapStrategy": "WRAP",
                "verticalAlignment": "MIDDLE", "padding": {"left": 16},
                "textFormat": {"fontSize": 10, "foregroundColor": bp.TEXT, "fontFamily": "Inter"}},
                "userEnteredFormat(backgroundColor,wrapStrategy,verticalAlignment,padding,textFormat)"))
    reqs.append(fmt(inbox_row, inbox_row + 1, 3, 4, {"backgroundColor": bp.GRAPHITE,
                "horizontalAlignment": "CENTER", "verticalAlignment": "MIDDLE",
                "textFormat": {"bold": True, "fontSize": 11, "foregroundColor": bp.CREAM, "fontFamily": "Inter"}},
                "userEnteredFormat(backgroundColor,horizontalAlignment,verticalAlignment,textFormat)"))
    # how-to steps + footer merged
    for r in (sec_use + 1, sec_use + 2, sec_use + 3):
        reqs += [merge(r), fmt(r, r + 1, 0, NC, {"padding": {"left": 18},
                 "textFormat": {"fontSize": 11, "foregroundColor": bp.TEXT, "fontFamily": "Inter"}},
                 "userEnteredFormat(padding,textFormat)")]
    reqs += [merge(foot), fmt(foot, foot + 1, 0, NC, {"padding": {"left": 18},
             "textFormat": {"italic": True, "fontSize": 9, "foregroundColor": bp.DIM, "fontFamily": "Inter"}},
             "userEnteredFormat(padding,textFormat)")]
    # widths + row heights + freeze + hide gridlines
    widths = [(0, 1, 210), (1, 2, 90), (2, 3, 380), (3, 4, 140)]
    for c0, c1, px in widths:
        reqs.append({"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "COLUMNS",
                    "startIndex": c0, "endIndex": c1}, "properties": {"pixelSize": px}, "fields": "pixelSize"}})
    reqs.append({"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "ROWS",
                "startIndex": 0, "endIndex": 1}, "properties": {"pixelSize": 46}, "fields": "pixelSize"}})
    for r in card_rows:
        reqs.append({"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "ROWS",
                    "startIndex": r, "endIndex": r + 1}, "properties": {"pixelSize": 40}, "fields": "pixelSize"}})
    reqs.append({"updateSheetProperties": {"properties": {"sheetId": sid,
                "gridProperties": {"hideGridlines": True, "frozenRowCount": 2}},
                "fields": "gridProperties(hideGridlines,frozenRowCount)"}})

    kb.ss.batch_update({"requests": reqs})
    print("Home rebuilt — interactive landing")


if __name__ == "__main__":
    main()
