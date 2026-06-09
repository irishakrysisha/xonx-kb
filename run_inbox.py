"""Раннер для розкладу: обробити Drive _Inbox → Inbox-вкладку. Логує підсумок."""
import warnings
warnings.filterwarnings("ignore")

from kb_sortuvalnyk import Sortuvalnyk


def main():
    res = Sortuvalnyk().process_inbox()
    print(f"[kb] оброблено файлів: {len(res)}")
    for name, tid, info in res:
        print(f"  {name} -> {tid} | {info}")


if __name__ == "__main__":
    main()
