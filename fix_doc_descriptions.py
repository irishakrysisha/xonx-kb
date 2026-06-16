"""Переписати «дебільні» авто-описи/ключові слова по документах на людські.

Старі описи були сирим дампом (шапка PDF / повтор питання). Тут — чисті
1–2-реченнєві описи + осмислені ключові слова, плюс виправлені поля
(Категорія/Юрисдикція/Тип документа/Форма), які класифікатор колись вгадав хибно.

    python3 fix_doc_descriptions.py
"""
from kb_api import KB

# {таблиця: {ID: {колонка: значення}}}
FIXES = {
    "Шаблони": {
        "TPL-0001": {
            "Категорія": "Трудові / HR",
            "Тип документа": "Amendment / дод. угода",
            "Юрисдикція": "UK",
            "Опис": ("Шаблон угоди про зміну умов трудового договору (deed of variation) "
                     "за правом Англії та Уельсу. Ключові слова: трудовий договір, "
                     "зміна умов, deed of variation, employment contract, variation, UK."),
        },
    },
    "Рісьорчі": {
        "RES-0001": {
            "Форма": "Меморандум",
            "Питання / тригер": ("Як на практиці застосовувати конвенції про уникнення "
                                 "подвійного оподаткування?"),
            "Опис": ("Аналіз умов і порядку застосування конвенцій про уникнення "
                     "подвійного оподаткування. Ключові слова: подвійне оподаткування, "
                     "DTT, конвенція, резидентність, withholding tax, міжнародне "
                     "оподаткування."),
        },
        "RES-0002": {
            "Форма": "Q&A",
            "Опис": ("Чи може ФОП 3-ї групи надавати IT-послуги нерезиденту з ЄС і "
                     "отримувати валютну оплату без втрати спрощеної системи. Ключові "
                     "слова: ФОП, єдиний податок, 3 група, IT-послуги, нерезидент ЄС, "
                     "валютна виручка, ЗЕД, спрощена система."),
        },
    },
}


def main():
    kb = KB()
    updates = []
    for table, rows in FIXES.items():
        ws = kb.ss.worksheet(table)
        v = ws.get_all_values()
        h = v[0]
        idx = {r[0]: ri for ri, r in enumerate(v[1:], start=2)}
        for rid, fields in rows.items():
            if rid not in idx:
                print(f"!! {rid} не знайдено в {table}")
                continue
            ri = idx[rid]
            for col, val in fields.items():
                updates.append({"range": f"{table}!{_a1(ri, h.index(col) + 1)}",
                                "values": [[val]]})
            print(f"{table}/{rid}: оновлено {list(fields)}")
    if updates:
        kb.ss.values_batch_update({"valueInputOption": "RAW", "data": updates})
    print("DONE")


def _a1(row, col):
    s = ""
    while col:
        col, r = divmod(col - 1, 26)
        s = chr(65 + r) + s
    return f"{s}{row}"


if __name__ == "__main__":
    main()
