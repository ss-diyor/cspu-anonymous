# CSPU Anonymous Bot

Chirchiq davlat pedagogika universiteti kanali uchun anonim xabar, moderatsiya va
kanal postlariga anonim komment yuborish boti.

## Imkoniyatlar

- kategoriya bilan anonim xabar yuborish;
- matn, rasm, video, hujjat, voice va animation qabul qilish;
- yuborishdan oldin preview va tasdiqlash;
- moderator, avtomatik va gibrid nashr rejimlari;
- moderator guruhida tasdiqlash, rad etish, tahrirlash va bloklash;
- moderatorning anonim muallif bilan bot orqali savol-javobi;
- kanal postining discussion kommentiga `Anonim javob yozish` deep-link tugmasi;
- anonim kommentlar uchun alohida moderatsiya rejimi;
- xabar holati, statistika, kategoriyalar, moderatorlar va bloklanganlar paneli;
- rate limit, 24 soatlik takroriy-xabar himoyasi va taqiqlangan so‘zlar filtri;
- audit jurnali va PostgreSQL’da saqlanadigan foydalanuvchi jarayonlari;
- Telegram webhook maxfiy tokeni, Docker va Railway health-check.

## Texnologiyalar

- Python 3.12
- aiogram 3
- FastAPI
- PostgreSQL + SQLAlchemy async
- Alembic
- Docker

## Telegram’ni tayyorlash

1. `@BotFather` orqali bot yarating va token oling.
2. Kanal yarating.
3. Kanalga discussion superguruhini ulang: kanal sozlamalari → **Discussion**.
4. Botni kanalga post yuborish huquqi bilan administrator qiling.
5. Botni discussion guruhiga administrator qilib qo‘shing. U xabar yubora olishi kerak.
6. Alohida yopiq moderatorlar guruhini yarating va botni administrator qiling.
7. Superadminning Telegram ID raqamini `SUPERADMIN_IDS` ga kiriting.

Kanal, discussion guruh va moderatorlar guruhi uchta alohida chat ID bo‘lishi kerak.
Superguruh va kanal ID raqamlari odatda `-100...` ko‘rinishida bo‘ladi.

## Railway deploy

### 1. PostgreSQL

Railway loyiha oynasida **New → Database → PostgreSQL** tanlang. Railway yaratgan
`DATABASE_URL` bot servisiga reference sifatida berilishi kerak.

### 2. Bot servisi

GitHub repository’ni Railway’ga ulang. Loyiha `Dockerfile` va `railway.toml` orqali
avtomatik build qilinadi.

### 3. Environment variables

`.env.example` dagi qiymatlarni Railway servisining **Variables** bo‘limiga kiriting:

| Variable | Vazifasi |
| --- | --- |
| `BOT_TOKEN` | BotFather bergan token |
| `BOT_USERNAME` | `@` belgisiz bot username’i |
| `DATABASE_URL` | Railway PostgreSQL reference’i |
| `SUPERADMIN_IDS` | Vergul bilan ajratilgan Telegram ID lar |
| `CHANNEL_ID` | Xabarlar chiqadigan kanal ID si |
| `DISCUSSION_CHAT_ID` | Kanalga ulangan discussion superguruh ID si |
| `MODERATION_CHAT_ID` | Yopiq moderatorlar guruhi ID si |
| `WEBHOOK_SECRET` | Tasodifiy, faqat `A-Z a-z 0-9 _ -` belgili maxfiy qiymat |
| `APP_MODE` | Railway uchun `webhook` |

Railway public domain yaratilganda `RAILWAY_PUBLIC_DOMAIN` avtomatik o‘qiladi. Agar
bu variable mavjud bo‘lmasa, `WEBHOOK_BASE_URL=https://sizning-domeningiz` kiriting.

`WEBHOOK_SECRET` kamida 32 ta tasodifiy belgidan iborat bo‘lsin. Uni bot tokeni bilan
bir xil qilmang.

### 4. Domain va tekshiruv

Railway servisida **Settings → Networking → Generate Domain** ni bosing. Deploy
tugagach quyidagi manzil javob berishi kerak:

```text
https://<railway-domain>/health
```

Kutilgan javob:

```json
{"status":"ok"}
```

Ilova ishga tushishda `alembic upgrade head` migratsiyasini o‘zi bajaradi va webhook’ni
Telegram’da ro‘yxatdan o‘tkazadi.

## Lokal ishga tushirish

PostgreSQL tayyorlab, `.env.example` dan `.env` yarating va:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev]"
$env:APP_MODE="polling"
.venv\Scripts\python.exe -m app.start
```

Polling rejimida public domain kerak emas, ammo `WEBHOOK_SECRET` baribir sintaktik
to‘g‘ri qiymat bo‘lishi kerak.

## Admin panel

Botning private chatida:

```text
/admin
```

Standart holatda postlar va anonim kommentlar moderator tasdig‘idan o‘tadi. Admin
paneldan `manual`, `auto` yoki `hybrid` rejimiga o‘zgartirish mumkin.

## Maxfiylik modeli

Bot xabarni `forward` qilmaydi; media `file_id` orqali va matn bot nomidan qayta
yuboriladi. Moderatorga muallifning ismi, username’i yoki Telegram ID si ko‘rsatilmaydi.

Telegram Bot API botga yozgan foydalanuvchining ID raqamini texnik ravishda beradi.
Bot javob yuborish, rate limit va bloklash uchun uni bazada saqlaydi. Shu sabab xizmat
“moderatorlar va kanal obunachilari uchun anonim” deb ta’riflanishi kerak, Telegram’ga
nisbatan mutlaq anonim deb emas. Tayyor siyosat matni:
[docs/PRIVACY_POLICY_UZ.md](docs/PRIVACY_POLICY_UZ.md).

## Xavfsizlik

- `.env` Git’ga kiritilmaydi.
- Token va parollar faqat Railway Variables’da saqlanadi.
- Webhook so‘rovlari `X-Telegram-Bot-Api-Secret-Token` orqali tekshiriladi.
- Moderator callback’lari har safar server tomonda avtorizatsiyadan o‘tadi.
- Deep-link’da ochiq post ID o‘rniga tasodifiy token ishlatiladi.
- SQL so‘rovlari SQLAlchemy parametrizatsiyasi orqali bajariladi.

Bot tokeni ochilib qolsa, darhol BotFather orqali bekor qilib yangisini yarating.

## Test va lint

```powershell
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m ruff check .
```

