'use client';

import React, { useState, useEffect } from 'react';
import { 
  X, 
  Copy, 
  Check, 
  Briefcase, 
  Shield, 
  Zap, 
  AlertTriangle, 
  Trash2, 
  Link as LinkIcon, 
  Sparkles, 
  CheckCircle2, 
  Activity, 
  Layers,
  ShieldCheck,
  ShieldAlert,
  Radio,
  MessagesSquare,
  UserX
} from 'lucide-react';
import { BotUser, BotGroupChat, BotChannel } from '@/types/user';

export type AnyBotEntity = BotUser | BotGroupChat | BotChannel;

interface UserDetailModalProps {
  entity?: AnyBotEntity | null;
  user?: AnyBotEntity | null; // backward compatibility
  isOpen: boolean;
  onClose: () => void;
}

export default function UserDetailModal({ entity, user, isOpen, onClose }: UserDetailModalProps) {
  const currentEntity = entity || user;
  const [copiedId, setCopiedId] = useState(false);
  const [activeTab, setActiveTab] = useState<'features' | 'activity'>('features');
  const [removing, setRemoving] = useState(false);
  const [confirmRemove, setConfirmRemove] = useState(false);
  const [removeError, setRemoveError] = useState<string | null>(null);

  // Reset confirmation whenever opened or entity changes
  useEffect(() => {
    setConfirmRemove(false);
    setRemoveError(null);
    setRemoving(false);
  }, [isOpen, currentEntity]);

  // Handle ESC key press
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    if (isOpen) {
      window.addEventListener('keydown', handleKeyDown);
      document.body.style.overflow = 'hidden';
    }
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = '';
    };
  }, [isOpen, onClose]);

  if (!isOpen || !currentEntity) return null;

  // Determine entity kind
  const isGroup = 'chatId' in currentEntity;
  const isChannel = 'channelId' in currentEntity;
  const isUser = 'telegramId' in currentEntity;

  const entityId = isGroup 
    ? (currentEntity as BotGroupChat).chatId 
    : isChannel 
    ? (currentEntity as BotChannel).channelId 
    : (currentEntity as BotUser).telegramId;

  const displayName = isGroup || isChannel 
    ? (currentEntity as BotGroupChat | BotChannel).title 
    : `${(currentEntity as BotUser).firstName} ${(currentEntity as BotUser).lastName || ''}`.trim();

  const entityTypeLabel = isGroup 
    ? (currentEntity as BotGroupChat).type === 'supergroup' ? 'Supergroup (GC)' : 'Group Chat (GC)'
    : isChannel 
    ? 'Broadcast Channel' 
    : (currentEntity as BotUser).roleLabel;

  const username = isUser ? (currentEntity as BotUser).username : undefined;
  const initials = displayName ? displayName.slice(0, 2).toUpperCase() : 'TG';

  const handleCopyId = () => {
    navigator.clipboard.writeText(entityId.toString());
    setCopiedId(true);
    setTimeout(() => setCopiedId(false), 2000);
  };

  const getFeatureIcon = (iconName: string) => {
    switch (iconName) {
      case 'Briefcase': return Briefcase;
      case 'Sparkles': return Sparkles;
      case 'CheckCircle2': return CheckCircle2;
      case 'Shield': return Shield;
      case 'Zap': return Zap;
      case 'AlertTriangle': return AlertTriangle;
      case 'Trash2': return Trash2;
      case 'Link': return LinkIcon;
      case 'Radio': return Radio;
      case 'MessagesSquare': return MessagesSquare;
      default: return ShieldCheck;
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-5 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
      <div 
        className="w-full max-w-3xl max-h-[90vh] bg-zinc-950 border border-zinc-800 rounded-3xl shadow-2xl flex flex-col overflow-hidden animate-in zoom-in-95 duration-200"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header Section */}
        <div className="p-5 sm:p-6 border-b border-zinc-800 bg-zinc-900/80 flex items-start justify-between gap-4">
          <div className="flex items-center gap-3.5 sm:gap-4 min-w-0">
            {/* Avatar */}
            <div className="w-12 h-12 sm:w-14 sm:h-14 rounded-2xl bg-white flex items-center justify-center text-black font-extrabold text-base sm:text-lg shadow-md shrink-0">
              {initials}
            </div>

            {/* Title & Metadata */}
            <div className="min-w-0 space-y-1">
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-lg sm:text-xl font-bold text-white tracking-tight truncate">
                  {displayName}
                </h2>
                <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-zinc-800 text-zinc-200 border border-zinc-700 shrink-0">
                  {entityTypeLabel}
                </span>
              </div>

              <div className="flex flex-wrap items-center gap-2 text-xs text-zinc-400">
                {username && (
                  <span className="font-mono text-white">@{username}</span>
                )}
                {username && <span>•</span>}
                <div className="flex items-center gap-1 font-mono">
                  <span>ID: {entityId}</span>
                  <button
                    onClick={handleCopyId}
                    className="p-1 hover:text-white rounded transition-colors cursor-pointer"
                    title="Copy ID"
                  >
                    {copiedId ? <Check className="w-3.5 h-3.5 text-white" /> : <Copy className="w-3.5 h-3.5" />}
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* Close Button */}
          <button
            onClick={onClose}
            className="p-2 rounded-xl text-zinc-400 hover:text-white hover:bg-zinc-800 transition-colors shrink-0 cursor-pointer"
            aria-label="Close dialog"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Scrollable Body */}
        <div className="flex-1 overflow-y-auto custom-scrollbar p-5 sm:p-6 space-y-6">

          {/* Overview Metrics Cards */}
          {currentEntity.stats && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {Object.entries(currentEntity.stats).map(([k, v]) => {
                const label = k.replace(/([A-Z])/g, ' $1').replace(/^./, (s) => s.toUpperCase());
                return (
                  <div key={k} className="p-3.5 rounded-2xl bg-zinc-900 border border-zinc-800 space-y-1">
                    <span className="text-[10px] font-semibold text-zinc-400 uppercase tracking-wider block truncate">
                      {label}
                    </span>
                    <span className="text-xl font-black text-white font-mono">
                      {typeof v === 'number' ? v.toLocaleString() : v}
                    </span>
                  </div>
                );
              })}
            </div>
          )}

          {/* Tab Selector */}
          <div className="flex items-center gap-2 border-b border-zinc-800 pb-2">
            <button
              onClick={() => setActiveTab('features')}
              className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                activeTab === 'features'
                  ? 'bg-white text-black font-bold'
                  : 'text-zinc-400 hover:text-white hover:bg-zinc-900'
              }`}
            >
              <Layers className="w-3.5 h-3.5" />
              <span>Features in Use ({currentEntity.featuresUsed?.length || 0})</span>
            </button>

            {currentEntity.recentActivity && currentEntity.recentActivity.length > 0 && (
              <button
                onClick={() => setActiveTab('activity')}
                className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                  activeTab === 'activity'
                    ? 'bg-white text-black font-bold'
                    : 'text-zinc-400 hover:text-white hover:bg-zinc-900'
                }`}
              >
                <Activity className="w-3.5 h-3.5" />
                <span>Activity Timeline ({currentEntity.recentActivity.length})</span>
              </button>
            )}
          </div>

          {/* TAB 1: FEATURES IN USE */}
          {activeTab === 'features' && (
            <div className="space-y-4">
              <div className="grid grid-cols-1 gap-3.5">
                {currentEntity.featuresUsed?.map((feat) => {
                  const Icon = getFeatureIcon(feat.iconName);

                  return (
                    <div
                      key={feat.id}
                      className="p-4 rounded-2xl bg-zinc-900/60 border border-zinc-800 space-y-2.5"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="flex items-center gap-2.5">
                          <div className="p-2 rounded-xl bg-zinc-800 text-white border border-zinc-700">
                            <Icon className="w-4 h-4" />
                          </div>
                          <div>
                            <h4 className="text-sm font-bold text-white tracking-tight">{feat.name}</h4>
                            <span className="text-[10px] text-zinc-400 font-mono capitalize">
                              Scope: {feat.category.replace('-', ' ')}
                            </span>
                          </div>
                        </div>

                        <span className="text-[10px] font-semibold px-2 py-0.5 rounded-md bg-zinc-800 text-zinc-200 border border-zinc-700">
                          {feat.statusLabel || feat.status}
                        </span>
                      </div>

                      <p className="text-xs text-zinc-300 leading-relaxed">
                        {feat.description}
                      </p>

                      {feat.configDetails && Object.keys(feat.configDetails).length > 0 && (
                        <div className="mt-3 p-3 rounded-xl bg-black border border-zinc-800 space-y-2">
                          <span className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider block">
                            Configuration Details:
                          </span>
                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                            {Object.entries(feat.configDetails).map(([key, val]) => (
                              <div
                                key={key}
                                className="flex flex-col p-2 rounded-lg bg-zinc-900 border border-zinc-800"
                              >
                                <span className="text-[10px] text-zinc-400 font-medium">{key}</span>
                                <span className="font-mono text-zinc-200 text-xs break-words whitespace-pre-wrap mt-0.5">
                                  {String(val)}
                                </span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* TAB 2: ACTIVITY TIMELINE */}
          {activeTab === 'activity' && (
            <div className="space-y-4">
              <div className="relative pl-6 space-y-6 before:absolute before:left-2 before:top-2 before:bottom-2 before:w-0.5 before:bg-zinc-800">
                {currentEntity.recentActivity?.map((act) => (
                  <div key={act.id} className="relative group">
                    <div className="absolute -left-6 top-1 w-3.5 h-3.5 rounded-full border-2 border-black bg-white ring-2 ring-white/20" />

                    <div className="p-3.5 rounded-xl bg-zinc-900 border border-zinc-800 space-y-1">
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-xs font-bold text-white">{act.action}</span>
                        <span className="text-[10px] text-zinc-400 font-mono">{act.timestamp}</span>
                      </div>
                      <p className="text-xs text-zinc-300 leading-relaxed">{act.details}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

        </div>

        {/* Modal Footer */}
        <div className="p-4 sm:p-5 border-t border-zinc-800 bg-zinc-900/80 flex flex-wrap items-center justify-between gap-3">
          {/* Left: Remove Bot Button */}
          <div className="flex items-center gap-2">
            <button
              onClick={async () => {
                if (!confirmRemove) {
                  setConfirmRemove(true);
                  return;
                }
                try {
                  setRemoving(true);
                  setRemoveError(null);
                  const entityType = isGroup ? 'gc' : isChannel ? 'channel' : 'user';
                  const res = await fetch('/api/users', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ id: entityId, type: entityType }),
                  });
                  if (res.ok) {
                    window.dispatchEvent(
                      new CustomEvent('bot_entity_removed', {
                        detail: { id: entityId, type: entityType, title: displayName },
                      })
                    );
                    onClose();
                  } else {
                    const errJson = await res.json();
                    setRemoveError(errJson.error || 'Removal failed');
                  }
                } catch (err: any) {
                  setRemoveError(err.message || 'Network error');
                } finally {
                  setRemoving(false);
                }
              }}
              disabled={removing}
              className={`px-3 py-2 rounded-xl text-xs font-semibold flex items-center gap-1.5 transition-all active:scale-95 border cursor-pointer ${
                confirmRemove
                  ? 'bg-white text-black font-bold border-white'
                  : 'bg-zinc-800 hover:bg-zinc-700 text-zinc-200 border-zinc-700'
              }`}
              title="If user removed bot from this ID, GC, or channel, click to purge their data"
            >
              <UserX className="w-3.5 h-3.5" />
              <span>
                {removing
                  ? 'Removing Bot...'
                  : confirmRemove
                  ? `Confirm: Remove Bot from ${isGroup ? 'GC' : isChannel ? 'Channel' : 'User'}?`
                  : `Remove Bot from this ${isGroup ? 'GC' : isChannel ? 'Channel' : 'ID'}`}
              </span>
            </button>

            {confirmRemove && (
              <button
                onClick={() => setConfirmRemove(false)}
                className="px-2.5 py-2 rounded-xl text-xs text-zinc-400 hover:text-white bg-zinc-800 border border-zinc-700 cursor-pointer"
              >
                Cancel
              </button>
            )}

            {removeError && (
              <span className="text-[11px] text-zinc-300 font-mono">{removeError}</span>
            )}
          </div>

          <div className="flex items-center gap-3">
            <div className="hidden sm:flex items-center gap-2 text-xs text-zinc-400">
              <span className="w-2 h-2 rounded-full bg-white" />
              <span>Telemetry Connected</span>
            </div>

            <button
              onClick={onClose}
              className="px-4 py-2 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-white text-xs font-semibold border border-zinc-700 transition-colors cursor-pointer"
            >
              Close
            </button>
          </div>
        </div>

      </div>
    </div>
  );
}
