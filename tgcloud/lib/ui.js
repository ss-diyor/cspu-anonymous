export const welcomeText = `<b>CSPU Anonymous</b>\n\nAnonim xabar yuborish uchun tugmani bosing.`;

export const privacyText = `<b>Maxfiylik</b>\n\nXabar kanalga anonim tarzda yuboriladi. Moderatorlarga muallifning ismi yoki username’i ko‘rsatilmaydi. Texnik jihatdan Telegram foydalanuvchi ID’si bot bazasida saqlanadi.`;

export function mainMenu() {
  return {
    inline_keyboard: [
      [{ text: '✍️ Anonim xabar yuborish', callback_data: 'user:new' }],
      [{ text: 'ℹ️ Qoidalar va maxfiylik', callback_data: 'user:privacy' }],
    ],
  };
}

export function categoryMenu(categories) {
  return {
    inline_keyboard: [
      ...categories.map((category) => [{
        text: `${category.emoji} ${category.title}`,
        callback_data: `category:${category.id}`,
      }]),
      [{ text: '❌ Bekor qilish', callback_data: 'user:cancel' }],
    ],
  };
}

export function previewMenu() {
  return {
    inline_keyboard: [
      [{ text: '✅ Moderatsiyaga yuborish', callback_data: 'draft:submit' }],
      [{ text: '🔄 Qayta yozish', callback_data: 'draft:rewrite' }],
      [{ text: '❌ Bekor qilish', callback_data: 'user:cancel' }],
    ],
  };
}

export function moderationMenu(id) {
  return {
    inline_keyboard: [[
      { text: '✅ Tasdiqlash', callback_data: `moderation:approve:${id}` },
      { text: '❌ Rad etish', callback_data: `moderation:reject:${id}` },
    ]],
  };
}
