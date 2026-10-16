import { table, integer, text, boolean, json, index, sql } from 'sdk/db';

export const users = table('users', {
  tgId: integer('tg_id').primaryKey(),
  isBanned: boolean('is_banned').default(false),
  lastActionAt: integer('last_action_at', { mode: 'timestamp' }),
  createdAt: integer('created_at', { mode: 'timestamp' }).default(sql`(unixepoch())`),
});

export const categories = table('categories', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  key: text('key').notNull().unique(),
  title: text('title').notNull(),
  emoji: text('emoji').notNull().default('📝'),
  enabled: boolean('enabled').default(true),
  sortOrder: integer('sort_order').notNull().default(0),
}, (t) => ({
  enabledOrder: index('idx_categories_enabled_order').on(t.enabled, t.sortOrder),
}));

export const sessions = table('sessions', {
  userId: integer('user_id').primaryKey(),
  state: text('state').notNull(),
  payload: json('payload').notNull().default({}),
  expiresAt: integer('expires_at', { mode: 'timestamp' }).notNull(),
  updatedAt: integer('updated_at', { mode: 'timestamp' }).default(sql`(unixepoch())`),
});

export const submissions = table('submissions', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  userId: integer('user_id').notNull(),
  categoryId: integer('category_id').notNull(),
  text: text('text').notNull(),
  // Existing published rows may predate anonymous comments, so this is nullable.
  commentToken: text('comment_token').unique(),
  status: text('status').notNull().default('pending'),
  moderationMessageId: integer('moderation_message_id'),
  channelMessageId: integer('channel_message_id'),
  discussionMessageId: integer('discussion_message_id'),
  createdAt: integer('created_at', { mode: 'timestamp' }).default(sql`(unixepoch())`),
  reviewedAt: integer('reviewed_at', { mode: 'timestamp' }),
}, (t) => ({
  statusCreated: index('idx_submissions_status_created').on(t.status, t.createdAt),
  userCreated: index('idx_submissions_user_created').on(t.userId, t.createdAt),
  channelMessage: index('idx_submissions_channel_message').on(t.channelMessageId),
}));

export const anonymousReplies = table('anonymous_replies', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  submissionId: integer('submission_id').notNull(),
  userId: integer('user_id').notNull(),
  text: text('text').notNull(),
  status: text('status').notNull().default('pending'),
  moderationMessageId: integer('moderation_message_id'),
  discussionMessageId: integer('discussion_message_id'),
  createdAt: integer('created_at', { mode: 'timestamp' }).default(sql`(unixepoch())`),
  reviewedAt: integer('reviewed_at', { mode: 'timestamp' }),
}, (t) => ({
  statusCreated: index('idx_replies_status_created').on(t.status, t.createdAt),
  submissionCreated: index('idx_replies_submission_created').on(t.submissionId, t.createdAt),
}));
