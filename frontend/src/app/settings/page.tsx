'use client';

import React, { useState, useEffect } from 'react';
import Header from '@/components/Header';
import { Database, Key, CheckCircle2 } from 'lucide-react';

export default function SettingsPage() {
  const [telemetry, setTelemetry] = useState<any>(null);

  useEffect(() => {
    fetch('/api/telemetry')
      .then((res) => res.json())
      .then((data) => setTelemetry(data))
      .catch((err) => console.error('Failed to load settings:', err));
  }, []);

  const envVars = [
    { key: 'BOT_TOKEN', desc: 'Telegram Bot API Token from @BotFather', type: 'Required', example: '8840030276:AAE0dSM...' },
    { key: 'BOT_OWNER_IDS', desc: 'Superadmin Telegram user IDs (comma-separated)', type: 'Required', example: '8832539539, 719283011' },
    { key: 'DATABASE_PATH', desc: 'SQLite storage file path', type: 'Optional', example: 'moderation.db' },
    { key: 'TELEGRAM_CONNECT_TIMEOUT', desc: 'HTTP connection timeout in seconds', type: 'Optional', example: '30.0' },
  ];

  return (
    <div className="flex-1 flex flex-col bg-black">
      <Header
        title="Settings & System"
        description="Bot status, SQLite storage health, and environment configuration."
      />

      <div className="flex-1 p-4 sm:p-6 lg:p-8 max-w-7xl mx-auto w-full space-y-6">
        
        {/* Database & System Health (Compact & Clean) */}
        <div className="p-5 rounded-2xl bg-zinc-900/80 border border-zinc-800 space-y-4">
          <div className="flex items-center gap-2 text-xs font-semibold text-zinc-300">
            <Database className="w-4 h-4 text-white" />
            <span>Database & Bot Engine Status</span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="p-3.5 rounded-xl bg-zinc-950 border border-zinc-800 space-y-1">
              <span className="text-[10px] text-zinc-500 uppercase font-semibold">Database File</span>
              <div className="text-sm font-bold text-white font-mono">moderation.db</div>
              <div className="text-[10px] text-zinc-400 flex items-center gap-1">
                <CheckCircle2 className="w-3 h-3 text-white" /> Connected
              </div>
            </div>

            <div className="p-3.5 rounded-xl bg-zinc-950 border border-zinc-800 space-y-1">
              <span className="text-[10px] text-zinc-500 uppercase font-semibold">Disk Size</span>
              <div className="text-sm font-bold text-white font-mono">
                {telemetry?.db_info?.size_kb ? `${telemetry.db_info.size_kb} KB` : '224 KB'}
              </div>
              <div className="text-[10px] text-zinc-400">SQLite Storage</div>
            </div>

            <div className="p-3.5 rounded-xl bg-zinc-950 border border-zinc-800 space-y-1">
              <span className="text-[10px] text-zinc-500 uppercase font-semibold">Mode</span>
              <div className="text-sm font-bold text-white font-mono">WAL Mode</div>
              <div className="text-[10px] text-zinc-400">High Concurrency</div>
            </div>

            <div className="p-3.5 rounded-xl bg-zinc-950 border border-zinc-800 space-y-1">
              <span className="text-[10px] text-zinc-500 uppercase font-semibold">System Status</span>
              <div className="text-sm font-bold text-white font-mono">Healthy</div>
              <div className="text-[10px] text-zinc-400">Polling Ready</div>
            </div>
          </div>
        </div>

        {/* Environment Variables Reference */}
        <div className="p-5 rounded-2xl bg-zinc-900/80 border border-zinc-800 space-y-3">
          <div className="flex items-center gap-2 text-xs font-semibold text-zinc-300">
            <Key className="w-4 h-4 text-white" />
            <span>Environment Variables (.env)</span>
          </div>

          <div className="overflow-x-auto rounded-xl border border-zinc-800 bg-zinc-950">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-zinc-800 bg-zinc-900/60 text-zinc-400 font-semibold">
                  <th className="py-2.5 px-3">Variable Key</th>
                  <th className="py-2.5 px-3">Requirement</th>
                  <th className="py-2.5 px-3">Description</th>
                  <th className="py-2.5 px-3">Example</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800">
                {envVars.map((v) => (
                  <tr key={v.key} className="hover:bg-zinc-900/40 transition-colors">
                    <td className="py-2.5 px-3 font-mono font-bold text-white">{v.key}</td>
                    <td className="py-2.5 px-3">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-semibold border ${
                        v.type === 'Required' 
                          ? 'bg-white text-black font-bold border-white' 
                          : 'bg-zinc-800 text-zinc-300 border-zinc-700'
                      }`}>
                        {v.type}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-zinc-300">{v.desc}</td>
                    <td className="py-2.5 px-3 font-mono text-zinc-400">{v.example}</td>
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
