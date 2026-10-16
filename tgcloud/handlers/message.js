import { api, db } from 'sdk';
import { eq } from 'sdk/db';
import { submissions, users } from '../schema.js';
import { config, escapeHtml } from '../lib/config.js';
import { getSession, ensureUser, setSession, clearSession } from '../lib/store.js';
import { anonymousCommentButton, mainMenu, previewMenu, welcomeText } from '../lib/ui.js';

function privateChat(message) {
  return message.chat?.type === 'private' && message.from?.id;
}

function isDiscussionForward(message) {
  return message.is_automatic_forward === true
    && message.chat?.id === config.discussionChatId;
}

async function botUsername() {
  if (config.botUsername) return config.botUsername.replace(/^@/, '');
  const me = await api.getMe();
  if (!me.username) throw new Error('Bot username is required for anonymous comment links');
  return me.username;
}

async function attachAnonymousCommentButton(message) {
  const origin = message.forward_origin;
  const channelMessageId = origin?.message_id;
  const originChatId = origin?.chat?.id;
  if (!channelMessageId || originChatId !== config.channelId) return;

  const submission = await db.select().from(submissions)
    .where(eq(submissions.channelMessageId, channelMessageId)).get();
  if (!submission || submission.status !== 'published' || submission.discussionMessageId) return;

  await db.update(submissions)
    .set({ discussionMessageId: message.message_id })
    .where(eq(submissions.id, submission.id)).run();

  await api.sendMessage({
    chat_id: config.discussionChatId,
    text: 'Bu postga shaxsingizni ko‘rsatmasdan javob qoldirishingiz mumkin.',
    reply_parameters: { message_id: message.message_id },
    reply_markup: anonymousCommentButton(await botUsername(), submission.commentToken),
    disable_notification: true,
  });
}

async function startDeepLink(userId, payload) {
  if (!payload?.startsWith('comment_')) return false;
  const token = payload.slice('comment_'.length);
  const submission = await db.select().from(submissions)
    .where(eq(submissions.commentToken, token)).get();
  if (!submission || submission.status !== 'published' || !submission.discussionMessageId) {
    await api.sendMessage({ chat_id: userId, text: 'Bu postga anonim javob berish havolasi faol emas.' });
    return true;
  }

  await setSession(userId, 'awaiting_comment', { submissionId: submission.id });
  await api.sendMessage({
    chat_id: userId,
    text: `#${submission.id}-postga anonim javobingizni matn ko‘rinishida yuboring.\n\nBekor qilish: /cancel`,
  });
  return true;
}

export default async function (message) {
  if (isDiscussionForward(message)) {
    await attachAnonymousCommentButton(message);
    return;
  }
  if (!privateChat(message)) return;

  const userId = message.from.id;
  await ensureUser(userId);
  const text = message.text?.trim() ?? '';
  const start = text.match(/^\/start(?:\s+(\S+))?$/);

  if (start) {
    await clearSession(userId);
    if (await startDeepLink(userId, start[1])) return;
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
  if (!session || !['awaiting_submission', 'awaiting_comment'].includes(session.state)) {
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

  const isComment = session.state === 'awaiting_comment';
  await setSession(userId, isComment ? 'preview_comment' : 'preview_submission', {
    ...(isComment ? { submissionId: session.payload.submissionId } : { categoryId: session.payload.categoryId }),
    text,
  });

  await api.sendMessage({
    chat_id: userId,
    text: `<b>Preview</b>\n\n${escapeHtml(text)}\n\nYuborishni tasdiqlang:`,
    parse_mode: 'HTML',
    reply_markup: previewMenu(isComment ? 'comment' : 'submission'),
  });
}
