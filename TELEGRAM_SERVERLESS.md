# Telegram Serverless MVP

Bu branch botning text-only anonim xabar oqimini Telegram Serverless’da ishlatadi:

1. Foydalanuvchi kategoriya tanlaydi.
2. Matn yuboradi va preview ko‘radi.
3. Xabar moderatorlar guruhiga anonim yuboriladi.
4. Moderator tasdiqlasa, kanalga `#raqam` bilan chiqadi.
5. Telegram kanalining discussion chatida bot avtomatik ravishda **✍️ Anonim javob yozish** tugmasini qo‘shadi.
6. Foydalanuvchi deep-link orqali komment matnini yuboradi.
7. Moderator tasdiqlasa, komment discussion postiga anonim reply bo‘ladi.

## Sozlash

`tgcloud/lib/config.js` ichida quyidagilarni to‘ldiring:

- `channelId` — postlar chiqadigan kanal ID’si;
- `discussionChatId` — kanalga ulangan discussion superguruh ID’si;
- `moderationChatId` — moderatorlar guruhi ID’si;
- `superadminIds` — tasdiqlash/rad etish huquqiga ega moderator Telegram ID’lari;
- `botUsername` — `@` belgisiz username; bo‘sh qoldirilsa API orqali olinadi.

Bot kanal va discussion guruhida administrator bo‘lishi kerak. Discussion guruhi kanalga ulangan bo‘lishi kerak.

```bash
npm install
npx tgcloud login
npm run check
npx tgcloud push
npx tgcloud migrate
npx tgcloud webhook sync
```

Schema o‘zgargani uchun `migrate` yangi `anonymous_replies` jadvalini ham yaratadi. Deploydan keyin yangi kanal postini test qiling: discussion chatida botning anonim reply tugmasi chiqishi kerak.

## Hozircha ataylab kiritilmagan

- media va PDF fayllar;
- murakkab admin panel;
- PostgreSQL’dan eski ma’lumotlarni import qilish;
- background retention job.
