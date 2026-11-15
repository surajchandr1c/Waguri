'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { 
  Bot, 
  Terminal, 
  Shield, 
  Zap, 
  Briefcase, 
  Home, 
  Menu, 
  X, 
  ExternalLink,
  Sliders,
  Send
} from 'lucide-react';

export default function Sidebar() {
  const pathname = usePathname();
  const [isOpen, setIsOpen] = useState(false);

  // Close on Escape key press
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setIsOpen(false);
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Prevent background scroll when mobile sidebar is open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [isOpen]);

  const navItems = [
    {
      name: 'Overview',
      path: '/',
      icon: Home,
      badge: 'All',
      color: 'text-indigo-400',
    },
    {
      name: 'General Commands',
      path: '/general',
      icon: Terminal,
      badge: '4',
      color: 'text-emerald-400',
    },
    {
      name: 'Group Management',
      path: '/group-management',
      icon: Shield,
      badge: '7',
      color: 'text-sky-400',
    },
    {
      name: 'Moderation & Penalties',
      path: '/moderation',
      icon: Zap,
      badge: '12',
      color: 'text-amber-400',
    },
    {
      name: 'Personal Auto-Reply',
      path: '/personal-autoreply',
      icon: Briefcase,
      badge: '10',
      color: 'text-purple-400',
    },
    {
      name: 'Bot Config & Architecture',
      path: '/settings',
      icon: Sliders,
      badge: 'Info',
      color: 'text-rose-400',
    },
  ];

  return (
    <>
      {/* Unified Mobile Top Navigation Bar (< lg screens) */}
      <div className="lg:hidden sticky top-0 z-40 bg-slate-950/95 backdrop-blur-md border-b border-slate-800/80 px-4 py-3 flex items-center justify-between w-full">
        <div className="flex items-center gap-3">
          <button
            onClick={() => setIsOpen(true)}
            className="p-2 rounded-xl bg-slate-900 text-slate-200 border border-slate-800 hover:bg-slate-800 active:scale-95 transition-all focus:outline-none focus:ring-2 focus:ring-indigo-500"
            aria-label="Open navigation menu"
          >
            <Menu className="w-5 h-5" />
          </button>

          <Link href="/" className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-indigo-600 to-purple-600 flex items-center justify-center text-white shadow-sm">
              <Bot className="w-5 h-5" />
            </div>
            <div>
              <span className="font-bold text-sm text-white tracking-tight">Waguri</span>
              <span className="ml-1 text-[9px] font-semibold px-1 py-0.2 rounded bg-indigo-500/20 text-indigo-400 border border-indigo-500/30">
                v2.0
              </span>
            </div>
          </Link>
        </div>

        <a
          href="https://t.me/Ms_Waguri_bot"
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-sm transition-all"
        >
          <Send className="w-3 h-3" />
          <span>Telegram</span>
        </a>
      </div>

      {/* Backdrop for Mobile Drawer */}
      {isOpen && (
        <div 
          onClick={() => setIsOpen(false)}
          className="lg:hidden fixed inset-0 bg-black/70 backdrop-blur-sm z-50 transition-opacity animate-in fade-in duration-200"
          aria-hidden="true"
        />
      )}

      {/* Sidebar Container */}
      <aside
        className={`fixed top-0 bottom-0 left-0 z-50 w-72 bg-slate-950 border-r border-slate-800/80 flex flex-col transition-transform duration-300 ease-in-out lg:translate-x-0 no-scrollbar ${
          isOpen ? 'translate-x-0 shadow-2xl' : '-translate-x-full'
        }`}
      >
        {/* Logo & Brand Header with Mobile Close Button */}
        <div className="p-4 sm:p-5 border-b border-slate-800/80 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-3 group" onClick={() => setIsOpen(false)}>
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 via-purple-600 to-pink-500 flex items-center justify-center text-white shadow-lg shadow-indigo-500/20 group-hover:scale-105 transition-transform">
              <Bot className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-lg text-white tracking-tight">Waguri Bot</span>
                <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded bg-indigo-500/20 text-indigo-400 border border-indigo-500/30">
                  v2.0
                </span>
              </div>
              <p className="text-xs text-slate-400 font-mono">@Ms_Waguri_bot</p>
            </div>
          </Link>

          {/* Close button for mobile drawer */}
          <button
            onClick={() => setIsOpen(false)}
            className="lg:hidden p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
            aria-label="Close menu"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Live Bot Status Pill */}
        <div className="px-4 sm:px-5 py-3">
          <div className="flex items-center justify-between px-3.5 py-2 rounded-xl bg-slate-900/90 border border-slate-800/80 text-xs">
            <div className="flex items-center gap-2">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
              </span>
              <span className="text-slate-300 font-medium">Telegram Polling</span>
            </div>
            <span className="text-[11px] text-emerald-400 font-medium">Active</span>
          </div>
        </div>

        {/* Navigation Section (Scrollbar Hidden) */}
        <div className="flex-1 px-3 py-2 space-y-1 overflow-y-auto no-scrollbar">
          <div className="px-3 pb-1 pt-2 text-[11px] font-semibold text-slate-400 tracking-wider uppercase">
            Command Categories
          </div>

          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = pathname === item.path;

            return (
              <Link
                key={item.path}
                href={item.path}
                onClick={() => setIsOpen(false)}
                className={`flex items-center justify-between px-3.5 py-2.5 rounded-xl text-sm font-medium transition-all group ${
                  isActive
                    ? 'bg-gradient-to-r from-indigo-600/20 to-purple-600/10 text-white border border-indigo-500/30 shadow-sm'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/60 border border-transparent'
                }`}
              >
                <div className="flex items-center gap-3">
                  <div
                    className={`p-1.5 rounded-lg transition-colors ${
                      isActive ? 'bg-indigo-600 text-white shadow-sm' : 'bg-slate-900 text-slate-400 group-hover:text-white'
                    }`}
                  >
                    <Icon className="w-4 h-4" />
                  </div>
                  <span className={isActive ? 'font-semibold text-white' : ''}>{item.name}</span>
                </div>
                <span
                  className={`text-[11px] px-2 py-0.5 rounded-full font-mono transition-colors ${
                    isActive
                      ? 'bg-indigo-500/30 text-indigo-200 border border-indigo-400/30'
                      : 'bg-slate-900 text-slate-400 border border-slate-800'
                  }`}
                >
                  {item.badge}
                </span>
              </Link>
            );
          })}
        </div>

        {/* Telegram Direct Link & Footer */}
        <div className="p-4 border-t border-slate-800/80 space-y-3 bg-slate-950/80">
          <a
            href="https://t.me/Ms_Waguri_bot"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center justify-center gap-2 w-full py-2.5 px-3 rounded-xl bg-gradient-to-r from-sky-500 to-blue-600 hover:from-sky-400 hover:to-blue-500 text-white text-xs font-semibold shadow-md shadow-sky-500/20 transition-all"
          >
            <Send className="w-3.5 h-3.5" />
            <span>Open in Telegram</span>
            <ExternalLink className="w-3 h-3 ml-auto opacity-70" />
          </a>

          <div className="px-2 pt-1 flex items-center justify-between text-[11px] text-slate-400">
            <span>Support:</span>
            <a
              href="https://t.me/lucky_paji"
              target="_blank"
              rel="noopener noreferrer"
              className="text-indigo-400 hover:underline font-mono"
            >
              @lucky_paji
            </a>
          </div>
        </div>
      </aside>
    </>
  );
}
