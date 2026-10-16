import { api, db } from 'sdk';
import { eq } from 'sdk/db';
import { anonymousReplies, categories, submissions, users } from '../schema.js';
import { config, escapeHtml, isModerator } from '../lib/config.js';
import { activeCategories, clearSession, ensureUser, getSession, setSession } from '../lib/store.js';
import { categoryMenu, mainMenu, moderationMenu, privacyText } from '../lib/ui.js';

function callbackUser(callback) {
  return callback.from?.id;
}

async function answer(callback, text = '') {
  await api.answerCallbackQuery({ callback_query_id: callback.id, text });
}

async function edit(callback, text, replyMarkup = undefined) {
  if (!callback.message) return;
  await api.editMessageText({
    chat_id: callback.message.chat.id,
    message_id: callback.message.message_id,
    text,
    parse_mode: 'HTML',
    ...(replyMarkup ? { reply_markup: replyMarkup } : {}),
  });
}

async function submitComment(callback, userId, session, user) {
  const submission = await db.select().from(submissions)
    .where(eq(submissions.id, session.payload.submissionId)).get();
  if (!submission || submission.status !== 'published' || !submission.discussionMessageId) {
    return answer(callback, 'Bu postga komment yozib bo‘lmaydi.');
  }
  const [reply] = await db.insert(anonymousReplies).values({
    submissionId: submission.id,
    userId,
    text: session.payload.text,
    status: 'pending',
  }).returning().run();

  const moderationMessage = await api.sendMessage({
    chat_id: config.moderationChatId,
    text: `<b>Yangi anonim komment #${reply.id}</b>\nKanal posti: #${submission.id}\n\n${escapeHtml(reply.text)}`,
    parse_mode: 'HTML',
    reply_markup: moderationMenu(reply.id, 'reply'),
  });
  await db.update(anonymousReplies).set({ moderationMessageId: moderationMessage.message_id })
    .where(eq(anonymousReplies.id, reply.id)).run();
  await db.update(users).set({ lastActionAt: new Date() }).where(eq(users.tgId, userId)).run();
  await clearSession(userId);
  await edit(callback, `⏳ Komment #${reply.id} moderatorlarga yuborildi.`, mainMenu());
  return answer(callback, 'Komment moderatorlarga yuborildi.');
}

