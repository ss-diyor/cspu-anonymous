# Production xavfsizlik ro‘yxati

## Railway

1. `BOT_TOKEN`, `WEBHOOK_SECRET` va database credential qiymatlarini **Seal** qiling.
2. Bot servisidagi `DATABASE_URL` PostgreSQL reference variable bo‘lsin; public TCP URL
   ni qo‘lda yozmang.
3. PostgreSQL service uchun Daily va Weekly backup’larni yoqing.
4. Har oy test muhitiga restore qilib backup ishlashini tekshiring.
5. Production va staging’ni alohida Railway environment sifatida saqlang.
6. Faqat bot servisida public domain bo‘lsin; PostgreSQL’ga public TCP proxy kerak emas.
7. Usage/billing ogohlantirishlari va deploy failure bildirishnomalarini yoqing.

## Telegram va administratorlar

1. BotFather tokeni faqat Railway’da saqlansin.
2. Barcha moderatorlar Telegram Two-Step Verification’ni yoqsin.
3. `moderator` faqat tasdiqlash/rad etish uchun ishlatiladi.
4. `senior_moderator` bloklash vakolatiga ega.
5. Faqat `superadmin` rejim, filtr, kategoriya va adminlarni o‘zgartiradi.
6. Ketgan xodimning vakolatini darhol olib tashlang va zarur bo‘lsa tokenlarni almashtiring.

## GitHub

Repository Settings → Code security bo‘limida Dependabot alerts, secret scanning va
CodeQL’ni yoqing. `main` uchun branch protection qo‘yib, CI muvaffaqiyatli tugamasdan
merge qilishni taqiqlang.

## Hodisaga javob

Token yoki database credential sizib chiqsa:

1. credential’ni darhol revoke/rotate qiling;
2. Railway deploy’ni yangilang;
3. Telegram webhook’ni yangi secret bilan qayta o‘rnating;
4. audit, Railway va GitHub loglarini tekshiring;
5. zarar ko‘rgan ma’lumotlar doirasini aniqlang;
6. hodisa va ko‘rilgan choralarni ichki jurnalga yozing.
