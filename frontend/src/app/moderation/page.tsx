'use client';

import React from 'react';
import Header from '@/components/Header';
import CommandCard from '@/components/CommandCard';
import { BOT_COMMANDS } from '@/data/commands';
import { Zap } from 'lucide-react';

export default function ModerationPenaltiesPage() {
  const moderationCommands = BOT_COMMANDS.filter((cmd) => cmd.category === 'moderation');

  const escalationStages = [
    {
      step: '1',
      title: 'First Message',
      action: 'Allowed',
      desc: 'First unique message is tracked in sliding window memory.',
      badge: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
    },
    {
      step: '2',
      title: 'Duplicate Detected',
      action: 'Warning 1/2',
      desc: 'Second identical message deleted; user warned.',
      badge: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
    },
    {
      step: '3',
      title: 'Third Duplicate',
      action: 'Warning 2/2',
      desc: 'Third identical message deleted; final warning issued.',
      badge: 'bg-orange-500/10 text-orange-400 border-orange-500/20',
    },
    {
      step: '4',
      title: 'Fourth Duplicate',
      action: '24h Mute & Cleanup',
      desc: 'User muted for 86,400s; all 3 prior spam messages deleted.',
      badge: 'bg-rose-500/10 text-rose-400 border-rose-500/20',
    },
  ];

  return (
    <div className="flex-1 flex flex-col">
      <Header
        title="Moderation & Penalties"
        description="Domain whitelists, keyword blacklists, warning tiers, temporary mutes, bans, and anti-spam protection."
        badge="12 Enforcement Commands"
      />

      <div className="flex-1 p-3.5 sm:p-6 lg:p-8 max-w-7xl mx-auto w-full space-y-6 sm:space-y-8">
        {/* Anti-Spam Sequence Visual Flow */}
        <div className="p-5 sm:p-8 rounded-3xl bg-slate-900/60 border border-slate-800 space-y-4">
          <div className="flex items-center gap-2">
            <span className="p-2 rounded-xl bg-amber-500/10 text-amber-400 border border-amber-500/20 shrink-0">
              <Zap className="w-5 h-5" />
            </span>
            <h2 className="text-base sm:text-lg font-bold text-white tracking-tight">
              Automated 4-Stage Progressive Spam Escalation
            </h2>
          </div>
          <p className="text-xs text-slate-400">
            Waguri protects group chats from flooding using cryptographic SHA-256 fingerprinting and sliding time windows.
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4 pt-2">
            {escalationStages.map((stage) => (
              <div key={stage.step} className="p-4 rounded-2xl bg-slate-950 border border-slate-800 space-y-2 relative">
                <div className="flex items-center justify-between">
                  <span className="w-6 h-6 rounded-full bg-slate-800 text-slate-300 flex items-center justify-center font-mono text-xs font-bold">
                    {stage.step}
                  </span>
                  <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${stage.badge}`}>
                    {stage.action}
                  </span>
                </div>
                <h3 className="text-xs sm:text-sm font-semibold text-white">{stage.title}</h3>
                <p className="text-xs text-slate-400 leading-relaxed">{stage.desc}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Command Cards Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-6">
          {moderationCommands.map((item) => (
            <CommandCard key={item.command} item={item} />
          ))}
        </div>
      </div>
    </div>
  );
}