export default async function (callback) {
  const userId = callbackUser(callback);
  if (!userId || !callback.data) return;
  const data = callback.data;
  await ensureUser(userId);

  if (data === 'user:new') {
    const user = await db.select().from(users).where(eq(users.tgId, userId)).get();
    if (user?.isBanned) return answer(callback, 'Botdan foydalanishingiz cheklangan.');
    await clearSession(userId);
    await edit(callback, 'Xabaringiz kategoriyasini tanlang:', categoryMenu(await activeCategories()));
    return answer(callback);
  }
  if (data === 'user:privacy') {
    await edit(callback, privacyText, mainMenu());
    return answer(callback);
  }
  if (data === 'user:home' || data === 'user:cancel') {
    await clearSession(userId);
    await edit(callback, 'Amal bekor qilindi.\n\nAnonim xabar yuborish uchun tugmani bosing.', mainMenu());
    return answer(callback);
  }
  if (data.startsWith('category:')) {
    const categoryId = Number(data.slice('category:'.length));
    const category = await db.select().from(categories).where(eq(categories.id, categoryId)).get();
    if (!category?.enabled) return answer(callback, 'Bu kategoriya hozir faol emas.');
    await setSession(userId, 'awaiting_submission', { categoryId });
    await edit(callback, `${category.emoji} <b>${escapeHtml(category.title)}</b>\n\nXabaringizni matn ko‘rinishida yuboring.\n\nBekor qilish: /cancel`);
    return answer(callback);
  }

  if (data === 'draft:rewrite' || data === 'comment:rewrite') {
    const session = await getSession(userId);
    if (!session || !['preview_submission', 'preview_comment'].includes(session.state)) {
      return answer(callback, 'Jarayon muddati tugagan.');
    }
    if (session.state === 'preview_comment') {
      await setSession(userId, 'awaiting_comment', { submissionId: session.payload.submissionId });
    } else {
      await setSession(userId, 'awaiting_submission', { categoryId: session.payload.categoryId });
    }
    await edit(callback, 'Yangi matnni yuboring.\n\nBekor qilish: /cancel');
    return answer(callback);
  }

  if (data === 'draft:submit' || data === 'comment:submit') {
    const session = await getSession(userId);
    if (!session || !['preview_submission', 'preview_comment'].includes(session.state)) {
      return answer(callback, 'Xabar muddati tugagan.');
    }
    const user = await db.select().from(users).where(eq(users.tgId, userId)).get();
    if (user?.isBanned) return answer(callback, 'Botdan foydalanishingiz cheklangan.');
    if (user?.lastActionAt && Date.now() - user.lastActionAt.getTime() < config.userRateLimitSeconds * 1000) {
      return answer(callback, `Yana ${config.userRateLimitSeconds} soniya kuting.`);
    }
    if (session.state === 'preview_comment') return submitComment(callback, userId, session, user);

    const [submission] = await db.insert(submissions).values({
      userId,
      categoryId: session.payload.categoryId,
      text: session.payload.text,
      commentToken: crypto.randomUUID().replaceAll('-', ''),
      status: 'pending',
    }).returning().run();
    const category = await db.select().from(categories).where(eq(categories.id, submission.categoryId)).get();
    const moderationMessage = await api.sendMessage({
      chat_id: config.moderationChatId,
      text: `<b>Yangi anonim xabar #${submission.id}</b>\nKategoriya: ${escapeHtml(category?.emoji ?? '📝')} ${escapeHtml(category?.title ?? '')}\n\n${escapeHtml(submission.text)}`,
      parse_mode: 'HTML',
      reply_markup: moderationMenu(submission.id),
    });
    await db.update(submissions).set({ moderationMessageId: moderationMessage.message_id }).where(eq(submissions.id, submission.id)).run();
    await db.update(users).set({ lastActionAt: new Date() }).where(eq(users.tgId, userId)).run();
    await clearSession(userId);
    await edit(callback, `⏳ <b>#${submission.id}</b> xabaringiz moderatorlarga yuborildi.`, mainMenu());
    return answer(callback, 'Moderatorlarga yuborildi.');
  }

  if (data.startsWith('moderation:')) {
    if (!isModerator(userId)) return answer(callback, 'Sizda bu amal uchun huquq yo‘q.');
    const [, action, rawId] = data.split(':');
    const id = Number(rawId);
    const submission = await db.select().from(submissions).where(eq(submissions.id, id)).get();
    if (!submission || submission.status !== 'pending') return answer(callback, 'Xabar topilmadi yoki allaqachon ko‘rilgan.');
    if (action === 'reject') {
      await db.update(submissions).set({ status: 'rejected', reviewedAt: new Date() }).where(eq(submissions.id, id)).run();
      await api.sendMessage({ chat_id: submission.userId, text: `❌ #${id} xabaringiz moderatorlar tomonidan rad etildi.` });
      await edit(callback, `❌ <b>#${id}</b> rad etildi.`);
      return answer(callback, 'Xabar rad etildi.');
    }
    if (action === 'approve') {
      const category = await db.select().from(categories).where(eq(categories.id, submission.categoryId)).get();
      const posted = await api.sendMessage({
        chat_id: config.channelId,
        text: `#${submission.id}\n\n${escapeHtml(submission.text)}\n\n#${escapeHtml(category?.key ?? 'anonim')}`,
        parse_mode: 'HTML',
      });
      await db.update(submissions).set({ status: 'published', channelMessageId: posted.message_id, reviewedAt: new Date() }).where(eq(submissions.id, id)).run();
      await api.sendMessage({ chat_id: submission.userId, text: `✅ #${id} xabaringiz kanalga anonim joylandi.` });
      await edit(callback, `✅ <b>#${id}</b> kanalga joylandi.`);
      return answer(callback, 'Xabar tasdiqlandi.');
    }
  }

  if (data.startsWith('reply:')) {
    if (!isModerator(userId)) return answer(callback, 'Sizda bu amal uchun huquq yo‘q.');
    const [, action, rawId] = data.split(':');
    const id = Number(rawId);
    const reply = await db.select().from(anonymousReplies).where(eq(anonymousReplies.id, id)).get();
    if (!reply || reply.status !== 'pending') return answer(callback, 'Komment topilmadi yoki allaqachon ko‘rilgan.');
    if (action === 'reject') {
      await db.update(anonymousReplies).set({ status: 'rejected', reviewedAt: new Date() }).where(eq(anonymousReplies.id, id)).run();
      await api.sendMessage({ chat_id: reply.userId, text: `❌ Anonim komment #${id} moderatorlar tomonidan rad etildi.` });
      await edit(callback, `❌ <b>Komment #${id}</b> rad etildi.`);
      return answer(callback, 'Komment rad etildi.');
    }
    if (action === 'approve') {
      const submission = await db.select().from(submissions).where(eq(submissions.id, reply.submissionId)).get();
      if (!submission?.discussionMessageId) return answer(callback, 'Discussion posti hali tayyor emas.');
      const posted = await api.sendMessage({
        chat_id: config.discussionChatId,
        text: `${escapeHtml(reply.text)}\n\n#anonim_${reply.id}`,
        parse_mode: 'HTML',
        reply_parameters: { message_id: submission.discussionMessageId },
      });
      await db.update(anonymousReplies).set({ status: 'published', discussionMessageId: posted.message_id, reviewedAt: new Date() }).where(eq(anonymousReplies.id, id)).run();
      await api.sendMessage({ chat_id: reply.userId, text: `✅ Anonim kommentingiz #${submission.id}-postga joylandi.` });
      await edit(callback, `✅ <b>Komment #${id}</b> discussion’ga joylandi.`);
      return answer(callback, 'Komment tasdiqlandi.');
    }
  }

  return answer(callback, 'Noma’lum amal.');
}
