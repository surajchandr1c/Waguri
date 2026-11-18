import { NextResponse } from 'next/server';
import { execSync } from 'node:child_process';
import path from 'node:path';
import fs from 'node:fs';
import { BotUser, BotGroupChat, BotChannel, BotFeatureUsage, UserActivity } from '@/types/user';

function fetchRawDatabaseData() {
  const candidateScripts = [
    path.join(process.cwd(), '..', 'get_users_data.py'),
    path.join(process.cwd(), 'get_users_data.py'),
    'c:\\Users\\Suraj\\Desktop\\New folder\\bot\\get_users_data.py',
  ];

  for (const script of candidateScripts) {
    if (fs.existsSync(/*turbopackIgnore: true*/ script)) {
      try {
        const stdout = execSync(`python "${script}"`, {
          timeout: 15000,
          encoding: 'utf-8',
          windowsHide: true,
        });
        const parsed = JSON.parse(stdout);
        if (parsed && !parsed.error) {
          return parsed;
        }
      } catch (err) {
        console.warn(`Execution failed for ${script}:`, err);
      }
    }
  }

  return null;
}

export async function GET() {
  const dbData = fetchRawDatabaseData();

  const businessConnections: any[] = dbData?.business_connections || [];
  const personalSettings: any[] = dbData?.personal_reply_settings || [];
  const personalTemplates: any[] = dbData?.personal_reply_templates || [];
  const businessReplyLogs: any[] = dbData?.business_reply_logs || [];
  const rawChats: any[] = dbData?.chats || [];
  const chatSettings: any[] = dbData?.chat_settings || [];
  const chatStatistics: any[] = dbData?.chat_statistics || [];
  const chatJoinEvents: any[] = dbData?.chat_join_events || [];

  // ONLY USERS WHO ADDED THE BOT ON PERSONAL DIRECT MESSAGES
  const users: BotUser[] = [];

  for (const bc of businessConnections) {
    if (!bc.is_enabled) continue;
    const settings = personalSettings.find((ps) => ps.user_id === bc.user_id) || {};
    const template = personalTemplates.find((pt) => pt.user_id === bc.user_id) || {};
    const userReplies = businessReplyLogs.filter((r) => r.business_user_id === bc.user_id);

    const features: BotFeatureUsage[] = [
      {
        id: 'feat_business_secretary',
        name: 'Personal Auto-Reply (Secretary Mode)',
        category: 'personal-autoreply',
        iconName: 'Briefcase',
        status: bc.is_enabled ? 'active' : 'disabled',
        statusLabel: 'Active Secretary',
        description: 'Automated personal secretary responding directly to incoming messages.',
        configDetails: {
          'Status': bc.is_enabled ? 'Enabled' : 'Disabled',
          'Can Reply': bc.can_reply ? 'Granted' : 'Pending',
          'Mode': settings.first_time_only ? 'First-Time Contacts Only' : 'Periodic Cooldown',
          'Daily Reply Limit': `${settings.daily_limit || 100} msgs/day`,
          'Cooldown Interval': `${(settings.cooldown_seconds || 86400) / 3600} Hours`,
          'Parse Mode': settings.parse_mode || 'HTML',
        },
        metrics: [
          { label: 'Daily Cap', value: `${settings.daily_limit || 100} msgs` },
          { label: 'Cooldown', value: `${(settings.cooldown_seconds || 86400) / 3600}h` },
        ],
      },
      {
        id: 'feat_custom_templates',
        name: 'Dynamic Message Template',
        category: 'personal-autoreply',
        iconName: 'Sparkles',
        status: template.content ? 'active' : 'configured',
        statusLabel: 'Active Template',
        description: 'Auto-reply template with dynamic variables.',
        configDetails: {
          'Template Name': template.template_name || 'default',
          'Content': template.content || 'https://t.me/+jneLoLFT1xs3YWNl',
        },
        metrics: [
          { label: 'Template', value: template.template_name || 'default' },
        ],
      },
      {
        id: 'feat_first_contact',
        name: 'First-Time Contact Detection',
        category: 'personal-autoreply',
        iconName: 'CheckCircle2',
        status: settings.first_time_only ? 'active' : 'configured',
        statusLabel: 'Strict First Contact',
        description: 'Ensures secretary replies are sent only once per unique incoming sender.',
        configDetails: {
          'First Contact Filter': settings.first_time_only ? 'Enabled' : 'Disabled',
          'Welcome Message': settings.welcome_message_enabled ? 'Enabled' : 'Disabled',
        },
      },
      {
        id: 'feat_cooldown_timer',
        name: '24-Hour Cooldown Window',
        category: 'personal-autoreply',
        iconName: 'Clock',
        status: 'active',
        statusLabel: '24h Timer Armed',
        description: 'Rate-limits repeated replies to the same sender within 24 hours.',
        configDetails: {
          'Cooldown Window': `${(settings.cooldown_seconds || 86400) / 3600} Hours`,
        },
      },
    ];

    const activities: UserActivity[] = [
      {
        id: `act_${bc.user_id}_conn`,
        timestamp: new Date((bc.connected_at || Date.now() / 1000) * 1000).toLocaleString(),
        action: 'Connected Bot to Personal Account',
        category: 'business',
        details: `Connected @Ms_Waguri_bot as personal business secretary for @${bc.account_username || 'user'}.`,
      },
      ...userReplies.slice(0, 5).map((r) => ({
        id: `act_${bc.user_id}_rep_${r.id}`,
        timestamp: new Date((r.sent_at || Date.now() / 1000) * 1000).toLocaleString(),
        action: 'Secretary Auto-Reply Sent',
        category: 'business' as const,
        details: `Sent template "${r.reply_text}" (Status: ${r.status}).`,
      })),
    ];

    users.push({
      id: `usr_${bc.user_id}`,
      telegramId: bc.user_id,
      firstName: bc.account_first_name || 'Telegram User',
      username: bc.account_username || undefined,
      role: 'business_owner',
      roleLabel: 'Personal DM Account',
      avatarGradient: 'from-purple-500 via-indigo-500 to-pink-500',
      status: bc.is_enabled ? 'online' : 'idle',
      connectedAt: new Date((bc.connected_at || Date.now() / 1000) * 1000).toLocaleDateString(),
      lastActive: 'Active now',
      associatedChat: {
        id: bc.user_chat_id || bc.user_id,
        title: `Personal DM (@${bc.account_username || 'user'})`,
        type: 'business_dm',
      },
      stats: {
        totalInteractions: userReplies.length,
        autoRepliesSent: userReplies.length,
        warningsCount: 0,
        messagesChecked: userReplies.length,
        groupsCount: 0,
      },
      featuresUsed: features,
      recentActivity: activities,
    });
  }

  // GROUP CHATS (GC) AND CHANNELS THAT ADDED THE BOT
  const groups: BotGroupChat[] = [];
  const channels: BotChannel[] = [];

  for (const c of rawChats) {
    if (!c.is_active) continue;

    const isChannel = c.chat_type === 'channel';
    const settings = chatSettings.find((s) => s.chat_id === c.chat_id) || {};
    const statsRow = chatStatistics.find((s) => s.chat_id === c.chat_id) || {};

    if (isChannel) {
      channels.push({
        id: `chan_${Math.abs(c.chat_id)}`,
        channelId: c.chat_id,
        title: c.chat_title || 'Telegram Channel',
        type: 'channel',
        subscriberCount: 1,
        isActive: Boolean(c.is_active),
        avatarGradient: 'from-purple-600 via-pink-500 to-rose-500',
        addedAt: new Date((c.added_at || Date.now() / 1000) * 1000).toLocaleDateString(),
        featuresUsed: [
          {
            id: 'feat_chan_antilink',
            name: 'Broadcast Anti-Link Filter',
            category: 'group-management',
            iconName: 'Link',
            status: settings.anti_link_enabled ? 'active' : 'disabled',
            statusLabel: settings.anti_link_enabled ? 'Active' : 'Disabled',
            description: 'Deletes unauthorized promotion and referral links in channel posts.',
            configDetails: {
              'Action': 'Deletes unauthorized link posts',
            },
          },
          {
            id: 'feat_chan_cleanservice',
            name: 'Clean Service Noise Reducer',
            category: 'group-management',
            iconName: 'Trash2',
            status: settings.clean_service_enabled ? 'active' : 'disabled',
            statusLabel: settings.clean_service_enabled ? 'Active' : 'Disabled',
            description: 'Suppresses channel notification clutter.',
            configDetails: {
              'Service Messages Clean': 'Enabled',
            },
          },
        ],
        stats: {
          postsProcessed: 28,
          linksFiltered: 0,
        },
        recentActivity: [
          {
            id: `act_chan_${c.chat_id}_1`,
            timestamp: 'Today',
            action: 'Channel Active',
            category: 'system',
            details: 'Waguri added to channel with anti-link and clean-service enabled.',
          },
        ],
      });
    } else {
      // Group Chat (GC)
      const groupJoins = chatJoinEvents.filter((j) => j.chat_id === c.chat_id);

      const gcFeatures: BotFeatureUsage[] = [
        {
          id: 'feat_gc_antilink',
          name: 'Anti-Link Enforcement',
          category: 'moderation',
          iconName: 'Link',
          status: settings.anti_link_enabled ? 'active' : 'disabled',
          statusLabel: settings.anti_link_enabled ? 'Active' : 'Disabled',
          description: 'Blocks unauthorized Telegram invite links and external advertisements.',
          configDetails: {
            'Anti-Link': settings.anti_link_enabled ? 'Enabled' : 'Disabled',
            'Action': 'Delete and warn sender',
          },
        },
        {
          id: 'feat_gc_antispam',
          name: 'Anti-Spam Flooding Shield',
          category: 'moderation',
          iconName: 'Zap',
          status: settings.anti_spam_enabled ? 'active' : 'disabled',
          statusLabel: settings.anti_spam_enabled ? 'Active' : 'Disabled',
          description: `Detects repetitive flooding (${settings.flood_threshold_messages || 8} msgs / ${settings.flood_window_seconds || 10}s).`,
          configDetails: {
            'Threshold': `${settings.flood_threshold_messages || 8} msgs / ${settings.flood_window_seconds || 10}s`,
            'Spam Window': `${settings.spam_window_seconds || 30}s`,
          },
        },
        {
          id: 'feat_gc_antibio',
          name: 'Anti-Bio Link Screening',
          category: 'group-management',
          iconName: 'ShieldCheck',
          status: settings.anti_bio_link_enabled ? 'active' : 'disabled',
          statusLabel: settings.anti_bio_link_enabled ? 'Active' : 'Disabled',
          description: 'Scans profiles of new members for advertising links in their bio.',
          configDetails: {
            'Bio Link Check': settings.anti_bio_link_enabled ? 'Enabled' : 'Disabled',
          },
        },
        {
          id: 'feat_gc_cleanservice',
          name: 'Clean Service Noise Reducer',
          category: 'group-management',
          iconName: 'Trash2',
          status: settings.clean_service_enabled ? 'active' : 'disabled',
          statusLabel: settings.clean_service_enabled ? 'Active' : 'Disabled',
          description: 'Deletes noisy "X joined" and "Y left" service messages.',
          configDetails: {
            'Clean Service': settings.clean_service_enabled ? 'Enabled' : 'Disabled',
          },
        },
        {
          id: 'feat_gc_warnings',
          name: '2-Strike Warning System',
          category: 'moderation',
          iconName: 'AlertTriangle',
          status: 'active',
          statusLabel: '2 Strikes Max',
          description: 'Automated 2-strike penalty escalating to a 24-hour mute.',
          configDetails: {
            'Limit': '2 Strikes maximum',
            'Penalty': '24-hour mute',
          },
        },
      ];

      groups.push({
        id: `gc_${Math.abs(c.chat_id)}`,
        chatId: c.chat_id,
        title: c.chat_title || 'Group Chat',
        type: c.chat_type === 'supergroup' ? 'supergroup' : 'group',
        memberCount: groupJoins.length || (c.chat_type === 'supergroup' ? 42 : 12),
        isActive: Boolean(c.is_active),
        avatarGradient: c.chat_type === 'supergroup' ? 'from-indigo-600 via-sky-500 to-blue-600' : 'from-sky-500 to-teal-500',
        addedAt: new Date((c.added_at || Date.now() / 1000) * 1000).toLocaleDateString(),
        featuresUsed: gcFeatures,
        stats: {
          messagesChecked: statsRow.total_messages_checked || 0,
          linksDeleted: statsRow.links_deleted || 0,
          spamDeleted: statsRow.spam_deleted || 0,
          warningsIssued: statsRow.warnings_issued || 0,
          usersRestricted: statsRow.restrictions_applied || 0,
        },
        recentActivity: [
          {
            id: `act_gc_${c.chat_id}_1`,
            timestamp: 'Active',
            action: 'Group Protected',
            category: 'group',
            details: `Waguri added to group. Enforcing Anti-Link, Anti-Spam, and CleanService.`,
          },
        ],
      });
    }
  }

  return NextResponse.json({
    totalUsers: users.length,
    users,
    groups,
    channels,
    summary: {
      totalUsers: users.length,
      totalGC: groups.length,
      totalChannels: channels.length,
    },
  });
}

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const action = body.action;

    const candidateScripts = [
      path.join(process.cwd(), '..', 'get_users_data.py'),
      path.join(process.cwd(), 'get_users_data.py'),
      'c:\\Users\\Suraj\\Desktop\\New folder\\bot\\get_users_data.py',
    ];

    let scriptPath = '';
    for (const script of candidateScripts) {
      if (fs.existsSync(/*turbopackIgnore: true*/ script)) {
        scriptPath = script;
        break;
      }
    }

    if (!scriptPath) {
      return NextResponse.json({ error: 'Failed to locate handler script' }, { status: 500 });
    }

    const runPy = (args: string[], stdinData?: string) => {
      const { spawnSync } = require('node:child_process');
      const res = spawnSync('python', [scriptPath, ...args], {
        input: stdinData,
        encoding: 'utf-8',
        timeout: 15000,
        windowsHide: true,
      });
      if (res.error) throw res.error;
      const stdout = (res.stdout || '').trim();
      if (!stdout && res.stderr) throw new Error(res.stderr);
      return JSON.parse(stdout || '{}');
    };

    if (action === 'add_chat') {
      const res = runPy(['--chat-add'], JSON.stringify(body.data || body));
      return NextResponse.json(res);
    } else if (action === 'edit_chat') {
      const id = body.id || body.chat_id;
      if (!id) return NextResponse.json({ error: 'Missing chat id' }, { status: 400 });
      const res = runPy(['--chat-edit', String(id)], JSON.stringify(body.data || body));
      return NextResponse.json(res);
    } else if (action === 'delete_chat') {
      const id = body.id || body.chat_id;
      if (!id) return NextResponse.json({ error: 'Missing chat id' }, { status: 400 });
      const res = runPy(['--chat-delete', String(id)]);
      return NextResponse.json(res);
    } else if (action === 'add_user') {
      const res = runPy(['--user-add'], JSON.stringify(body.data || body));
      return NextResponse.json(res);
    } else if (action === 'edit_user') {
      const id = body.id || body.user_id;
      if (!id) return NextResponse.json({ error: 'Missing user id' }, { status: 400 });
      const res = runPy(['--user-edit', String(id)], JSON.stringify(body.data || body));
      return NextResponse.json(res);
    } else if (action === 'delete_user') {
      const id = body.id || body.user_id;
      if (!id) return NextResponse.json({ error: 'Missing user id' }, { status: 400 });
      const res = runPy(['--user-delete', String(id)]);
      return NextResponse.json(res);
    }

    // Default legacy entity removal: { id, type }
    const { id, type } = body;
    if (!id || !type) {
      return NextResponse.json({ error: 'Missing id or type parameter' }, { status: 400 });
    }

    const res = runPy(['--remove', String(type), String(id)]);
    return NextResponse.json(res);
  } catch (err: any) {
    console.error('User/Chat operation failed:', err);
    return NextResponse.json({ error: err.message || 'Operation failed' }, { status: 500 });
  }
}
