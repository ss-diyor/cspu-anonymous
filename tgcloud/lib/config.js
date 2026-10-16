// Deploydan oldin quyidagi qiymatlarni Telegram chat ID’lari bilan almashtiring.
// ID’lar maxfiy token emas, ammo ularni public repository’ga chiqarmaslik tavsiya etiladi.
export const config = {
  channelId: -1000000000000,
  discussionChatId: -1000000000000,
  moderationChatId: -1000000000000,
  botUsername: '', // @ belgisiz; bo‘sh qoldirilsa api.getMe() orqali olinadi
  superadminIds: [0],
  sessionTtlMinutes: 30,
  userRateLimitSeconds: 20,
};

export function isModerator(userId) {
  return config.superadminIds.includes(Number(userId));
}

export function escapeHtml(value = '') {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;');
}
