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

## Yangi bot qo'shish

1. `bots/yangi_bot/` papkasini yarating (kitobxon strukturasini nusxalang)
2. `core/config.py` ga token va webhook path qo'shing
3. `main.py` ga `registry.register(...)` qo'shing
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
