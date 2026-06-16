"""Раннер для розкладу (раз на день):
  1) розібрати нові файли з Drive _Inbox → чернетки в Inbox-вкладку;
  2) перенести в каталог усі чернетки, які людина позначила «ОК»
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

    # 2) схвалені людиною чернетки → каталог
    promoted = s.kb.promote_approved()
    print(f"[kb] схвалених перенесено в каталог: {len(promoted)}")
    for tid, result in promoted:
        print(f"  {tid} -> {result}")


if __name__ == "__main__":
    main()
