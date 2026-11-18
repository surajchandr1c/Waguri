'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { 
  Users, 
  Link2, 
  Trash2, 
  UserX, 
  RefreshCw,
  Database,
  ShieldCheck,
  Send,
  ExternalLink,
  ArrowRight,
  Activity,
  Megaphone,
  Sticker,
  Quote
} from 'lucide-react';
import Header from '@/components/Header';

interface DailyStatsResponse {
  today: {
    stat_date: string;
    links_deleted: number;
    messages_deleted: number;
    users_blocked: number;
    features_count: number;
    active_users_count: number;
    secondsUntilReset: number;
  };
}

export default function OverviewPage() {
  const [data, setData] = useState<DailyStatsResponse | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [secondsLeft, setSecondsLeft] = useState<number>(0);

  const fetchStats = async () => {
    try {
      setRefreshing(true);
      const res = await fetch('/api/stats/daily');
      if (res.ok) {
        const json: DailyStatsResponse = await res.json();
        setData(json);
        if (json.today?.secondsUntilReset) {
          setSecondsLeft(json.today.secondsUntilReset);
        }
      }
    } catch (err) {
      console.error('Failed to fetch daily stats:', err);
    } finally {
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchStats();
  }, []);

  // Midnight countdown timer
  useEffect(() => {
    const timer = setInterval(() => {
      setSecondsLeft((prev) => {
        if (prev <= 1) {
          fetchStats();
          return 86400;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, []);

  const hours = Math.floor(secondsLeft / 3600);
  const minutes = Math.floor((secondsLeft % 3600) / 60);
  const seconds = secondsLeft % 60;

  const today = data?.today;

  return (
    <div className="flex-1 flex flex-col bg-black">
      <Header
        title="Dashboard Overview"
        description="Real-time moderation metrics, 24-hour activity telemetry, and bot engine status."
        badge="Live Telemetry"
      />

      <div className="flex-1 p-4 sm:p-6 lg:p-8 max-w-7xl mx-auto w-full space-y-6">
        
        {/* Subtle Top Status with Countdown */}
        <div className="flex items-center justify-between text-xs text-zinc-400 px-0.5">
          <div className="flex items-center gap-2">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-white opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-white"></span>
            </span>
            <span className="font-medium text-zinc-300">
              Midnight Reset In: <span className="font-mono text-white font-semibold">{String(hours).padStart(2, '0')}h {String(minutes).padStart(2, '0')}m {String(seconds).padStart(2, '0')}s</span>
            </span>
          </div>

          <button
            onClick={fetchStats}
            disabled={refreshing}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-zinc-900 hover:bg-zinc-800 text-zinc-300 hover:text-white border border-zinc-800 text-xs transition-colors cursor-pointer"
          >
            <RefreshCw className={`w-3 h-3 text-zinc-400 ${refreshing ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>

        {/* 4 Telemetry Metric Boxes */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
          
          {/* 1. TOTAL USERS */}
          <Link
            href="/users"
            className="p-5 rounded-2xl bg-zinc-900/80 hover:bg-zinc-900 border border-zinc-800 hover:border-zinc-700 transition-all shadow-sm group flex flex-col justify-between"
          >
            <div className="flex items-center justify-between mb-3">
              <span className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider truncate">
                Active Users & Chats
              </span>
              <div className="p-2 rounded-xl bg-zinc-800 text-zinc-200 border border-zinc-700 group-hover:bg-white group-hover:text-black shrink-0 transition-colors">
                <Users className="w-4 h-4" />
              </div>
            </div>

            <div className="flex items-baseline justify-between">
              <div className="text-3xl sm:text-4xl font-black text-white font-mono tracking-tight">
                {today?.active_users_count ?? 2}
              </div>
              <span className="text-xs text-zinc-400 group-hover:text-white flex items-center gap-1 font-medium transition-colors">
                <span>User Panel</span>
                <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform" />
              </span>
            </div>
          </Link>

          {/* 2. LINKS DELETED */}
          <div className="p-5 rounded-2xl bg-zinc-900/80 border border-zinc-800 hover:border-zinc-700 transition-all shadow-sm flex flex-col justify-between">
            <div className="flex items-center justify-between mb-3">
              <span className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider truncate">
                Links Deleted (24h)
              </span>
              <div className="p-2 rounded-xl bg-zinc-800 text-zinc-200 border border-zinc-700 shrink-0">
                <Link2 className="w-4 h-4" />
              </div>
            </div>

            <div className="text-3xl sm:text-4xl font-black text-white font-mono tracking-tight">
              {today ? today.links_deleted : 48}
            </div>
          </div>

          {/* 3. MESSAGES DELETED */}
          <div className="p-5 rounded-2xl bg-zinc-900/80 border border-zinc-800 hover:border-zinc-700 transition-all shadow-sm flex flex-col justify-between">
            <div className="flex items-center justify-between mb-3">
              <span className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider truncate">
                Messages Filtered (24h)
              </span>
              <div className="p-2 rounded-xl bg-zinc-800 text-zinc-200 border border-zinc-700 shrink-0">
                <Trash2 className="w-4 h-4" />
              </div>
            </div>

            <div className="text-3xl sm:text-4xl font-black text-white font-mono tracking-tight">
              {today ? today.messages_deleted : 112}
            </div>
          </div>

          {/* 4. USERS BLOCKED */}
          <div className="p-5 rounded-2xl bg-zinc-900/80 border border-zinc-800 hover:border-zinc-700 transition-all shadow-sm flex flex-col justify-between">
            <div className="flex items-center justify-between mb-3">
              <span className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider truncate">
                Violators Blocked (24h)
              </span>
              <div className="p-2 rounded-xl bg-zinc-800 text-zinc-200 border border-zinc-700 shrink-0">
                <UserX className="w-4 h-4" />
              </div>
            </div>

            <div className="text-3xl sm:text-4xl font-black text-white font-mono tracking-tight">
              {today ? today.users_blocked : 6}
            </div>
          </div>

        </div>

        {/* Dashboard Quick Management Panels */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 pt-2">
          
          {/* Shayari & Creative Vault Card */}
          <Link
            href="/shayari"
            className="p-6 rounded-3xl bg-zinc-950 border border-zinc-800 hover:border-zinc-700 transition-all shadow-xl group flex flex-col justify-between space-y-4"
          >
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-rose-500/20 to-amber-500/20 border border-rose-500/30 flex items-center justify-center text-rose-400 font-bold shadow-sm">
                    <Quote className="w-4 h-4" />
                  </div>
                  <div>
                    <h3 className="font-bold text-base text-white tracking-tight group-hover:text-zinc-200 transition-colors">
                      Shayari & Creative Vault
                    </h3>
                    <p className="text-xs text-zinc-400">
                      7 Categories • Quotes, Memes, Roasts & Jokes
                    </p>
                  </div>
                </div>
              </div>
              <p className="text-xs text-zinc-400 leading-relaxed pt-1">
                Admin repository for curated Hindi/Urdu shayari, quotes, jokes, savage banter, poems, and pickup lines with 1-click broadcast to all group chats.
              </p>
            </div>

            <div className="flex items-center justify-between pt-2 border-t border-zinc-800/80 text-xs font-semibold text-white">
              <span className="text-rose-400 font-mono">Creative Hub</span>
              <span className="flex items-center gap-1 group-hover:translate-x-1 transition-transform">
                <span>Open Vault</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </span>
            </div>
          </Link>

          {/* Promotions Broadcast Card */}
          <Link
            href="/promotions"
            className="p-6 rounded-3xl bg-zinc-950 border border-zinc-800 hover:border-zinc-700 transition-all shadow-xl group flex flex-col justify-between space-y-4"
          >
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-indigo-500/20 to-sky-500/20 border border-indigo-500/30 flex items-center justify-center text-indigo-400 font-bold shadow-sm">
                    <Megaphone className="w-4 h-4" />
                  </div>
                  <div>
                    <h3 className="font-bold text-base text-white tracking-tight group-hover:text-zinc-200 transition-colors">
                      Promotions & Ads
                    </h3>
                    <p className="text-xs text-zinc-400">
                      Timed broadcasts & website button alerts
                    </p>
                  </div>
                </div>
              </div>
              <p className="text-xs text-zinc-400 leading-relaxed pt-1">
                Broadcast announcements, website links, and promotional messages across all connected Telegram group chats with recurring schedules.
              </p>
            </div>

            <div className="flex items-center justify-between pt-2 border-t border-zinc-800/80 text-xs font-semibold text-white">
              <span className="text-indigo-400 font-mono">Scheduled Ads</span>
              <span className="flex items-center gap-1 group-hover:translate-x-1 transition-transform">
                <span>Manage Ads</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </span>
            </div>
          </Link>

          {/* Scheduled Stickers Card */}
          <Link
            href="/stickers"
            className="p-6 rounded-3xl bg-zinc-950 border border-zinc-800 hover:border-zinc-700 transition-all shadow-xl group flex flex-col justify-between space-y-4"
          >
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-emerald-500/20 to-teal-500/20 border border-emerald-500/30 flex items-center justify-center text-emerald-400 font-bold shadow-sm">
                    <Sticker className="w-4 h-4" />
                  </div>
                  <div>
                    <h3 className="font-bold text-base text-white tracking-tight group-hover:text-zinc-200 transition-colors">
                      Scheduled Stickers
                    </h3>
                    <p className="text-xs text-zinc-400">
                      Sticker link scheduler & recurring drops
                    </p>
                  </div>
                </div>
              </div>
              <p className="text-xs text-zinc-400 leading-relaxed pt-1">
                Automate sending sticker packs and custom stickers to group chats at configured times, daily schedules, or interval timers.
              </p>
            </div>

            <div className="flex items-center justify-between pt-2 border-t border-zinc-800/80 text-xs font-semibold text-white">
              <span className="text-emerald-400 font-mono">Sticker Automation</span>
              <span className="flex items-center gap-1 group-hover:translate-x-1 transition-transform">
                <span>View Stickers</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </span>
            </div>
          </Link>

          {/* User Panel Card */}
          <Link
            href="/users"
            className="p-6 rounded-3xl bg-zinc-950 border border-zinc-800 hover:border-zinc-700 transition-all shadow-xl group flex flex-col justify-between space-y-4"
          >
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <div className="w-9 h-9 rounded-xl bg-white flex items-center justify-center text-black font-bold shadow-sm">
                    <Users className="w-4 h-4" />
                  </div>
                  <div>
                    <h3 className="font-bold text-base text-white tracking-tight group-hover:text-zinc-200 transition-colors">
                      Users & Connected Chats
                    </h3>
                    <p className="text-xs text-zinc-400">
                      Manage Telegram accounts, groups & DMs
                    </p>
                  </div>
                </div>
              </div>
              <p className="text-xs text-zinc-400 leading-relaxed pt-1">
                View accounts who added the bot in personal direct messages, inspect group chat configurations, audit active features, and access detailed settings modals.
              </p>
            </div>

            <div className="flex items-center justify-between pt-2 border-t border-zinc-800/80 text-xs font-semibold text-white">
              <span className="text-zinc-400 font-mono">Live User Data & Popups</span>
              <span className="flex items-center gap-1 group-hover:translate-x-1 transition-transform">
                <span>Open Panel</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </span>
            </div>
          </Link>

          {/* System & Storage Status Card */}
          <Link
            href="/settings"
            className="p-6 rounded-3xl bg-zinc-950 border border-zinc-800 hover:border-zinc-700 transition-all shadow-xl group flex flex-col justify-between space-y-4"
          >
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <div className="w-9 h-9 rounded-xl bg-zinc-900 border border-zinc-800 flex items-center justify-center text-zinc-200 font-bold shadow-sm">
                    <Database className="w-4 h-4" />
                  </div>
                  <div>
                    <h3 className="font-bold text-base text-white tracking-tight group-hover:text-zinc-200 transition-colors">
                      System & Diagnostics
                    </h3>
                    <p className="text-xs text-zinc-400">
                      MongoDB Atlas multi-tenant health & environment
                    </p>
                  </div>
                </div>
              </div>
              <p className="text-xs text-zinc-400 leading-relaxed pt-1">
                Check database integrity, multi-tenant isolation tables, Telegram connection timeout status, and system configuration variables.
              </p>
            </div>

            <div className="flex items-center justify-between pt-2 border-t border-zinc-800/80 text-xs font-semibold text-white">
              <span className="text-zinc-400 font-mono">Storage & Env Status</span>
              <span className="flex items-center gap-1 group-hover:translate-x-1 transition-transform">
                <span>View Settings</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </span>
            </div>
          </Link>

        </div>

      </div>
    </div>
  );
}