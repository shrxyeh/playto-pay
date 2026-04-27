# Payout Engine

Production-grade payout system for Indian merchants built with Django, PostgreSQL, and Celery.

## Quick Start

```bash
cp backend/.env.example backend/.env
docker-compose up --build
# In a separate terminal, after the backend is healthy:
docker-compose exec backend python manage.py seed
```

Backend: http://localhost:8000  
Frontend: http://localhost:3000

## Manual Setup (without Docker)

```bash
# Backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill in DB/Redis credentials

python manage.py migrate
python manage.py seed       # creates 3 merchants with credit history
python manage.py runserver

# Worker (separate terminal)
celery -A config worker -l info

# Beat scheduler (separate terminal)
celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

## API Reference

All requests require `X-Merchant-Id: <uuid>` header.

### Create Merchant (test helper)
```
POST /api/v1/merchants
{"name": "Acme", "email": "acme@example.com"}
```

### Add Credit (test helper)
```
POST /api/v1/credits
X-Merchant-Id: <uuid>
{"amount_paise": 100000}
```

### Request Payout
```
POST /api/v1/payouts
X-Merchant-Id: <uuid>
Idempotency-Key: <uuid>
{"amount_paise": 50000, "bank_account_id": "HDFC-001"}
```

### List Payouts
```
GET /api/v1/payouts
X-Merchant-Id: <uuid>
```

### Get Balance
```
GET /api/v1/balance
X-Merchant-Id: <uuid>
```

### Get Ledger History
```
GET /api/v1/ledger
X-Merchant-Id: <uuid>
```

## Seed Data

`python manage.py seed` creates three merchants with pre-loaded credit history:

| Merchant | Email | Seeded Balance |
|---|---|---|
| Priya Designs | priya@designs.in | ₹5,200 |
| Kiran Dev Studio | kiran@devstudio.in | ₹11,250 |
| Ananya Translations | ananya@translations.in | ₹1,350 |

To get a merchant's UUID for the dashboard, use the admin at `/admin/` or:
```bash
python manage.py shell -c "from merchants.models import Merchant; [print(m.id, m.name) for m in Merchant.objects.all()]"
```

Re-run with `--reset` to wipe and re-seed: `python manage.py seed --reset`

## Running Tests

```bash
cd backend
python manage.py test tests --verbosity=2
```

Requires a running PostgreSQL instance (tests use `TransactionTestCase` which hits the real DB).

## Architecture

See [EXPLAINER.md](EXPLAINER.md) for detailed design decisions.
