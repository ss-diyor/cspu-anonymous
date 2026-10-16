import { api, db } from 'sdk';
import { eq } from 'sdk/db';
import { users } from '../schema.js';
import { escapeHtml } from '../lib/config.js';
import { getSession, ensureUser, setSession, clearSession } from '../lib/store.js';
import { mainMenu, previewMenu, welcomeText } from '../lib/ui.js';

function privateChat(message) {
  return message.chat?.type === 'private' && message.from?.id;
}

export default async function (message) {
  if (!privateChat(message)) return;

  const userId = message.from.id;
  await ensureUser(userId);
  const text = message.text?.trim() ?? '';

  if (text === '/start') {
    await clearSession(userId);
    await api.sendMessage({ chat_id: userId, text: welcomeText, parse_mode: 'HTML', reply_markup: mainMenu() });
    return;
  }

  if (text === '/cancel') {
    await clearSession(userId);
    await api.sendMessage({ chat_id: userId, text: 'Amal bekor qilindi.', reply_markup: mainMenu() });
    return;
  }

  if (!text) return;

  const session = await getSession(userId);
  if (!session || session.state !== 'awaiting_submission') {
    await api.sendMessage({ chat_id: userId, text: welcomeText, parse_mode: 'HTML', reply_markup: mainMenu() });
    return;
  }

  const user = await db.select().from(users).where(eq(users.tgId, userId)).get();
  if (user?.isBanned) {
    await api.sendMessage({ chat_id: userId, text: 'Botdan foydalanishingiz cheklangan.' });
    return;
  }

  if (text.length > 3800) {
    await api.sendMessage({ chat_id: userId, text: 'Xabar 3800 belgidan oshmasligi kerak. Qaytadan yuboring.' });
    return;
  }

  await setSession(userId, 'preview_submission', {
    categoryId: session.payload.categoryId,
    text,
  });

  await api.sendMessage({
    chat_id: userId,
    text: `<b>Preview</b>\n\n${escapeHtml(text)}\n\nXabarni yuborishni tasdiqlang:`,
    parse_mode: 'HTML',
    reply_markup: previewMenu(),
  });
}
