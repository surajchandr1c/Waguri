'use client';

import React from 'react';
import Header from '@/components/Header';
import { Sliders, Database, Key, Server, Shield, CheckCircle2, HardDrive } from 'lucide-react';

export default function SettingsArchitecturePage() {
  const envVars = [
    { key: 'BOT_TOKEN', desc: 'Telegram Bot API Token provided by @BotFather', type: 'Required', example: '8840030276:AAE0dSM...' },
    { key: 'BOT_OWNER_IDS', desc: 'Comma-separated Telegram user IDs with superadmin /owner access', type: 'Required', example: '111111,222222' },
    { key: 'DATABASE_PATH', desc: 'SQLite database file path for multi-tenant state persistence', type: 'Optional', example: 'moderation.db' },
    { key: 'TELEGRAM_CONNECT_TIMEOUT', desc: 'HTTP connection timeout in seconds to prevent drops', type: 'Optional', example: '30.0' },
    { key: 'TELEGRAM_READ_TIMEOUT', desc: 'HTTP read timeout in seconds for polling stability', type: 'Optional', example: '30.0' },
    { key: 'TELEGRAM_BOOTSTRAP_RETRIES', desc: 'Network retry attempts during initial polling startup', type: 'Optional', example: '5' },
    { key: 'TELEGRAM_PROXY_URL', desc: 'Optional HTTP/SOCKS5 proxy URL for restricted regions', type: 'Optional', example: 'http://proxy.host:8080' },
  ];

  const tables = [
    { name: 'telegram_business_connections', desc: 'Stores connected Telegram Business accounts, status, rights, and account names.' },
    { name: 'personal_auto_reply_settings', desc: 'Individual per-user preferences: is_enabled, first_time_only, cooldown_seconds, daily_limit, reply_delay_seconds.' },
    { name: 'personal_reply_templates', desc: 'Custom user message templates with placeholder support.' },
    { name: 'personal_first_contacts', desc: 'Tracks sender history with UNIQUE(business_user_id, sender_user_id) constraint.' },
    { name: 'personal_reply_deliveries', desc: 'Audit log of sent auto-replies, response times, and failure reasons.' },
    { name: 'personal_excluded_users', desc: 'User blacklist exclusions to avoid auto-replying to specific senders.' },
    { name: 'group_settings', desc: 'Isolated group moderation toggles (anti-link, anti-spam, media, raid mode).' },
    { name: 'group_stats', desc: 'Per-group counters for deleted links, filtered spam, and issued warnings.' },
    { name: 'whitelist_domains', desc: 'Group-level allowed URL domains that bypass anti-link filtration.' },
    { name: 'blacklist_patterns', desc: 'Group-level banned regex strings and keyword patterns.' },
  ];

  return (
    <div className="flex-1 flex flex-col">
      <Header
        title="Bot Configuration & Architecture"
        description="System environment variables, SQLite multi-tenant database tables, and connection diagnostics."
        badge="System Architecture"
      />

      <div className="flex-1 p-3.5 sm:p-6 lg:p-8 max-w-7xl mx-auto w-full space-y-8 sm:space-y-10">
        {/* Architecture Highlights */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 sm:gap-6">
          <div className="p-5 sm:p-6 rounded-3xl bg-slate-900/60 border border-slate-800 space-y-3">
            <div className="p-3 rounded-2xl bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 w-fit">
              <Database className="w-5 h-5" />
            </div>
            <h3 className="text-base font-bold text-white">Multi-Tenant SQLite</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Every group and connected Telegram Business user is strictly keyed by unique identifiers (<code>chat_id</code> / <code>user_id</code>), preventing cross-account contamination.
            </p>
          </div>

          <div className="p-5 sm:p-6 rounded-3xl bg-slate-900/60 border border-slate-800 space-y-3">
            <div className="p-3 rounded-2xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 w-fit">
              <Server className="w-5 h-5" />
            </div>
            <h3 className="text-base font-bold text-white">Conflict Prevention</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Native handling for <code>telegram.error.Conflict</code> ensures clean error reporting if multiple instances attempt to poll with the same token.
            </p>
          </div>

          <div className="p-5 sm:p-6 rounded-3xl bg-slate-900/60 border border-slate-800 space-y-3">
            <div className="p-3 rounded-2xl bg-purple-500/10 text-purple-400 border border-purple-500/20 w-fit">
              <Shield className="w-5 h-5" />
            </div>
            <h3 className="text-base font-bold text-white">Cryptographic Spam Check</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Message text is hashed using normalized SHA-256 fingerprints to track burst repetitions without storing raw message contents long-term.
            </p>
          </div>
        </div>

        {/* Database Tables Section */}
        <div className="p-5 sm:p-8 rounded-3xl bg-slate-900/40 border border-slate-800 space-y-4">
          <div className="flex items-center gap-2">
            <HardDrive className="w-5 h-5 text-indigo-400 shrink-0" />
            <h2 className="text-base sm:text-lg font-bold text-white tracking-tight">
              Persistent Database Schema (10 Tables)
            </h2>
          </div>
          <p className="text-xs text-slate-400">
            Waguri maintains SQLite persistence across bot restarts with automated schema verification.
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-2">
            {tables.map((t, idx) => (
              <div key={idx} className="p-3.5 sm:p-4 rounded-2xl bg-slate-950 border border-slate-800 space-y-1">
                <code className="text-xs font-mono font-bold text-indigo-300 break-words">{t.name}</code>
                <p className="text-[11px] sm:text-xs text-slate-400 leading-relaxed">{t.desc}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Environment Variables Reference (Responsive Table / Mobile Scroll) */}
        <div className="p-5 sm:p-8 rounded-3xl bg-slate-900/40 border border-slate-800 space-y-4">
          <div className="flex items-center gap-2">
            <Key className="w-5 h-5 text-purple-400 shrink-0" />
            <h2 className="text-base sm:text-lg font-bold text-white tracking-tight">
              Environment Variables (.env) Reference
            </h2>
          </div>

          <div className="overflow-x-auto custom-scrollbar -mx-2 px-2">
            <table className="w-full text-left text-xs border-collapse min-w-[580px]">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400 uppercase tracking-wider text-[10px] sm:text-[11px]">
                  <th className="py-3 px-3 sm:px-4">Variable</th>
                  <th className="py-3 px-3 sm:px-4">Type</th>
                  <th className="py-3 px-3 sm:px-4">Description</th>
                  <th className="py-3 px-3 sm:px-4">Example</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {envVars.map((v, i) => (
                  <tr key={i} className="hover:bg-slate-900/50 transition-colors">
                    <td className="py-3 px-3 sm:px-4 font-mono font-bold text-purple-300 whitespace-nowrap">{v.key}</td>
                    <td className="py-3 px-3 sm:px-4 whitespace-nowrap">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                          v.type === 'Required'
                            ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                            : 'bg-slate-800 text-slate-400'
                        }`}
                      >
                        {v.type}
                      </span>
                    </td>
                    <td className="py-3 px-3 sm:px-4 text-slate-300">{v.desc}</td>
                    <td className="py-3 px-3 sm:px-4 font-mono text-slate-400 text-[11px] whitespace-nowrap">{v.example}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
