'use client';

import React from 'react';
import Header from '@/components/Header';
import CommandCard from '@/components/CommandCard';
import { BOT_COMMANDS } from '@/data/commands';
import { Shield, Sliders } from 'lucide-react';

export default function GroupManagementPage() {
  const managementCommands = BOT_COMMANDS.filter((cmd) => cmd.category === 'group-management');

  const featureToggles = [
    { name: 'anti_link_enabled', alias: 'antilink', desc: 'Deletes unauthorized URLs, invites, and deep links' },
    { name: 'anti_spam_enabled', alias: 'antispam', desc: 'Enforces 4-stage progressive spam muting' },
    { name: 'anti_bio_link_enabled', alias: 'antibiolink', desc: 'Checks sender user bios for promotional links' },
    { name: 'clean_service_enabled', alias: 'cleanservice', desc: 'Deletes joins, leaves, pins, and video chat notices' },
    { name: 'flood_protection_enabled', alias: 'flood', desc: 'Restricts burst messaging over 5 msgs/3 seconds' },
    { name: 'media_restrictions_enabled', alias: 'media', desc: 'Restricts photos, stickers, voice notes, documents' },
    { name: 'anti_forward_enabled', alias: 'antiforward', desc: 'Blocks forwarded messages from external channels' },
    { name: 'raid_mode_enabled', alias: 'raid', desc: 'Locks chat and restricts all incoming new members' },
  ];

  return (
    <div className="flex-1 flex flex-col">
      <Header
        title="Group Management Commands"
        description="Interactive dashboards, live moderation audit logs, and chat feature controls for group administrators."
        badge="Scope: Admins Only"
      />

      <div className="flex-1 p-3.5 sm:p-6 lg:p-8 max-w-7xl mx-auto w-full space-y-6 sm:space-y-8">
        {/* Admin RBAC Banner */}
        <div className="p-4 sm:p-6 rounded-3xl bg-slate-900/60 border border-slate-800/80 shadow-md">
          <div className="flex items-start gap-3.5 sm:gap-4">
            <div className="p-2.5 sm:p-3 rounded-2xl bg-sky-500/10 text-sky-400 border border-sky-500/20 shrink-0">
              <Shield className="w-5 h-5 sm:w-6 sm:h-6" />
            </div>
            <div className="space-y-1">
              <h2 className="text-base sm:text-lg font-bold text-white tracking-tight">
                Server-Side Admin Verification
              </h2>
              <p className="text-xs sm:text-sm text-slate-300 leading-relaxed">
                All group management commands verify caller privileges server-side using Telegram API checks (<code>OWNER</code> or <code>ADMINISTRATOR</code> status). Anonymous channel senders are automatically cross-checked, and non-admins are blocked with friendly permission alerts.
              </p>
            </div>
          </div>
        </div>

        {/* Command Cards Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-6">
          {managementCommands.map((item) => (
            <CommandCard key={item.command} item={item} />
          ))}
        </div>

        {/* Feature Toggle Syntax Guide */}
        <div className="p-5 sm:p-8 rounded-3xl bg-slate-900/40 border border-slate-800 space-y-4 sm:space-y-6">
          <div>
            <h3 className="text-sm sm:text-base font-bold text-white tracking-tight flex items-center gap-2">
              <Sliders className="w-4 h-4 text-sky-400 shrink-0" />
              <span>Available Feature Modules for /enable & /disable</span>
            </h3>
            <p className="text-xs text-slate-400 mt-1">
              Toggle features using <code>/enable &lt;name&gt;</code>, <code>/disable &lt;name&gt;</code>, or via the interactive <code>/settings</code> panel.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {featureToggles.map((f, i) => (
              <div key={i} className="p-3 sm:p-3.5 rounded-xl bg-slate-950 border border-slate-800 space-y-1">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs font-semibold text-sky-300">{f.alias}</span>
                  <span className="text-[10px] text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded">Ready</span>
                </div>
                <p className="text-[11px] text-slate-400 leading-normal">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
