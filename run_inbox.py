"""Раннер для розкладу (раз на день):
  1) розібрати нові файли з Drive _Inbox → чернетки в Inbox-вкладку
     (впевнені одразу летять у каталог — авто-promote усередині intake);
  2) safety-net: підібрати впевнені чернетки, що лишились pending;
  3) перенести в каталог усі чернетки, які людина позначила «ОК»
     (Статус ревʼю = approved/ок) у вкладці Inbox.
Логує підсумок.
"""
import warnings
warnings.filterwarnings("ignore")

from kb_sortuvalnyk import Sortuvalnyk


def main():
    s = Sortuvalnyk()

    # 1) нові кинуті файли → чернетки
    res = s.process_inbox()
    print(f"[kb] нових файлів оброблено: {len(res)}")
    for name, tid, info in res:
        print(f"  {name} -> {tid} | {info}")

    # 2) safety-net: впевнені чернетки, що лишились pending → каталог
    from kb_sortuvalnyk import AUTOPROMOTE_CONF
    auto = s.kb.promote_confident(threshold=AUTOPROMOTE_CONF)
    print(f"[kb] авто-перенесено впевнених (>= {AUTOPROMOTE_CONF}): {len(auto)}")
    for tid, result in auto:
        print(f"  {tid} -> {result}")

    # 3) схвалені людиною чернетки → каталог
    promoted = s.kb.promote_approved()
    print(f"[kb] схвалених перенесено в каталог: {len(promoted)}")
    for tid, result in promoted:
        print(f"  {tid} -> {result}")


if __name__ == "__main__":
    main()
