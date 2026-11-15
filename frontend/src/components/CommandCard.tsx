'use client';

import React, { useState } from 'react';
import { 
  Copy, 
  Check, 
  Terminal, 
  ShieldAlert, 
  UserCheck, 
  Briefcase, 
  ChevronDown, 
  ChevronUp, 
  Bot,
  Sparkles
} from 'lucide-react';
import { BotCommandItem } from '@/data/commands';

interface CommandCardProps {
  item: BotCommandItem;
}

export default function CommandCard({ item }: CommandCardProps) {
  const [copied, setCopied] = useState(false);
  const [showPreview, setShowPreview] = useState(false);

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const getPermissionBadge = (perm: string) => {
    switch (perm) {
      case 'Admin':
        return {
          bg: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
          icon: ShieldAlert,
          label: 'Admin Only',
        };
      case 'Connected User':
        return {
          bg: 'bg-purple-500/10 text-purple-400 border-purple-500/20',
          icon: Briefcase,
          label: 'Connected Account',
        };
      case 'Owner':
        return {
          bg: 'bg-rose-500/10 text-rose-400 border-rose-500/20',
          icon: ShieldAlert,
          label: 'Group Owner',
        };
      default:
        return {
          bg: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
          icon: UserCheck,
          label: 'All Members',
        };
    }
  };

  const badgeInfo = getPermissionBadge(item.permission);
  const PermIcon = badgeInfo.icon;

  return (
    <div className="rounded-2xl bg-slate-900/60 border border-slate-800/80 hover:border-slate-700/80 transition-all shadow-md hover:shadow-xl p-4 sm:p-5 flex flex-col justify-between group overflow-hidden">
      <div>
        {/* Header row: Command & Permissions (Mobile Wrap) */}
        <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
          <div className="flex items-center gap-2 min-w-0">
            <span className="font-mono font-bold text-base sm:text-lg text-white group-hover:text-indigo-400 transition-colors truncate">
              {item.command}
            </span>
            {item.badge && (
              <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 shrink-0">
                {item.badge}
              </span>
            )}
          </div>

          <div className="flex items-center gap-1.5 shrink-0">
            <span
              className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-medium border ${badgeInfo.bg}`}
            >
              <PermIcon className="w-3 h-3 shrink-0" />
              <span>{badgeInfo.label}</span>
            </span>

            <button
              onClick={() => handleCopy(item.syntax)}
              className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-colors border border-slate-700/50"
              title="Copy syntax"
              aria-label={`Copy command ${item.command}`}
            >
              {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
            </button>
          </div>
        </div>

        {/* Short & Long Description */}
        <p className="text-xs sm:text-sm font-medium text-slate-200 mb-1">{item.shortDesc}</p>
        <p className="text-[11px] sm:text-xs text-slate-400 leading-relaxed mb-4 break-words">{item.description}</p>

        {/* Parameters pill list if available */}
        {item.parameters && item.parameters.length > 0 && (
          <div className="mb-4">
            <div className="text-[10px] sm:text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-1.5">
              Available Options
            </div>
            <div className="flex flex-wrap gap-1.5">
              {item.parameters.map((param, i) => (
                <span
                  key={i}
                  className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-mono text-[10px] sm:text-[11px] border border-slate-700/60"
                >
                  {param}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Syntax Code Block with safe scrollbar */}
        <div className="rounded-xl bg-slate-950 p-2.5 sm:p-3 border border-slate-800 font-mono text-xs text-indigo-300 flex items-center justify-between gap-2 mb-3 min-w-0">
          <div className="flex items-center gap-2 overflow-x-auto custom-scrollbar min-w-0 py-0.5">
            <span className="text-slate-500 select-none shrink-0">$</span>
            <span className="whitespace-nowrap">{item.syntax}</span>
          </div>
          <button
            onClick={() => handleCopy(item.example)}
            className="text-[10px] sm:text-[11px] text-slate-400 hover:text-indigo-300 flex items-center gap-1 transition-colors whitespace-nowrap ml-2 shrink-0"
          >
            <Copy className="w-3 h-3" />
            <span className="hidden xs:inline">Copy Ex</span>
          </button>
        </div>
      </div>

      {/* Telegram Live Output Preview Dropdown */}
      <div className="border-t border-slate-800/80 pt-3 mt-1">
        <button
          onClick={() => setShowPreview(!showPreview)}
          className="flex items-center justify-between w-full text-xs font-medium text-slate-400 hover:text-slate-200 transition-colors"
        >
          <span className="flex items-center gap-1.5">
            <Bot className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
            <span className="truncate">Telegram Response Preview</span>
          </span>
          {showPreview ? <ChevronUp className="w-3.5 h-3.5 shrink-0" /> : <ChevronDown className="w-3.5 h-3.5 shrink-0" />}
        </button>

        {showPreview && (
          <div className="mt-2.5 p-3 rounded-xl bg-slate-950/90 border border-slate-800/90 text-xs text-slate-300 font-sans shadow-inner">
            <div className="flex items-center gap-2 mb-2 pb-1.5 border-b border-slate-800/60">
              <div className="w-5 h-5 rounded-full bg-gradient-to-tr from-indigo-500 to-purple-600 flex items-center justify-center text-white text-[10px] font-bold shrink-0">
                W
              </div>
              <span className="font-semibold text-white text-xs">Waguri</span>
              <span className="text-[10px] text-indigo-400 bg-indigo-500/10 px-1 rounded">bot</span>
              <span className="text-[10px] text-slate-500 ml-auto">just now</span>
            </div>
            <div className="whitespace-pre-wrap break-words font-sans text-slate-200 leading-relaxed text-[11px] sm:text-[12px] bg-slate-900/60 p-2.5 rounded-lg border border-slate-800/40">
              {item.previewOutput}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
