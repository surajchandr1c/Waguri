import { NextResponse } from 'next/server';
import { getDb } from '@/lib/mongodb';
import { fetchRawDatabaseData } from '@/lib/pythonBridge';

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

export async function GET() {
  const timing = calculateMidnightTiming();

  try {
    const db = await getDb();

    // 1. Real active counts from MongoDB
    const activeChatsCount = await db.collection('chats').countDocuments({ is_active: 1 });
    const businessUserIds = await db.collection('business_connections').distinct('user_id', { is_enabled: 1 });
    const totalActiveEntities = businessUserIds.length + activeChatsCount;

    // 2. Real moderation log counts in last 24h
    const nowSec = Date.now() / 1000;
    const past24hSec = nowSec - 86400;

    const recentLogs = await db
      .collection('chat_moderation_logs')
      .find({ timestamp: { $gte: past24hSec } })
      .toArray();

    let linksDeleted24h = 0;
    let abuseDeleted24h = 0;
    let spamDeleted24h = 0;
    let usersBlocked24h = 0;

    for (const log of recentLogs) {
      const action = String(log.action || '');
      if (action.includes('LINK_DELETED')) {
        linksDeleted24h++;
      } else if (action === 'ABUSE_DELETED') {
        abuseDeleted24h++;
      } else if (action === 'SPAM_DELETED') {
        spamDeleted24h++;
      } else if (action.includes('MUTED') || action.includes('RESTRICTED') || action.includes('BANNED')) {
        usersBlocked24h++;
      }
    }

    // 3. Real cumulative stats from chat_statistics
    const statAgg = await db
      .collection('chat_statistics')
      .aggregate([
        {
          $group: {
            _id: null,
            totalLinks: { $sum: '$links_deleted' },
            totalAbuse: { $sum: '$abuse_deleted' },
            totalSpam: { $sum: '$spam_deleted' },
            totalMessages: { $sum: '$total_messages_checked' },
            totalRestrictions: { $sum: '$restrictions_applied' },
            totalWarnings: { $sum: '$warnings_issued' },
          },
        },
      ])
      .toArray();

    const totals = statAgg[0] || {};
    const cumulativeLinks = Number(totals.totalLinks || 0);
    const cumulativeAbuse = Number(totals.totalAbuse || 0);
    const cumulativeSpam = Number(totals.totalSpam || 0);
    const cumulativeRestrictions = Number(totals.totalRestrictions || 0);

    const linksDeleted = Math.max(linksDeleted24h, cumulativeLinks);
    const messagesDeleted = Math.max(
      linksDeleted24h + abuseDeleted24h + spamDeleted24h,
      cumulativeLinks + cumulativeAbuse + cumulativeSpam
    );
    const usersBlocked = Math.max(usersBlocked24h, cumulativeRestrictions);

    // 4. Real daily history from daily_moderation_stats
    const historyRows = await db
      .collection('daily_moderation_stats')
      .find({})
      .sort({ stat_date: -1 })
      .limit(7)
      .toArray();

    const history24h = historyRows.map((h: any) => ({
      stat_date: String(h.stat_date),
      links_deleted: Number(h.links_deleted || 0),
      messages_deleted: Number(h.messages_deleted || 0),
      users_blocked: Number(h.users_blocked || 0),
      features_count: Number(h.features_count || 33),
      active_users_count: Number(h.active_users_count || 0),
      archived_at: String(h.archived_at || ''),
    }));

    return NextResponse.json({
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
  } catch (error) {
    console.warn('Direct MongoDB query failed, falling back to pythonBridge:', error);

    const rawData = fetchRawDatabaseData<any>();
    if (rawData) {
      const activeChats = (rawData.chats || []).filter((c: any) => c.is_active).length;
      const activeUsers = (rawData.business_connections || []).filter((bc: any) => bc.is_enabled).length;
      const totalLinks = rawData.total_links_deleted || 0;
      const totalAbuse = rawData.total_abuse_deleted || 0;
      const totalSpam = rawData.total_spam_deleted || 0;
      const totalRestrictions = (rawData.chat_statistics || []).reduce(
        (acc: number, s: any) => acc + (s.restrictions_applied || 0),
        0
      );

      return NextResponse.json({
        databaseEngine: 'MongoDB Atlas Active',
        postgresConnected: false,
        today: {
          stat_date: timing.todayStr,
          links_deleted: totalLinks,
          messages_deleted: totalLinks + totalAbuse + totalSpam,
          users_blocked: totalRestrictions,
          features_count: 33,
          active_users_count: activeUsers + activeChats,
          reset_at: `${timing.todayStr}T00:00:00`,
          updated_at: new Date().toISOString(),
          secondsUntilReset: timing.secondsUntilReset,
          nextResetIso: timing.nextResetIso,
        },
        history24h: [],
      });
    }

    return NextResponse.json(
      {
        databaseEngine: 'MongoDB Atlas Active',
        postgresConnected: false,
        today: {
          stat_date: timing.todayStr,
          links_deleted: 0,
          messages_deleted: 0,
          users_blocked: 0,
          features_count: 33,
          active_users_count: 0,
          reset_at: `${timing.todayStr}T00:00:00`,
          updated_at: new Date().toISOString(),
          secondsUntilReset: timing.secondsUntilReset,
          nextResetIso: timing.nextResetIso,
        },
        history24h: [],
      },
      { status: 200 }
    );
  }
}
