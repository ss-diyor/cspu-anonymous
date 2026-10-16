# Telegram Serverless MVP

Bu branch faqat CSPU Anonymous botning text-only anonim xabar oqimini ko‘chiradi:

1. Foydalanuvchi kategoriya tanlaydi.
2. Matn yuboradi va preview ko‘radi.
3. Xabar moderatorlar guruhiga anonim yuboriladi.
4. Moderator tasdiqlasa, xabar kanalga chiqadi.
5. Rad etilsa, foydalanuvchiga xabar beriladi.

## Sozlash

`tgcloud/lib/config.js` ichida quyidagilarni to‘ldiring:

- `channelId` — postlar chiqadigan kanal ID’si;
- `moderationChatId` — moderatorlar guruhi ID’si;
- `superadminIds` — tasdiqlash/rad etish huquqiga ega moderator Telegram ID’lari.

Bot Serverless’da ishlashi uchun BotFather → bot → **Serverless** bo‘limidan Serverless’ni yoqing va CLI Access token oling.

```bash
npm install
npx tgcloud login
npm run check
npx tgcloud push
npx tgcloud migrate
npx tgcloud webhook sync
```

`migrate` bazani yaratadi. `push` kodni deploy qiladi. `webhook sync` handlerlar asosida webhook’ni moslaydi.

## Hozircha ataylab kiritilmagan

- media, PDF va fayllar;
- anonim kommentlar;
- murakkab admin panel;
- PostgreSQL’dan eski ma’lumotlarni import qilish;
- background retention job.

Bu funksiyalar MVP ishlashi tasdiqlangandan keyin alohida qo‘shiladi.
