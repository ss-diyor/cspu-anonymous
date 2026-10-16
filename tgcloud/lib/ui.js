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

export function previewMenu(kind = 'submission') {
  const comment = kind === 'comment';
  return {
    inline_keyboard: [
      [{ text: comment ? '✅ Anonim yuborish' : '✅ Moderatsiyaga yuborish', callback_data: comment ? 'comment:submit' : 'draft:submit' }],
      [{ text: '🔄 Qayta yozish', callback_data: comment ? 'comment:rewrite' : 'draft:rewrite' }],
      [{ text: '❌ Bekor qilish', callback_data: 'user:cancel' }],
    ],
  };
}

export function moderationMenu(id, kind = 'submission') {
  const prefix = kind === 'reply' ? 'reply' : 'moderation';
  return {
    inline_keyboard: [[
      { text: '✅ Tasdiqlash', callback_data: `${prefix}:approve:${id}` },
      { text: '❌ Rad etish', callback_data: `${prefix}:reject:${id}` },
    ]],
  };
}

export function anonymousCommentButton(botUsername, commentToken) {
  return {
    inline_keyboard: [[{
      text: '✍️ Anonim javob yozish',
      url: `https://t.me/${botUsername.replace(/^@/, '')}?start=comment_${commentToken}`,
    }]],
  };
}
