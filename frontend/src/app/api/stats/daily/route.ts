import { NextResponse } from 'next/server';
import type { Document } from 'mongodb';
import { getDb } from '@/lib/mongodb';

interface DailyModerationRecord extends Document {
  stat_date?: string | Date;
  links_deleted?: number;
  messages_deleted?: number;
  users_blocked?: number;
  features_count?: number;
  active_users_count?: number;
  archived_at?: string | Date;
}

export function calculateMidnightTiming() {
  const now = new Date();
  const nextMidnight = new Date(now);
  nextMidnight.setHours(24, 0, 0, 0);

  const secondsUntilReset = Math.max(0, Math.floor((nextMidnight.getTime() - now.getTime()) / 1000));

  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  const todayStr = `${year}-${month}-${day}`;

  return {
    todayStr,
    secondsUntilReset,
    nextResetIso: nextMidnight.toISOString(),
  };
}

export async function GET(_request: Request) {
  const timing = calculateMidnightTiming();

  try {
    const db = await getDb();

    // 1. Real active counts from MongoDB
    const [activeChatsCount, businessUserIds] = await Promise.all([
      db.collection('chats').countDocuments({ is_active: 1 }),
      db.collection('business_connections').distinct('user_id', { is_enabled: 1 }),
    ]);
    const totalActiveEntities = businessUserIds.length + activeChatsCount;

    const startOfDay = new Date();
    startOfDay.setHours(0, 0, 0, 0);
    const dayStartSec = startOfDay.getTime() / 1000;
    const moderationLogs = db.collection('chat_moderation_logs');
    const [linksDeleted, abuseDeleted, spamDeleted, usersBlocked, historyRows] = await Promise.all([
      moderationLogs.countDocuments({
        timestamp: { $gte: dayStartSec },
        action: { $regex: 'LINK_DELETED' },
      }),
      moderationLogs.countDocuments({
        timestamp: { $gte: dayStartSec },
        action: 'ABUSE_DELETED',
      }),
      moderationLogs.countDocuments({
        timestamp: { $gte: dayStartSec },
        action: 'SPAM_DELETED',
      }),
      moderationLogs.countDocuments({
        timestamp: { $gte: dayStartSec },
        $or: [
          { action: { $regex: 'MUTED' } },
          { action: { $regex: 'RESTRICTED' } },
          { action: { $regex: 'BANNED' } },
        ],
      }),
      db.collection<DailyModerationRecord>('daily_moderation_stats')
        .find({})
        .sort({ stat_date: -1 })
        .limit(7)
        .toArray(),
    ]);
    const messagesDeleted = linksDeleted + abuseDeleted + spamDeleted;

    const history24h = historyRows.map((h) => ({
      stat_date: String(h.stat_date),
      links_deleted: Number(h.links_deleted || 0),
      messages_deleted: Number(h.messages_deleted || 0),
      users_blocked: Number(h.users_blocked || 0),
      features_count: Number(h.features_count || 33),
      active_users_count: Number(h.active_users_count || 0),
      archived_at: String(h.archived_at || ''),
    }));

    const response = NextResponse.json({
      databaseEngine: 'MongoDB Atlas Active',
      postgresConnected: false,
      today: {
        stat_date: timing.todayStr,
        links_deleted: linksDeleted,
        messages_deleted: messagesDeleted,
        users_blocked: usersBlocked,
        features_count: 33,
        active_users_count: totalActiveEntities,
        reset_at: `${timing.todayStr}T00:00:00`,
        updated_at: new Date().toISOString(),
        secondsUntilReset: timing.secondsUntilReset,
        nextResetIso: timing.nextResetIso,
      },
      history24h,
    });
    response.headers.set('Cache-Control', 'private, max-age=5, stale-while-revalidate=30');
    return response;
  } catch (error) {
    console.error('Failed to load daily moderation statistics:', error);
    return NextResponse.json(
      { error: 'Failed to load daily moderation statistics.' },
      { status: 500 }
    );
  }
}
