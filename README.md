# kbot_and_test_solve

FastAPI + SQLAlchemy async multi-bot platform. Clean Architecture: Handlers → Services → Repositories → Models.

## Setup

```bash
cd /home/ilyos/bots/kbot_and_test_solve
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# .env ni to'ldiring
nano .env
```

## Database

```bash
# 1. PostgreSQL da yangi DB yarating
createdb kbot_new_db

# 2. Migratsiya ishga tushiring
alembic upgrade head

# 3. Birinchi admin qo'shing (botga /start bosib keyin DB da is_admin=true qiling)
psql kbot_new_db -c "UPDATE kitobxon_users SET is_admin=true WHERE telegram_id=935795577;"
```

## Ishga tushirish

### Webhook rejimi (asosiy)

```bash
# Bir martalik — servis faylini o'rnating
sudo cp deploy/kbot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable kbot
sudo systemctl start kbot
sudo systemctl status kbot

# Loglar
sudo journalctl -u kbot -f
```

Eslatma: webhook rejimida `aiogram` FSM `MemoryStorage` bilan ishlayotgani uchun servis `1 worker` bilan ko'tarilishi kerak. Aks holda `Userlarni import`, kanal qo'shish, savol qo'shish kabi state'li oqimlar workerlar orasida yo'qolib qolishi mumkin.

### Botlarni alohida rejimda boshqarish

Har bir bot uchun `.env` da mode berish mumkin:

```bash
KITOBXON_MODE=webhook
KITOBMILLATBOT_MODE=webhook
MILLATCHIROQLARIBOT_MODE=webhook
```

Ruxsat etilgan qiymatlar:

- `webhook` — `main.py` startup vaqtida webhook set qiladi
- `polling` — `main.py` bu botni webhookka qo'shmaydi
- `disabled` — vaqtincha o'chirib qo'yadi

Mode'larni bitta komanda bilan almashtirish:

```bash
python3 manage_bot_modes.py kitobmillatbot=webhook kitobxon=polling millatchiroqlaribot=polling
```

Joriy holatni ko'rish:

```bash
python3 manage_bot_modes.py show
```

### Polling fallback (konkurs paytida webhook qotganda)

```bash
# Avval webhook servisi to'xtatiladi
sudo systemctl stop kbot

# Keyin polling ishga tushiriladi
source venv/bin/activate
python main_polling.py

# Qayta webhook rejimga o'tish
# Ctrl+C bilan polling to'xtatiladi
sudo systemctl start kbot
```

`MODE=polling` deb belgilangan barcha botlarni birga ishga tushirish:

```bash
source venv/bin/activate
python3 main_polling_selected.py
```

## Reklama yuborish (broadcast)

Dvigatel: [`core/broadcast.py`](core/broadcast.py). Har bir rassilka bazada
"job" sifatida saqlanadi, shuning uchun:

- **Restart rassilkani o'ldirmaydi.** Job `cursor_id` bilan yuriladi; servis
  qayta ishga tushganda tugallanmagan joblar avtomatik davom etadi (webhook
  uchun `main.py` lifespan, polling uchun har bir `main_polling_*.py`).
- **Hamma foydalanuvchi oladi — hech qanday filtr yo'q.** Na `is_registered`,
  na `is_blocked` hisobga olinadi. `users` jadvalidagi har bir qatorga uriniladi.
