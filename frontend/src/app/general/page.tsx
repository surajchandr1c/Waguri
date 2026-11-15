'use client';

import React from 'react';
import Header from '@/components/Header';
import CommandCard from '@/components/CommandCard';
import { BOT_COMMANDS } from '@/data/commands';
import { Terminal, HelpCircle } from 'lucide-react';

export default function GeneralCommandsPage() {
  const generalCommands = BOT_COMMANDS.filter((cmd) => cmd.category === 'general');

  return (
    <div className="flex-1 flex flex-col">
      <Header
        title="General Commands"
        description="Core utility commands available to all users in private chats and group chats."
        badge="Scope: Default"
      />

      <div className="flex-1 p-3.5 sm:p-6 lg:p-8 max-w-7xl mx-auto w-full space-y-6 sm:space-y-8">
        {/* Info Banner */}
        <div className="p-4 sm:p-6 rounded-3xl bg-slate-900/60 border border-slate-800/80 shadow-md">
          <div className="flex items-start gap-3.5 sm:gap-4">
            <div className="p-2.5 sm:p-3 rounded-2xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 shrink-0">
              <Terminal className="w-5 h-5 sm:w-6 sm:h-6" />
            </div>
            <div className="space-y-1">
              <h2 className="text-base sm:text-lg font-bold text-white tracking-tight">
                Public & Universal Commands
              </h2>
              <p className="text-xs sm:text-sm text-slate-300 leading-relaxed">
                These commands are accessible to any Telegram user without requiring administrative permissions. Waguri features contextual handling: running <code>/start</code> in private chats presents the rich personal dashboard, while in groups it replies with the official welcome message.
              </p>
            </div>
          </div>
        </div>

        {/* Command Cards Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 sm:gap-6">
          {generalCommands.map((item) => (
            <CommandCard key={item.command} item={item} />
          ))}
        </div>

        {/* Contextual Behavior Comparison */}
        <div className="p-4 sm:p-6 rounded-3xl bg-slate-900/40 border border-slate-800/80 space-y-4">
          <h3 className="text-sm sm:text-base font-bold text-white tracking-tight flex items-center gap-2">
            <HelpCircle className="w-4 h-4 text-emerald-400 shrink-0" />
            <span>Chat Context Matrix</span>
          </h3>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4">
            <div className="p-4 rounded-2xl bg-slate-950 border border-slate-800 space-y-2">
              <span className="text-[10px] sm:text-xs font-semibold px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                Private Chat (DM)
              </span>
              <p className="text-xs text-slate-300 leading-relaxed">
                Running <code>/start</code> opens the 8-button private dashboard with shortcuts to Add Waguri to Groups, View Managed Chats, Access Help, and configure Personal Auto-Reply.
              </p>
            </div>

            <div className="p-4 rounded-2xl bg-slate-950 border border-slate-800 space-y-2">
              <span className="text-[10px] sm:text-xs font-semibold px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                Group / Supergroup
              </span>
              <p className="text-xs text-slate-300 leading-relaxed">
                Running <code>/start</code> greets the group with: <em>&quot;Hi, welcome. I am Waguri. How can I help you&quot;</em>. Links sent in <code>/start</code> messages are filtered automatically.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
