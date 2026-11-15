'use client';

import React from 'react';
import { ShieldCheck, Send } from 'lucide-react';

interface HeaderProps {
  title: string;
  description?: string;
  badge?: string;
}

export default function Header({ title, description, badge }: HeaderProps) {
  return (
    <header className="sticky top-0 z-20 bg-slate-950/80 backdrop-blur-md border-b border-slate-800/80 px-4 sm:px-8 py-3.5 sm:py-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 sm:gap-4 max-w-7xl mx-auto">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-lg sm:text-2xl font-bold text-white tracking-tight break-words">{title}</h1>
            {badge && (
              <span className="px-2.5 py-0.5 rounded-full text-[10px] sm:text-xs font-semibold bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 whitespace-nowrap">
                {badge}
              </span>
            )}
          </div>
          {description && (
            <p className="text-xs sm:text-sm text-slate-400 mt-1 line-clamp-2 sm:line-clamp-none">
              {description}
            </p>
          )}
        </div>

        <div className="flex items-center gap-2 self-start sm:self-auto shrink-0">
          <div className="hidden md:flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-xs text-slate-300">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
            <span>SQLite Multi-Tenant</span>
          </div>

          <a
            href="https://t.me/Ms_Waguri_bot"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-sm transition-all whitespace-nowrap"
          >
            <Send className="w-3 h-3" />
            <span>Launch Bot</span>
          </a>
        </div>
      </div>
    </header>
  );
}
