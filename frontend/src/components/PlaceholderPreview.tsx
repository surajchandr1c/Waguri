'use client';

import React, { useState } from 'react';
import { PLACEHOLDERS } from '@/data/commands';
import { Copy, Check, Sparkles, Bot, Send } from 'lucide-react';

export default function PlaceholderPreview() {
  const [template, setTemplate] = useState(
    'Hello {first_name}! 👋 Thanks for reaching out. I am currently busy, but I will get back to you shortly!'
  );
  const [copied, setCopied] = useState(false);

  // Sample sender mock data
  const sampleSender = {
    first_name: 'Alex',
    last_name: 'Taylor',
    full_name: 'Alex Taylor',
    username: '@alextaylor',
    time: '14:35 UTC',
    date: '2026-11-16',
  };

  const renderTemplate = (text: string) => {
    return text
      .replace(/{first_name}/g, sampleSender.first_name)
      .replace(/{last_name}/g, sampleSender.last_name)
      .replace(/{full_name}/g, sampleSender.full_name)
      .replace(/{username}/g, sampleSender.username)
      .replace(/{time}/g, sampleSender.time)
      .replace(/{date}/g, sampleSender.date);
  };

  const handleInsertPlaceholder = (placeholder: string) => {
    setTemplate((prev) => prev + ' ' + placeholder);
  };

  const handleCopyCommand = () => {
    navigator.clipboard.writeText(`/setmessage ${template}`);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const presets = [
    {
      title: 'Professional',
      text: 'Hello {first_name}! Thank you for reaching out. I am currently attending to client matters and will reply shortly.',
    },
    {
      title: 'Friendly',
      text: 'Hey {first_name}! Thanks for messaging me. I am away right now ({time}), but I will text you back soon! ✨',
    },
    {
      title: 'Support Notice',
      text: 'Hi {first_name}! For urgent requests, please email support@mycompany.com. Otherwise I will reply later today.',
    },
  ];

  return (
    <div className="rounded-3xl bg-slate-900/60 border border-slate-800 p-4 sm:p-6 shadow-xl space-y-6 overflow-hidden">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="p-2 rounded-xl bg-purple-500/10 text-purple-400 border border-purple-500/20 shrink-0">
              <Sparkles className="w-5 h-5" />
            </span>
            <h2 className="text-base sm:text-lg font-bold text-white tracking-tight">
              Interactive Message Template Simulator
            </h2>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Test how dynamic sender variables render in real-time before saving with <code>/setmessage</code>.
          </p>
        </div>

        {/* Copy /setmessage Command */}
        <button
          onClick={handleCopyCommand}
          className="flex items-center justify-center gap-2 px-3.5 py-2 rounded-xl bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white text-xs font-semibold shadow-md shadow-purple-500/20 transition-all w-full sm:w-auto"
        >
          {copied ? <Check className="w-4 h-4 text-emerald-300" /> : <Copy className="w-4 h-4" />}
          <span>{copied ? 'Command Copied!' : 'Copy /setmessage Command'}</span>
        </button>
      </div>

      {/* Preset Buttons */}
      <div>
        <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block mb-2">
          Quick Template Presets:
        </span>
        <div className="flex flex-wrap gap-2">
          {presets.map((preset, idx) => (
            <button
              key={idx}
              onClick={() => setTemplate(preset.text)}
              className="px-2.5 sm:px-3 py-1.5 rounded-lg bg-slate-800/80 hover:bg-slate-700 text-xs font-medium text-slate-300 hover:text-white border border-slate-700/60 transition-colors"
            >
              {preset.title}
            </button>
          ))}
        </div>
      </div>

      {/* Editor & Live Preview Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Editor Side */}
        <div className="space-y-3">
          <label className="text-xs font-semibold text-slate-300 block">
            Edit Message Template:
          </label>
          <textarea
            value={template}
            onChange={(e) => setTemplate(e.target.value)}
            rows={4}
            className="w-full p-3.5 sm:p-4 rounded-2xl bg-slate-950 border border-slate-800 text-slate-200 text-xs sm:text-sm focus:outline-none focus:ring-2 focus:ring-purple-500/50 resize-none font-mono"
            placeholder="Type your auto-reply message..."
          />

          {/* Placeholders quick pills */}
          <div>
            <span className="text-[11px] text-slate-400 block mb-1.5">
              Click to insert dynamic placeholder:
            </span>
            <div className="flex flex-wrap gap-1.5">
              {PLACEHOLDERS.map((p, i) => (
                <button
                  key={i}
                  onClick={() => handleInsertPlaceholder(p.variable)}
                  className="px-2 py-0.5 sm:px-2.5 sm:py-1 rounded-md bg-purple-500/10 hover:bg-purple-500/20 text-purple-300 border border-purple-500/30 font-mono text-[10px] sm:text-[11px] transition-colors"
                  title={p.desc}
                >
                  {p.variable}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Live Preview Side (Telegram Bubble) */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <label className="text-xs font-semibold text-slate-300">
              Live Telegram Chat Preview:
            </label>
            <span className="text-[11px] text-slate-400">Recipient View</span>
          </div>

          <div className="p-3.5 sm:p-4 rounded-2xl bg-slate-950 border border-slate-800/90 min-h-[160px] max-h-[260px] overflow-y-auto custom-scrollbar flex flex-col justify-end shadow-inner">
            <div className="flex items-start gap-2.5 max-w-[95%] sm:max-w-[85%] self-end">
              <div className="bg-gradient-to-r from-indigo-700 to-purple-800 p-3 sm:p-3.5 rounded-2xl rounded-tr-none text-white text-xs leading-relaxed shadow-md break-words min-w-0">
                <p className="whitespace-pre-wrap">{renderTemplate(template)}</p>
                <div className="flex items-center justify-end gap-1 mt-1.5 text-[10px] text-indigo-200">
                  <span>{sampleSender.time}</span>
                  <span>✓✓</span>
                </div>
              </div>
              <div className="w-6 h-6 sm:w-7 sm:h-7 rounded-full bg-gradient-to-tr from-indigo-500 to-purple-600 flex items-center justify-center text-white text-[11px] sm:text-xs font-bold shrink-0">
                W
              </div>
            </div>
          </div>

          <div className="text-[11px] text-slate-400 flex items-center gap-1.5">
            <Bot className="w-3.5 h-3.5 text-purple-400 shrink-0" />
            <span className="truncate">Simulated sender: Alex Taylor (@alextaylor)</span>
          </div>
        </div>
      </div>
    </div>
  );
}