- `users.is_blocked` — faqat hisobot uchun: 403 qaytargan foydalanuvchi
  belgilanadi, `/start` bosilsa tozalanadi. Yuborishga ta'sir qilmaydi
  (blok olib tashlangan bo'lishi mumkin).
- **Yetib bormaganlar yozib boriladi** — `<prefix>_broadcast_failures`.
  Hisobot ostidagi "🔁 Yetib bormaganlarga qayta yuborish" tugmasi faqat
  o'shalarga yangi job ochadi.
- Rassilka fon workerida ishlaydi, DB sessiyasi ushlab turilmaydi. Bir botda
  bir vaqtda bitta job ishlaydi (navbat), Telegram flood limitiga urilmaslik uchun.

### Polling rejimida to'xtatish

Rassilka fon worker'ida ketadi, shuning uchun har bir kirish nuqtasi chiqishda
`engine.pause()` chaqiradi:

| Qanday to'xtatilsa | Nima bo'ladi |
|---|---|
| **Ctrl+C** (terminal) | `finally` ishlaydi → job `pending` bo'lib saqlanadi, qulf bo'shatiladi. Keyingi ishga tushirishda **darhol** o'sha joydan davom etadi, dublikatsiz. |
| **`kill`** (SIGTERM) yoki **`kill -9`** | Jarayon darhol o'ladi, `finally` ishlamaydi. Kursor oxirgi checkpoint'da qoladi → keyingi start davom ettiradi, **hech kim tushib qolmaydi**, ko'pi bilan ~20 kishiga takror ketishi mumkin. |

O'lik jarayonning qulfi keyingi startda avtomatik tortib olinadi (pid tirikligi
tekshiriladi), shuning uchun qayta ishga tushirishdan oldin kutish shart emas.

⚠️ **Webhook va pollingni bir vaqtda ishlatmang.** Ikkalasi bitta bazaga
ulanadi, shuning uchun `broadcast_jobs.locked_by/locked_at` qulfi qo'yilgan:
jobni faqat bitta jarayon yuboradi, ikkinchisi "owned by another process"
deb logga yozib, tegmaydi. Bu xavfsizlik to'ri, ish tartibi emas — polling
oldidan har doim `sudo systemctl stop kbot` qiling.

```sql
-- Oxirgi rassilkalar holati
SELECT id, status, total, sent, failed, skipped_blocked, cursor_id, started_at, finished_at
FROM kitobmillatbot_broadcast_jobs ORDER BY id DESC LIMIT 10;

-- Falon jobda kimga bormadi va nega
SELECT telegram_id, reason, detail FROM kitobmillatbot_broadcast_failures WHERE job_id = 42;
```

Tezlikni sozlash: `BroadcastEngine.SEND_DELAY` (standart 50 ms). Amaldagi
tezlik Telegram API javob vaqti bilan cheklanadi — taxminan 3–7 xabar/sek.

## Yangi bot qo'shish

1. `bots/yangi_bot/` papkasini yarating (kitobxon strukturasini nusxalang)
2. `core/config.py` ga token va webhook path qo'shing
3. `main.py` ga `registry.register(...)` va `BROADCAST_ENGINES` ga yozuv qo'shing
4. Migratsiya: `alembic revision --autogenerate -m "add yangi_bot tables"`
5. `alembic upgrade head`
6. `sudo systemctl restart kbot`

## Nginx config (HTTPS)

```nginx
server {
    listen 443 ssl;
    server_name sizningserver.com;

    ssl_certificate /etc/letsencrypt/live/sizningserver.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/sizningserver.com/privkey.pem;

    location /kitobxon/webhook {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Telegram-Bot-Api-Secret-Token $http_x_telegram_bot_api_secret_token;
    }

    location /health {
        proxy_pass http://127.0.0.1:8001;
    }
}
```

## Fayl tuzilmasi

```
kbot_and_test_solve/
├── main.py                  # FastAPI webhook (asosiy)
├── main_polling.py          # Polling fallback
├── core/                    # Umumiy infratuzilma
│   ├── config.py            # Pydantic Settings
│   ├── database.py          # Async engine + session
│   ├── base_model.py        # SQLAlchemy Base + TimestampMixin
│   ├── middleware.py        # DB session per-update
│   ├── registry.py          # Multi-bot registry
│   └── logging.py
└── bots/
    └── kitobxon/
        ├── models.py        # SQLAlchemy 2.0 modellari
        ├── states.py        # FSM states
        ├── exceptions.py    # Domain exceptions
        ├── keyboards/       # reply.py, inline.py
        ├── repositories/    # BaseRepository + ixtisoslashganlar
        ├── services/        # Barcha biznes logika
        ├── handlers/        # aiogram Router'lar
        └── utils/           # certificate.py, excel.py
```
