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
    <header className="relative lg:sticky lg:top-0 z-20 bg-zinc-950/90 backdrop-blur-md border-b border-zinc-800/80 px-4 sm:px-8 py-3.5 sm:py-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 sm:gap-4 max-w-7xl mx-auto">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-lg sm:text-2xl font-bold text-white tracking-tight break-words">{title}</h1>
            {badge && (
              <span className="px-2.5 py-0.5 rounded-full text-[10px] sm:text-xs font-semibold bg-zinc-800 text-zinc-200 border border-zinc-700 whitespace-nowrap">
                {badge}
              </span>
            )}
          </div>
          {description && (
            <p className="text-xs sm:text-sm text-zinc-400 mt-1 line-clamp-2 sm:line-clamp-none">
              {description}
            </p>
          )}
        </div>

        <div className="flex items-center gap-2 self-start sm:self-auto shrink-0">
          <div className="hidden md:flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-zinc-900 border border-zinc-800 text-xs text-zinc-300">
            <ShieldCheck className="w-3.5 h-3.5 text-zinc-400" />
            <span>MongoDB Atlas</span>
          </div>

          <a
            href="https://t.me/Ms_Waguri_bot"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-white hover:bg-zinc-200 text-black text-xs font-bold shadow-sm transition-all whitespace-nowrap"
          >
            <Send className="w-3 h-3 text-black" />
            <span>Launch Bot</span>
          </a>
        </div>
      </div>
    </header>
  );
}
