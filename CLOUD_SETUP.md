# Хмарна рутіна для авто-обробки Inbox — сетап

Мета: щоб файли, кинуті в Drive-папку `_Inbox`, **автоматично** розкладались
у вкладку Inbox за розкладом, без увімкненого компʼютера.

Хмарний агент Anthropic не має ні твого OAuth-токена, ні локальних файлів, ні
сховища секретів. Тому потрібні 2 разові кроки з твого боку. Код уже готовий
працювати в обох режимах (локально — твій токен; у хмарі — service account).

---

## Крок 1. Google service account (headless-доступ)

1. https://console.cloud.google.com → створи проект (або візьми наявний).
2. APIs & Services → Enable APIs → увімкни **Google Sheets API** і **Google Drive API**.
3. IAM & Admin → Service Accounts → **Create service account** (напр. `kb-bot`).
4. У створеного SA → Keys → **Add key → JSON** → завантаж файл. Це і є ключ.
5. Скопіюй email сервіс-акаунта (вигляд `kb-bot@PROJECT.iam.gserviceaccount.com`).
6. **Розшар цьому email** (як Editor):
   - спредшит KB (Share у Google Sheets),
   - папку `_Inbox` на Shared Drive (Share у Drive). Для Shared Drive — додай
     SA членом drive або розшар саме папку.

> Обмеж SA лише цими обʼєктами — він не повинен мати зайвого доступу.

## Крок 2. Приватний GitHub-репо з кодом

1. Створи **приватний** репозиторій (напр. `xonx-kb`).
2. Заллий туди вміст `/Users/user/Claude/knowledge_base/` **плюс** JSON-ключ
   із кроку 1 під іменем `kb_sa.json` (поряд з `kb_client.py`).
   - Репо приватний → ключ не публічний. Це єдиний спосіб віддати креди хмарі
     (рутіни не мають секрет-сховища). Якщо ключ колись витече — відклич його
     в Google Cloud і згенеруй новий.
3. (`brand_palette.py` лежить у `../sheets/` — поклади його копію поряд або
   прибери залежність; для рутіни потрібен лише для `kb_polish`, не для
   `run_inbox`, тож можна не тягнути.)

---

## Крок 3. Рутіна (це роблю я)

Коли кроки 1–2 готові — даю Claude створити рутіну:
- клонує репо,
- `python3 -m pip install -r requirements.txt`,
- `python3 run_inbox.py` (читає `kb_sa.json` автоматично через `kb_client`).
- розклад: щогодини (мін. інтервал рутіни — 1 год).

Перевірка локально (працює вже зараз, твоїм токеном):
```
cd /Users/user/Claude/knowledge_base && python3 run_inbox.py
```
