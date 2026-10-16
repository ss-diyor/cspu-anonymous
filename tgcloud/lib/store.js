import { db, eq, asc } from 'sdk/db';
import { categories, sessions, users } from '../schema.js';
import { config } from './config.js';

export const DEFAULT_CATEGORIES = [
  ['suggestion', 'Fikr va taklif', '💬', 10],
  ['question', 'Savol', '❓', 20],
  ['problem', 'Muammo', '⚠️', 30],
  ['announcement', 'E’lon', '📢', 40],
  ['student_life', 'Talabalar hayoti', '🎓', 50],
  ['other', 'Boshqa', '📝', 60],
];

export async function ensureUser(userId) {
  const existing = await db.select().from(users).where(eq(users.tgId, userId)).get();
  if (existing) return existing;
  await db.insert(users).values({ tgId: userId }).onConflictDoNothing({ target: users.tgId }).run();
  return db.select().from(users).where(eq(users.tgId, userId)).get();
}

export async function ensureCategories() {
  for (const [key, title, emoji, sortOrder] of DEFAULT_CATEGORIES) {
    await db.insert(categories).values({ key, title, emoji, sortOrder })
      .onConflictDoNothing({ target: categories.key }).run();
  }
}

export async function activeCategories() {
  await ensureCategories();
  return db.select().from(categories)
    .where(eq(categories.enabled, true))
    .orderBy(asc(categories.sortOrder)).all();
}

export async function getSession(userId) {
  const session = await db.select().from(sessions).where(eq(sessions.userId, userId)).get();
  if (!session) return null;
  if (session.expiresAt && session.expiresAt.getTime() <= Date.now()) {
    await clearSession(userId);
    return null;
  }
  return session;
}

export async function setSession(userId, state, payload) {
  const expiresAt = new Date(Date.now() + config.sessionTtlMinutes * 60_000);
  await db.insert(sessions).values({ userId, state, payload, expiresAt })
    .onConflictDoUpdate({
      target: sessions.userId,
      set: { state, payload, expiresAt, updatedAt: new Date() },
    }).run();
}

export async function clearSession(userId) {
  await db.delete(sessions).where(eq(sessions.userId, userId)).run();
}
