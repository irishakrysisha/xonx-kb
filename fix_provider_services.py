"""Почистити колонку «Послуги» у Провайдерах — там був дамп із 30–46 ключових слів
в одній комірці (нечитабельно). Робимо короткий згрупований людський перелік;
повний набір ключових слів зберігаємо у прихованому «Опис» (пошук/AI бачать усе).

    python3 fix_provider_services.py
"""
from kb_api import KB

# короткий людський перелік основних послуг (через · )
CONCISE = {
    "Corplex": ("Реєстрація компаній (mainland / free zone / offshore) · ліцензування · "
                "візи та резиденція · банківські рахунки · бухгалтерія і податки · "
                "корпоративне структурування · M&A · легалізація документів"),
    "Notarity": ("Онлайн-нотаризація · посвідчення підписів · довіреності · "
                 "корпоративні документи · засвідчені копії · апостиль і легалізація · "
                 "нотаризація для реєстрації компаній"),
    "TotalPro": ("Реєстрація та адміністрування компаній (Кіпр) · номінальний сервіс · "
                 "бухгалтерія та аудит · податки / ПДВ · банківські рахунки · "
                 "інвестфонди / CIF · віртуальний офіс"),
    "Magrat": ("Бухгалтерія та аудит · податки (ПДВ, звітність) · нарахування зарплати · "
               "реєстрація компаній (Естонія) · e-Residency · юридична адреса / "
               "контактна особа · ліцензії (crypto / fintech)"),
}


def main():
    kb = KB()
    ws = kb.ss.worksheet("Провайдери")
    v = ws.get_all_values()
    h = v[0]
    cs, co = h.index("Послуги"), h.index("Опис")
    updates = []
    for ri, row in enumerate(v[1:], start=2):
        name = row[1].strip()
        if name not in CONCISE:
            continue
        full = row[cs].strip()
        desc = row[co].strip()
        # повні ключові слова → у кінець опису (один раз)
        new_desc = desc
        if full and "Ключові слова:" not in desc:
            new_desc = (desc + (" " if desc and not desc.endswith(".") else " ")
                        + "Ключові слова: " + full).strip()
        updates.append({"range": f"Провайдери!{_a1(ri, cs + 1)}",
                        "values": [[CONCISE[name]]]})
        updates.append({"range": f"Провайдери!{_a1(ri, co + 1)}",
                        "values": [[new_desc]]})
        print(f"{name}: Послуги {len(full)}→{len(CONCISE[name])} симв.; ключові слова збережено в Опис")
    if updates:
        kb.ss.values_batch_update({"valueInputOption": "RAW", "data": updates})
    print("DONE — далі: python3 kb_polish.py")


def _a1(row, col):
    s = ""
    while col:
        col, r = divmod(col - 1, 26)
        s = chr(65 + r) + s
    return f"{s}{row}"


if __name__ == "__main__":
    main()
