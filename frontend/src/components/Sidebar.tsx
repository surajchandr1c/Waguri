'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { 
  Bot, 
  Home, 
  Menu, 
  X, 
  ExternalLink,
  Sliders,
  Send,
  Users,
  Sticker,
  Megaphone,
  Quote,
  LogOut,
  Loader2
} from 'lucide-react';

export default function Sidebar() {
  const pathname = usePathname();
  const [isOpen, setIsOpen] = useState(false);
  const [userCount, setUserCount] = useState<number | null>(null);
  const [loggingOut, setLoggingOut] = useState(false);

  const handleLogout = async () => {
    setLoggingOut(true);
    try {
      await fetch('/api/admin/logout', { method: 'POST' });
    } catch (err) {
      console.error('Logout error in sidebar:', err);
    } finally {
      window.location.href = '/login';
    }
  };

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

  // Fetch user count badge
  useEffect(() => {
    let isMounted = true;
    async function fetchUserCount() {
      try {
        const res = await fetch('/api/users');
        if (res.ok) {
          const data = await res.json();
          if (isMounted && typeof data.totalUsers === 'number') {
            setUserCount(data.totalUsers);
          }
        }
      } catch (err) {
        console.error('Failed to load user count for sidebar:', err);
      }
    }
    fetchUserCount();
    return () => {
      isMounted = false;
    };
  }, []);

  const navItems = [
    {
      name: 'Overview',
      path: '/',
      icon: Home,
      badge: 'Live',
    },
    {
      name: 'Promotions',
      path: '/promotions',
      icon: Megaphone,
      badge: 'All GCs',
      highlight: true,
    },
    {
      name: 'Stickers',
      path: '/stickers',
      icon: Sticker,
      badge: 'GC Bot',
      highlight: true,
    },
    {
      name: 'Shayari & Vault',
      path: '/shayari',
      icon: Quote,
      badge: '7 Cats',
      highlight: true,
    },
    {
      name: 'Users & Chats',
      path: '/users',
      icon: Users,
      badge: userCount !== null ? `${userCount}` : 'Live',
      highlight: true,
    },
    {
      name: 'Settings & Config',
      path: '/settings',
      icon: Sliders,
    },
  ];

  return (
    <>
      {/* Unified Mobile Top Navigation Bar (< lg screens) */}
      <nav
        aria-label="Mobile Navigation"
        className="lg:hidden sticky top-0 z-40 bg-zinc-950/95 backdrop-blur-md border-b border-zinc-800 px-3 sm:px-4 py-2.5 sm:py-3 flex items-center justify-between w-full shrink-0"
      >
        <div className="flex items-center gap-2 sm:gap-3 min-w-0">
          <button
            onClick={() => setIsOpen(true)}
            className="p-2 rounded-xl bg-zinc-900 text-zinc-200 border border-zinc-800 hover:bg-zinc-800 active:scale-95 transition-all focus:outline-none cursor-pointer shrink-0"
            aria-label="Open navigation menu"
          >
            <Menu className="w-5 h-5" />
          </button>

          <Link href="/" className="flex items-center gap-2 min-w-0">
            <div className="w-8 h-8 rounded-lg bg-white flex items-center justify-center text-black font-bold shadow-sm shrink-0">
              <Bot className="w-5 h-5 text-black" />
            </div>
            <div className="truncate">
              <span className="font-bold text-sm text-white tracking-tight">Waguri</span>
              <span className="ml-1 text-[9px] font-semibold px-1 py-0.5 rounded bg-zinc-800 text-zinc-300 border border-zinc-700">
                v2.0
              </span>
            </div>
          </Link>
        </div>

        <div className="flex items-center gap-1.5 sm:gap-2 shrink-0">
          <Link
            href="/users"
            className="flex items-center gap-1.5 px-2.5 sm:px-3 py-1.5 rounded-lg bg-zinc-800 text-white border border-zinc-700 text-xs font-semibold hover:bg-zinc-700 transition-colors shrink-0"
          >
            <Users className="w-3.5 h-3.5 text-zinc-300" />
            <span className="hidden min-[390px]:inline">User Panel</span>
            <span className="min-[390px]:hidden">Users</span>
          </Link>

          <a
            href="https://t.me/Ms_Waguri_bot"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 px-2.5 sm:px-3 py-1.5 rounded-lg bg-white hover:bg-zinc-200 text-black text-xs font-bold shadow-sm transition-all shrink-0"
          >
            <Send className="w-3 h-3 text-black" />
            <span className="hidden min-[420px]:inline">Telegram</span>
            <span className="min-[420px]:hidden">Bot</span>
          </a>
        </div>
      </nav>

      {/* Backdrop for Mobile Drawer */}
      {isOpen && (
        <div 
          onClick={() => setIsOpen(false)}
          className="lg:hidden fixed inset-0 bg-black/80 backdrop-blur-sm z-50 transition-opacity animate-in fade-in duration-200"
          aria-hidden="true"
        />
      )}

      {/* Sidebar Container */}
      <aside
        className={`fixed top-0 bottom-0 left-0 z-50 w-72 max-w-[85vw] bg-zinc-950 border-r border-zinc-800 flex flex-col transition-transform duration-300 ease-in-out lg:translate-x-0 custom-scrollbar ${
          isOpen ? 'translate-x-0 shadow-2xl' : '-translate-x-full'
        }`}
      >
        {/* Logo & Brand Header with Mobile Close Button */}
        <div className="p-4 sm:p-5 border-b border-zinc-800 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-3 group" onClick={() => setIsOpen(false)}>
            <div className="w-10 h-10 rounded-xl bg-white flex items-center justify-center text-black font-bold shadow-md group-hover:scale-105 transition-transform">
              <Bot className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-lg text-white tracking-tight">Waguri Bot</span>
                <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-300 border border-zinc-700">
                  v2.0
                </span>
              </div>
              <p className="text-xs text-zinc-400 font-mono">@Ms_Waguri_bot</p>
            </div>
          </Link>

          {/* Close button for mobile drawer */}
          <button
            onClick={() => setIsOpen(false)}
            className="lg:hidden p-1.5 rounded-lg text-zinc-400 hover:text-white hover:bg-zinc-800 transition-colors"
            aria-label="Close menu"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Live Bot Status Pill */}
        <div className="px-4 sm:px-5 py-3">
          <div className="flex items-center justify-between px-3.5 py-2 rounded-xl bg-zinc-900 border border-zinc-800 text-xs">
            <div className="flex items-center gap-2">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-white opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-white"></span>
              </span>
              <span className="text-zinc-300 font-medium">Telegram Polling</span>
            </div>
            <span className="text-[11px] text-zinc-200 font-medium font-mono">Active</span>
          </div>
        </div>

        {/* Navigation Section */}
        <div className="flex-1 px-3 py-2 space-y-1 overflow-y-auto custom-scrollbar">
          <div className="px-3 pb-1 pt-2 text-[11px] font-semibold text-zinc-500 tracking-wider uppercase">
            Navigation Menu
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
                    ? 'bg-zinc-800 text-white border border-zinc-700 shadow-sm'
                    : 'text-zinc-400 hover:text-white hover:bg-zinc-900 border border-transparent'
                }`}
              >
                <div className="flex items-center gap-3">
                  <div
                    className={`p-1.5 rounded-lg transition-colors ${
                      isActive 
                        ? 'bg-white text-black' 
                        : 'bg-zinc-900 text-zinc-400 group-hover:text-white'
                    }`}
                  >
                    <Icon className="w-4 h-4" />
                  </div>
                  <span className={isActive ? 'font-semibold text-white' : ''}>{item.name}</span>
                </div>
                <span
                  className={`text-[11px] px-2 py-0.5 rounded-full font-mono transition-colors ${
                    isActive
                      ? 'bg-white text-black font-bold'
                      : 'bg-zinc-900 text-zinc-400 border border-zinc-800'
                  }`}
                >
                  {item.badge}
                </span>
              </Link>
            );
          })}
        </div>

        {/* Admin Session & Sign Out */}
        <div className="px-4 py-3 border-t border-zinc-800/80 bg-zinc-950/60">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-purple-400">Admin Session</span>
            <span className="inline-block w-2 h-2 rounded-full bg-emerald-400"></span>
          </div>
          <button
            onClick={handleLogout}
            disabled={loggingOut}
            className="w-full flex items-center justify-center gap-2 py-2 px-3 rounded-xl bg-zinc-900 hover:bg-red-950/40 text-zinc-300 hover:text-red-300 border border-zinc-800 hover:border-red-500/30 text-xs font-semibold transition-all cursor-pointer disabled:opacity-50"
          >
            {loggingOut ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin text-red-400" />
            ) : (
              <LogOut className="w-3.5 h-3.5 text-red-400" />
            )}
            <span>Sign Out</span>
          </button>
        </div>

        {/* Telegram Direct Link & Footer */}
        <div className="p-4 border-t border-zinc-800 space-y-3 bg-zinc-950">
          <a
            href="https://t.me/Ms_Waguri_bot"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center justify-center gap-2 w-full py-2.5 px-3 rounded-xl bg-white hover:bg-zinc-200 text-black text-xs font-bold shadow-md transition-all"
          >
            <Send className="w-3.5 h-3.5 text-black" />
            <span>Open in Telegram</span>
            <ExternalLink className="w-3 h-3 ml-auto opacity-70" />
          </a>

          <div className="px-2 pt-1 flex items-center justify-between text-[11px] text-zinc-400">
            <span>Support:</span>
            <a
              href="https://t.me/lucky_paji"
              target="_blank"
              rel="noopener noreferrer"
              className="text-zinc-200 hover:text-white hover:underline font-mono"
            >
              @lucky_paji
            </a>
          </div>
        </div>
      </aside>
    </>
  );
}