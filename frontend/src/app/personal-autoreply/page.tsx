'use client';

import React from 'react';
import Header from '@/components/Header';
import CommandCard from '@/components/CommandCard';
import PlaceholderPreview from '@/components/PlaceholderPreview';
import { BOT_COMMANDS, PLACEHOLDERS } from '@/data/commands';
import { Briefcase, Key, Clock, Ban, CheckCircle2, Sparkles } from 'lucide-react';

export default function PersonalAutoReplyPage() {
  const autoReplyCommands = BOT_COMMANDS.filter((cmd) => cmd.category === 'personal-autoreply');

  return (
    <div className="flex-1 flex flex-col">
      <Header
        title="Personal Auto-Reply (Telegram Business)"
        description="Multi-user Telegram Business Secretary Mode with first-time sender detection and custom dynamic templates."
        badge="Phase 2 Live"
      />

      <div className="flex-1 p-3.5 sm:p-6 lg:p-8 max-w-7xl mx-auto w-full space-y-8 sm:space-y-10">
        {/* Secretary Mode Overview Banner */}
        <div className="p-5 sm:p-8 rounded-3xl bg-gradient-to-br from-purple-950/70 via-slate-900 to-slate-950 border border-purple-500/20 shadow-xl space-y-4">
          <div className="flex items-center gap-2">
            <span className="p-2 rounded-xl bg-purple-500/10 text-purple-400 border border-purple-500/20 shrink-0">
              <Briefcase className="w-5 h-5" />
            </span>
            <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-purple-500/10 text-purple-300 border border-purple-500/20">
              Telegram Business Integration
            </span>
          </div>

          <h2 className="text-xl sm:text-2xl lg:text-3xl font-extrabold text-white tracking-tight break-words">
            How Personal Secretary Mode Works
          </h2>

          <p className="text-xs sm:text-sm text-slate-300 leading-relaxed max-w-3xl">
            Telegram Business allows subscribers to attach Waguri as an automated secretary bot. Every person connecting their business account gets <strong>complete tenant isolation</strong>: your custom templates, sender contact logs, and auto-reply toggles are private to your account and never shared with other users or group chats.
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3.5 sm:gap-4 pt-2">
            <div className="p-4 rounded-2xl bg-slate-950/80 border border-slate-800 space-y-1.5">
              <div className="flex items-center gap-2 text-purple-400 font-semibold text-xs">
                <CheckCircle2 className="w-4 h-4 shrink-0" />
                <span>First-Contact Detection</span>
              </div>
              <p className="text-[11px] text-slate-400 leading-relaxed">
                Waguri tracks each incoming sender and sends your auto-reply only once. Subsequent messages will never trigger annoying repeated auto-replies.
              </p>
            </div>

            <div className="p-4 rounded-2xl bg-slate-950/80 border border-slate-800 space-y-1.5">
              <div className="flex items-center gap-2 text-indigo-400 font-semibold text-xs">
                <Clock className="w-4 h-4 shrink-0" />
                <span>Optional Cooldown Mode</span>
              </div>
              <p className="text-[11px] text-slate-400 leading-relaxed">
                Prefer periodic follow-ups? Switch from first-time only to cooldown mode (1m, 10m, 1h, 24h, 7d) to re-reply only after an interval.
              </p>
            </div>

            <div className="p-4 rounded-2xl bg-slate-950/80 border border-slate-800 space-y-1.5">
              <div className="flex items-center gap-2 text-rose-400 font-semibold text-xs">
                <Ban className="w-4 h-4 shrink-0" />
                <span>Exclusion Blacklists</span>
              </div>
              <p className="text-[11px] text-slate-400 leading-relaxed">
                Use <code>/exclude_user</code> to prevent specific friends, bots, or coworkers from receiving automatic secretary replies.
              </p>
            </div>
          </div>
        </div>

        {/* Step-by-Step Connection Guide */}
        <div className="p-5 sm:p-8 rounded-3xl bg-slate-900/60 border border-slate-800 space-y-4">
          <h3 className="text-sm sm:text-base font-bold text-white tracking-tight flex items-center gap-2">
            <Key className="w-4 h-4 text-purple-400 shrink-0" />
            <span>How to Connect Your Telegram Business Account</span>
          </h3>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
            {[
              { step: '1', title: 'Open Settings', desc: 'In Telegram, go to Settings -> Telegram Business.' },
              { step: '2', title: 'Tap Chatbots', desc: 'Select Chatbots (or Business Bots).' },
              { step: '3', title: 'Select Waguri', desc: 'Search for and add @Ms_Waguri_bot.' },
              { step: '4', title: 'Enable Reply Rights', desc: 'Turn on "Reply to messages" permission and save.' },
            ].map((s) => (
              <div key={s.step} className="p-4 rounded-2xl bg-slate-950 border border-slate-800 space-y-1.5">
                <span className="w-6 h-6 rounded-full bg-purple-500/20 text-purple-300 border border-purple-500/30 flex items-center justify-center text-xs font-mono font-bold">
                  {s.step}
                </span>
                <h4 className="text-xs font-bold text-white">{s.title}</h4>
                <p className="text-[11px] text-slate-400 leading-relaxed">{s.desc}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Interactive Template Playground Simulator */}
        <PlaceholderPreview />

        {/* Supported Placeholders Table */}
        <div className="p-5 sm:p-8 rounded-3xl bg-slate-900/40 border border-slate-800 space-y-4">
          <h3 className="text-sm sm:text-base font-bold text-white tracking-tight flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-purple-400 shrink-0" />
            <span>Supported Message Variables</span>
          </h3>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {PLACEHOLDERS.map((p, i) => (
              <div key={i} className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 space-y-1">
                <div className="flex items-center justify-between">
                  <code className="text-xs font-bold text-purple-300 font-mono">{p.variable}</code>
                  <span className="text-[10px] text-slate-400 font-mono">{p.sample}</span>
                </div>
                <p className="text-xs text-slate-400">{p.desc}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Command Cards Grid */}
        <div>
          <h3 className="text-base font-bold text-white tracking-tight mb-4">
            Secretary Mode Command Reference
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-6">
            {autoReplyCommands.map((item) => (
              <CommandCard key={item.command} item={item} />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
