"""Build the X-ON-X Knowledge Base prototype end-to-end.

Creates the Drive folder tree, the spreadsheet with all tabs, brand styling,
dropdown validation, seed records with cross-links, and writes kb_config.json
(spreadsheet id + folder ids) for the runtime KB-API to consume.

Idempotency: this is a one-shot builder. Re-running creates a *new* spreadsheet
and folder tree. Run once; iterate on data via kb_api.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sheets"))

import brand_palette as bp  # shared X-ON-X styling helpers
from kb_client import get_clients
from kb_schema import (DRIVE_ROOT_NAME, HOME, INBOX, INBOX_COLUMNS,
                       SPREADSHEET_TITLE, TABLES, TAXONOMY, TAXONOMY_VALUES,
                       CHECKBOX_COLUMNS, HIDDEN_COLUMNS, SUMMARY_COL, STATUS_COL,
                       RELATED_COL, OWNER_COL, CREATED_BY, CREATED_AT, UPDATED_AT)

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "kb_config.json")
FOLDER_MIME = "application/vnd.google-apps.folder"


# --------------------------------------------------------------------------- #
# Drive
# --------------------------------------------------------------------------- #
def mkfolder(drive, name, parent=None):
    meta = {"name": name, "mimeType": FOLDER_MIME}
    if parent:
        meta["parents"] = [parent]
    f = drive.files().create(body=meta, fields="id").execute()
    return f["id"]


def build_drive(drive):
    root = mkfolder(drive, DRIVE_ROOT_NAME)
    folders = {"_root": root}
    for section in ["Precedents", "Templates", "Researches", "Providers", "_Inbox"]:
        folders[section] = mkfolder(drive, section, root)
    # one folder per seed precedent
    folders["PRE-0001"] = mkfolder(drive, "PRE-0001", folders["Precedents"])
    folders["PRE-0002"] = mkfolder(drive, "PRE-0002", folders["Precedents"])
    return folders


def folder_link(fid):
    return f"https://drive.google.com/drive/folders/{fid}"


# --------------------------------------------------------------------------- #
# Seed data (symmetric cross-links)
# --------------------------------------------------------------------------- #
def seed_rows(folders):
    L = folder_link
    return {
        "Прецеденти": [
            {"ID": "PRE-0001", "Назва": "Придбання TechCorp GmbH (share deal)",
             "Категорія": "1.3 Інвестиційні", "Юрисдикція": "Multi",
             "Перевірений локалом": "TRUE", OWNER_COL: "Iryna",
             "Файл": L(folders["PRE-0001"]),
             SUMMARY_COL: "Транскордонна купівля частки в німецькому таргеті. "
                          "Структура угоди з capped warranties і tax indemnity під escrow. "
                          "Див. повʼязаний SPA-шаблон і рісьорч по warranty caps.",
             STATUS_COL: "active", RELATED_COL: "TPL-0001, RES-0001, PRV-0001",
             CREATED_BY: "human"},
            {"ID": "PRE-0002", "Назва": "Спір з вендором — LogiTrans",
             "Категорія": "1.1 Договірні", "Юрисдикція": "EU",
             "Перевірений локалом": "TRUE", OWNER_COL: "Iryna",
             "Файл": L(folders["PRE-0002"]),
             SUMMARY_COL: "Спір з договору, виграний завдяки exclusive jurisdiction "
                          "clause. Підкріплений рісьорчем по юрисдикційних застереженнях.",
             STATUS_COL: "active", RELATED_COL: "RES-0002", CREATED_BY: "human"},
        ],
        "Шаблони": [
            {"ID": "TPL-0001", "Назва": "Share Purchase Agreement (capped warranties)",
             "Категорія": "1.3 Інвестиційні", "Юрисдикція": "Multi", OWNER_COL: "Iryna",
             "Файл": L(folders["Templates"]),
             SUMMARY_COL: "Каркас SPA з узгодженим warranty cap і tax-indemnity клозами. "
                          "Походить від угоди TechCorp.",
             STATUS_COL: "active", RELATED_COL: "PRE-0001, RES-0001", CREATED_BY: "human"},
            {"ID": "TPL-0002", "Назва": "Mutual NDA (білінгва)",
             "Категорія": "1.1 Договірні", "Юрисдикція": "UA", OWNER_COL: "Iryna",
             "Файл": L(folders["Templates"]),
             SUMMARY_COL: "Стандартний взаємний NDA, паралельний текст UA/EN.",
             STATUS_COL: "active", RELATED_COL: "", CREATED_BY: "human"},
        ],
        "Рісьорчі": [
            {"ID": "RES-0001", "Назва": "Чинність warranty caps (DE/UA)",
             "Питання / тригер": "Чи enforceable договірні warranty caps у share deals DE і UA?",
             "Категорія": "1.3 Інвестиційні", "Юрисдикція": "Multi",
             "Підтверджено локалом": "TRUE", OWNER_COL: "Iryna",
             "Файл": L(folders["Researches"]),
             SUMMARY_COL: "Меморандум: warranty caps чинні в обох юрисдикціях із "
                          "застереженнями про добросовісність. Підкріплює SPA-шаблон.",
             STATUS_COL: "active", RELATED_COL: "PRE-0001, TPL-0001", CREATED_BY: "human"},
            {"ID": "RES-0002", "Назва": "Exclusive jurisdiction clauses — чинність",
             "Питання / тригер": "Чи тримаються exclusive jurisdiction clauses у транскордонних B2B спорах?",
             "Категорія": "1.1 Договірні", "Юрисдикція": "EU",
             "Підтверджено локалом": "TRUE", OWNER_COL: "Iryna",
             "Файл": L(folders["Researches"]),
             SUMMARY_COL: "Меморандум на підтримку exclusive jurisdiction clauses "
                          "(Brussels Ia / Hague), застосовано у спорі LogiTrans.",
             STATUS_COL: "active", RELATED_COL: "PRE-0002", CREATED_BY: "human"},
        ],
        "Провайдери": [
            {"ID": "PRV-0001", "Назва": "Mueller & Partner (Munich)",
             "Тип послуги": "Зовнішній юрист", "Юрисдикція / регіон": "DE",
             "Контакти": "j.mueller@mp-law.de", "Поінт оф контакт": "Iryna",
             "Оцінка": "Recommended", "Партнер": "FALSE", "Папка на Drive": "",
             SUMMARY_COL: "Німецький local counsel; вів tax-indemnity драфтинг по угоді TechCorp.",
             STATUS_COL: "active", RELATED_COL: "PRE-0001", CREATED_BY: "human"},
            {"ID": "PRV-0002", "Назва": "Київська нотаріальна контора №12",
             "Тип послуги": "Нотаріус", "Юрисдикція / регіон": "UA",
             "Контакти": "+380 44 000 0000", "Поінт оф контакт": "Iryna",
             "Оцінка": "Okay", "Партнер": "FALSE", "Папка на Drive": "",
             SUMMARY_COL: "Надійне нотаріальне посвідчення корпоративних подач у Києві.",
             STATUS_COL: "active", RELATED_COL: "", CREATED_BY: "human"},
        ],
    }


# --------------------------------------------------------------------------- #
# Sheet building
# --------------------------------------------------------------------------- #
NOW = "2026-05-29 00:00"


def dict_to_row(d, columns):
    out = []
    for c in columns:
        v = d.get(c, "")
        if c in (CREATED_AT, UPDATED_AT) and not v:
            v = NOW
        out.append(v)
    return out


def main():
    gc, drive = get_clients()
    print("Building Drive tree...")
    folders = build_drive(drive)

    print("Creating spreadsheet...")
    ss = gc.create(SPREADSHEET_TITLE)
    # move spreadsheet into the KB root folder
    drive.files().update(fileId=ss.id, addParents=folders["_root"],
                         removeParents="root", fields="id, parents").execute()

    seeds = seed_rows(folders)

    # --- create worksheets in order ---
    order = [HOME] + list(TABLES.keys()) + [INBOX, TAXONOMY]
    ws = {}
    default = ss.sheet1
    default.update_title(HOME)
    ws[HOME] = default
    for name in order:
        if name == HOME:
            continue
        ws[name] = ss.add_worksheet(title=name, rows=1000, cols=30)

    fmt_requests = []

    # --- entity tables: headers + seed + styling + validation ---
    for name, spec in TABLES.items():
        cols = spec["columns"]
        rows = [cols] + [dict_to_row(d, cols) for d in seeds[name]]
        ws[name].update("A1", rows, value_input_option="RAW")
        sid = ws[name].id
        fmt_requests += style_table(sid, len(cols), len(rows))
        fmt_requests += validation_for(sid, cols)
        fmt_requests += checkbox_for(sid, cols)
        fmt_requests += hide_for(sid, cols)

    # --- Inbox ---
    ws[INBOX].update("A1", [INBOX_COLUMNS], value_input_option="RAW")
    fmt_requests += style_table(ws[INBOX].id, len(INBOX_COLUMNS), 1)
    fmt_requests += validation_for(ws[INBOX].id, INBOX_COLUMNS)

    # --- Taxonomy reference ---
    tax_cols = list(TAXONOMY_VALUES.keys())
    maxlen = max(len(v) for v in TAXONOMY_VALUES.values())
    tax_rows = [tax_cols]
    for i in range(maxlen):
        tax_rows.append([TAXONOMY_VALUES[c][i] if i < len(TAXONOMY_VALUES[c]) else ""
                         for c in tax_cols])
    ws[TAXONOMY].update("A1", tax_rows, value_input_option="RAW")
    fmt_requests += style_table(ws[TAXONOMY].id, len(tax_cols), len(tax_rows))

    # --- Home ---
    build_home(ws[HOME], ss.id, folders)
    fmt_requests += home_style(ws[HOME].id)

    print("Applying formatting + validation...")
    ss.batch_update({"requests": fmt_requests})

    cfg = {
        "spreadsheet_id": ss.id,
        "spreadsheet_url": f"https://docs.google.com/spreadsheets/d/{ss.id}",
        "folders": folders,
    }
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)

    print("\nDONE")
    print("Spreadsheet:", cfg["spreadsheet_url"])
    print("Drive root :", folder_link(folders["_root"]))
    print("Config saved:", CONFIG_PATH)


# --------------------------------------------------------------------------- #
# styling helpers (reuse brand_palette colors)
# --------------------------------------------------------------------------- #
def style_table(sid, ncols, nrows):
    reqs = []
    # header row: graphite bg, cream text, bold
    reqs.append({"repeatCell": {
        "range": {"sheetId": sid, "startRowIndex": 0, "endRowIndex": 1,
                  "startColumnIndex": 0, "endColumnIndex": ncols},
        "cell": {"userEnteredFormat": {
            "backgroundColor": bp.GRAPHITE,
            "textFormat": {"bold": True, "foregroundColor": bp.CREAM,
                           "fontSize": 10, "fontFamily": "Inter"},
            "verticalAlignment": "MIDDLE",
            "padding": {"left": 8, "top": 4, "bottom": 4, "right": 4}}},
        "fields": "userEnteredFormat(backgroundColor,textFormat,verticalAlignment,padding)"}})
    # body: cream bg, wrap, top align
    if nrows > 1:
        reqs.append({"repeatCell": {
            "range": {"sheetId": sid, "startRowIndex": 1, "endRowIndex": nrows,
                      "startColumnIndex": 0, "endColumnIndex": ncols},
            "cell": {"userEnteredFormat": {
                "backgroundColor": bp.CREAM, "wrapStrategy": "WRAP",
                "verticalAlignment": "TOP",
                "textFormat": {"fontSize": 10, "fontFamily": "Inter",
                               "foregroundColor": bp.TEXT}}},
            "fields": "userEnteredFormat(backgroundColor,wrapStrategy,verticalAlignment,textFormat)"}})
    # freeze header + first column
    reqs.append({"updateSheetProperties": {
        "properties": {"sheetId": sid,
                       "gridProperties": {"frozenRowCount": 1, "frozenColumnCount": 1}},
        "fields": "gridProperties(frozenRowCount,frozenColumnCount)"}})
    # ID + key text columns widths
    reqs.append({"updateDimensionProperties": {
        "range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 1},
        "properties": {"pixelSize": 90}, "fields": "pixelSize"}})
    reqs.append({"updateDimensionProperties": {
        "range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": 1, "endIndex": 2},
        "properties": {"pixelSize": 260}, "fields": "pixelSize"}})
    return reqs


def validation_for(sid, cols):
    from kb_schema import COLUMN_VALIDATION
    reqs = []
    for idx, c in enumerate(cols):
        key = COLUMN_VALIDATION.get(c)
        if not key:
            continue
        values = TAXONOMY_VALUES[key]
        reqs.append({"setDataValidation": {
            "range": {"sheetId": sid, "startRowIndex": 1, "endRowIndex": 1000,
                      "startColumnIndex": idx, "endColumnIndex": idx + 1},
            "rule": {
                "condition": {"type": "ONE_OF_LIST",
                              "values": [{"userEnteredValue": v} for v in values]},
                "showCustomUi": True, "strict": False}}})
    return reqs


def checkbox_for(sid, cols):
    reqs = []
    for idx, c in enumerate(cols):
        if c in CHECKBOX_COLUMNS:
            # scope to a working buffer (BOOLEAN validation fills FALSE on every row in range)
            reqs.append({"setDataValidation": {
                "range": {"sheetId": sid, "startRowIndex": 1, "endRowIndex": 50,
                          "startColumnIndex": idx, "endColumnIndex": idx + 1},
                "rule": {"condition": {"type": "BOOLEAN"}}}})
    return reqs


def hide_for(sid, cols):
    reqs = []
    for idx, c in enumerate(cols):
        if c in HIDDEN_COLUMNS:
            reqs.append({"updateDimensionProperties": {
                "range": {"sheetId": sid, "dimension": "COLUMNS",
                          "startIndex": idx, "endIndex": idx + 1},
                "properties": {"hiddenByUser": True}, "fields": "hiddenByUser"}})
    return reqs


def home_style(sid):
    return [
        bp.title_row_req(sid, 0, 2),
        bp.subtitle_row_req(sid, 1, 2),
        {"updateDimensionProperties": {
            "range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 1},
            "properties": {"pixelSize": 720}, "fields": "pixelSize"}},
        {"updateSheetProperties": {
            "properties": {"sheetId": sid, "gridProperties": {"frozenRowCount": 2}},
            "fields": "gridProperties(frozenRowCount)"}},
    ]


def build_home(ws, ssid, folders):
    lines = [
        ["X-ON-X Knowledge Base"],
        ["Юридичне ноу-хау, рісьорчі та провайдери. Для людей і AI-агентів."],
        [""],
        ["СТРУКТУРА — 3 полиці / 4 типи карток"],
        ["1. Документи: Прецеденти (PRE-) + Шаблони (TPL-)"],
        ["2. Рісьорчі: Researches (RES-)"],
        ["3. Провайдери: Providers (PRV-)"],
        [""],
        ["ЗВʼЯЗКИ — peer-to-peer"],
        ["Кожна картка має колонку «Звʼязки» = список ID (напр. PRE-0001, RES-0002)."],
        ["KB-API тримає звʼязки двосторонніми."],
        [""],
        ["НАПОВНЕННЯ — через вкладку Inbox"],
        ["Людина кидає в Inbox те, що варто. Сортувальник (AI) розбирає і заповнює поля."],
        ["Сумнівне лишається зі статусом «needs-review», поки сеньйор не гляне."],
        [""],
        ["СТАТУСИ"],
        ["active — у бібліотеці; pending-PII — чекає на анонімізацію; needs-review — на перевірку."],
        ["AI і джуни бачать лише active (чисте ядро)."],
        [""],
        ["СЛУЖБОВІ ПОЛЯ ДЛЯ AI"],
        ["Опис + ключові слова — це читає пошук і AI. Embedding — вектор для пошуку за змістом."],
        [""],
        ["ДОСТУП — kb_api.py (Python, gspread + Drive)"],
        ["search(query, table=None)  — знайти картки за текстом"],
        ["get(id)                     — картка + повʼязані картки"],
        ["propose(table, fields, ...) — чернетка в Inbox"],
        ["promote(temp_id, reviewer)  — Inbox → таблиця, реальний ID"],
        ["link(id_a, id_b)            — двосторонній звʼязок"],
        ["update(id, fields)          — редагувати картку"],
        [""],
        ["_Taxonomy = контрольований словник (категорії, юрисдикції, статуси...). Дропдауни його тримають."],
        ["Drive root: " + folder_link(folders["_root"])],
    ]
    ws.update("A1", lines, value_input_option="RAW")


if __name__ == "__main__":
    main()
