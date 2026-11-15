'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { 
  Search, 
  Terminal, 
  Shield, 
  Zap, 
  Briefcase, 
  Sparkles, 
  Bot, 
  ArrowRight, 
  CheckCircle2, 
  Copy, 
  Send,
  Database,
  Cpu,
  Layers
} from 'lucide-react';
import Header from '@/components/Header';
import CommandCard from '@/components/CommandCard';
import { BOT_COMMANDS, CATEGORIES } from '@/data/commands';

export default function HomePage() {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedFilter, setSelectedFilter] = useState<'all' | 'general' | 'group-management' | 'moderation' | 'personal-autoreply'>('all');

  const filteredCommands = BOT_COMMANDS.filter((cmd) => {
    const matchesCategory = selectedFilter === 'all' || cmd.category === selectedFilter;
    const matchesSearch =
      cmd.command.toLowerCase().includes(searchQuery.toLowerCase()) ||
      cmd.shortDesc.toLowerCase().includes(searchQuery.toLowerCase()) ||
      cmd.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
      cmd.syntax.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesCategory && matchesSearch;
  });

  return (
    <div className="flex-1 flex flex-col">
      <Header
        title="Waguri Bot Command Center"
        description="Explore, search, and preview commands for Telegram Group Moderation & Personal Business Secretary Mode."
        badge="Live Dashboard"
      />

      <div className="flex-1 p-3.5 sm:p-6 lg:p-8 max-w-7xl mx-auto w-full space-y-8 sm:space-y-10">
        {/* Responsive Hero Section */}
        <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-indigo-950/70 via-slate-900 to-slate-950 border border-indigo-500/20 p-5 sm:p-8 lg:p-10 shadow-2xl">
          <div className="absolute top-0 right-0 w-80 h-80 bg-indigo-600/10 rounded-full blur-3xl pointer-events-none" />
          <div className="absolute bottom-0 left-1/3 w-64 h-64 bg-purple-600/10 rounded-full blur-2xl pointer-events-none" />

          <div className="relative z-10 max-w-3xl space-y-3.5 sm:space-y-4">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-500/10 text-indigo-300 border border-indigo-500/20 text-xs font-semibold">
              <Sparkles className="w-3.5 h-3.5 shrink-0" />
              <span className="truncate">Multi-Tenant Group & Telegram Business Bot</span>
            </div>

            <h1 className="text-2xl sm:text-4xl lg:text-5xl font-black text-white tracking-tight leading-tight break-words">
              Enterprise Moderation & <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 via-purple-300 to-pink-400">Personal Auto-Reply</span>
            </h1>

            <p className="text-xs sm:text-sm lg:text-base text-slate-300 leading-relaxed">
              Waguri (@Ms_Waguri_bot) delivers high-performance automated group moderation alongside an isolated multi-user Telegram Business Secretary mode for personal accounts.
            </p>

            <div className="flex flex-wrap items-center gap-2.5 sm:gap-3 pt-2">
              <a
                href="https://t.me/Ms_Waguri_bot"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center justify-center gap-2 px-4 sm:px-5 py-2.5 rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white text-xs sm:text-sm font-semibold shadow-lg shadow-indigo-500/25 transition-all w-full sm:w-auto"
              >
                <Send className="w-4 h-4" />
                <span>Launch in Telegram</span>
              </a>

              <Link
                href="/personal-autoreply"
                className="flex items-center justify-center gap-2 px-4 sm:px-5 py-2.5 rounded-xl bg-slate-800/80 hover:bg-slate-700/80 text-slate-200 text-xs sm:text-sm font-medium border border-slate-700 transition-colors w-full sm:w-auto"
              >
                <Briefcase className="w-4 h-4 text-purple-400" />
                <span>Secretary Mode Guide</span>
              </Link>
            </div>
          </div>

          {/* Quick Metrics Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-4 mt-6 sm:mt-8 pt-6 sm:pt-8 border-t border-slate-800/80">
            <div className="p-2 sm:p-0">
              <div className="text-xl sm:text-3xl font-extrabold text-white font-mono">33</div>
              <div className="text-[11px] sm:text-xs text-slate-400 mt-0.5">Total Commands</div>
            </div>
            <div className="p-2 sm:p-0">
              <div className="text-xl sm:text-3xl font-extrabold text-indigo-400 font-mono">4</div>
              <div className="text-[11px] sm:text-xs text-slate-400 mt-0.5">Core Modules</div>
            </div>
            <div className="p-2 sm:p-0">
              <div className="text-xl sm:text-3xl font-extrabold text-purple-400 font-mono">100%</div>
              <div className="text-[11px] sm:text-xs text-slate-400 mt-0.5">Tenant Isolation</div>
            </div>
            <div className="p-2 sm:p-0">
              <div className="text-xl sm:text-3xl font-extrabold text-emerald-400 font-mono">0ms</div>
              <div className="text-[11px] sm:text-xs text-slate-400 mt-0.5">Fast SQLite</div>
            </div>
          </div>
        </div>

        {/* Categories Section */}
        <div>
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-lg sm:text-xl font-bold text-white tracking-tight">Command Categories</h2>
              <p className="text-xs text-slate-400">Select any section to inspect specific commands and syntax</p>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-5">
            {CATEGORIES.map((cat) => (
              <Link
                key={cat.id}
                href={cat.path}
                className="p-4 sm:p-5 rounded-2xl bg-slate-900/60 hover:bg-slate-900 border border-slate-800/80 hover:border-indigo-500/40 transition-all shadow-md hover:shadow-xl group flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-2xl">{cat.emoji}</span>
                    <span className="text-[11px] font-mono font-semibold px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 border border-slate-700/60">
                      {cat.count} commands
                    </span>
                  </div>
                  <h3 className="text-sm sm:text-base font-bold text-white group-hover:text-indigo-400 transition-colors mb-1">
                    {cat.name}
                  </h3>
                  <p className="text-xs text-slate-400 leading-relaxed mb-4">
                    {cat.description}
                  </p>
                </div>
                <div className="flex items-center gap-1.5 text-xs font-semibold text-indigo-400 group-hover:text-indigo-300 transition-colors">
                  <span>Explore Commands</span>
                  <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-1 transition-transform" />
                </div>
              </Link>
            ))}
          </div>
        </div>

        {/* Global Live Command Search & Filter */}
        <div className="space-y-4 pt-2">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <h2 className="text-lg sm:text-xl font-bold text-white tracking-tight">Interactive Command Finder</h2>
              <p className="text-xs text-slate-400">
                Live filtering across all {BOT_COMMANDS.length} bot commands
              </p>
            </div>

            {/* Filter Pills with Horizontal Swipe on Mobile */}
            <div className="flex gap-1.5 overflow-x-auto pb-1 sm:pb-0 custom-scrollbar -mx-1 px-1">
              {[
                { id: 'all', label: 'All (33)' },
                { id: 'general', label: 'General (4)' },
                { id: 'group-management', label: 'Management (7)' },
                { id: 'moderation', label: 'Moderation (12)' },
                { id: 'personal-autoreply', label: 'Secretary (10)' },
              ].map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setSelectedFilter(tab.id as any)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition-all shrink-0 ${
                    selectedFilter === tab.id
                      ? 'bg-indigo-600 text-white shadow-sm'
                      : 'bg-slate-900 hover:bg-slate-800 text-slate-400 hover:text-slate-200 border border-slate-800'
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          </div>

          {/* Search Input Bar */}
          <div className="relative">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search commands (e.g. /settings, /mute, /personal, /setmessage)..."
              className="w-full pl-10 pr-14 py-2.5 sm:py-3 rounded-2xl bg-slate-900/80 border border-slate-800 text-slate-200 text-xs sm:text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/50 placeholder:text-slate-500"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery('')}
                className="absolute right-3.5 top-1/2 -translate-y-1/2 text-xs text-slate-400 hover:text-slate-200 p-1"
              >
                Clear
              </button>
            )}
          </div>

          {/* Results Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-5 pt-2">
            {filteredCommands.length > 0 ? (
              filteredCommands.map((item) => (
                <CommandCard key={item.command} item={item} />
              ))
            ) : (
              <div className="col-span-full p-8 sm:p-12 text-center rounded-2xl bg-slate-900/40 border border-slate-800/80">
                <Terminal className="w-8 h-8 text-slate-600 mx-auto mb-3" />
                <p className="text-slate-300 font-medium text-sm">No commands match &quot;{searchQuery}&quot;</p>
                <p className="text-xs text-slate-500 mt-1">Try searching for keywords like link, spam, mute, or personal</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
