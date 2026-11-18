'use client';

import React, { useState, useEffect } from 'react';
import Header from '@/components/Header';
import { 
  Megaphone, 
  Send, 
  Calendar, 
  Clock, 
  Repeat, 
  Globe, 
  Trash2, 
  Play, 
  Pause, 
  CheckCircle2, 
  AlertCircle, 
  RefreshCw, 
  Plus, 
  X,
  Pencil,
  ChevronDown,
  ChevronUp,
  Layers,
  Users
} from 'lucide-react';

interface ScheduledPromotion {
  id: number;
  title: string;
  message: string;
  link_url?: string | null;
  button_text?: string | null;
  target_type: 'all_gc' | 'selected';
  target_chat_ids?: string | null;
  schedule_type: 'once' | 'recurring';
  scheduled_time: string;
  repeat_interval: string;
  status: 'active' | 'paused' | 'completed';
  total_delivered: number;
  last_sent_at?: string | null;
  created_at?: string;
}

interface PromotionLog {
  id: number;
  promotion_id?: number;
  chat_id: number;
  chat_title: string;
  sent_at: string;
  status: string;
  details?: string;
}

interface ChatOption {
  chat_id: number;
  chat_title: string;
  chat_type: string;
}

const INTERVAL_OPTIONS = [
  { value: '3min', label: 'Every 3 Minutes' },
  { value: '5min', label: 'Every 5 Minutes' },
  { value: '10min', label: 'Every 10 Minutes' },
  { value: '15min', label: 'Every 15 Minutes' },
  { value: '30min', label: 'Every 30 Minutes' },
  { value: '1hr', label: 'Every 1 Hour' },
  { value: '2h', label: 'Every 2 Hours' },
  { value: '6h', label: 'Every 6 Hours' },
  { value: '12h', label: 'Every 12 Hours' },
  { value: 'daily', label: 'Daily (Every 24h)' },
  { value: 'weekly', label: 'Weekly (Every 7d)' },
];

export default function PromotionsPage() {
  const [promotions, setPromotions] = useState<ScheduledPromotion[]>([]);
  const [logs, setLogs] = useState<PromotionLog[]>([]);
  const [chats, setChats] = useState<ChatOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [broadcastingId, setBroadcastingId] = useState<number | null>(null);

  // UI state
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [filterTab, setFilterTab] = useState<'all' | 'active' | 'paused'>('all');
  const [showLogs, setShowLogs] = useState(false);
  const [notification, setNotification] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  // Create Form State
  const [title, setTitle] = useState('');
  const [message, setMessage] = useState('');
  const [linkUrl, setLinkUrl] = useState('');
  const [buttonText, setButtonText] = useState('Visit Website');
  const [targetType, setTargetType] = useState<'all_gc' | 'selected'>('all_gc');
  const [selectedChatIds, setSelectedChatIds] = useState<number[]>([]);
  const [scheduleType, setScheduleType] = useState<'recurring' | 'once'>('recurring');
  const [scheduledTime, setScheduledTime] = useState('');
  const [repeatInterval, setRepeatInterval] = useState('5min');
  const [showLinkFields, setShowLinkFields] = useState(false);

  // Edit State
  const [editingPromo, setEditingPromo] = useState<ScheduledPromotion | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [editMessage, setEditMessage] = useState('');
  const [editLinkUrl, setEditLinkUrl] = useState('');
  const [editButtonText, setEditButtonText] = useState('');
  const [editTargetType, setEditTargetType] = useState<'all_gc' | 'selected'>('all_gc');
  const [editSelectedChatIds, setEditSelectedChatIds] = useState<number[]>([]);
  const [editScheduleType, setEditScheduleType] = useState<'recurring' | 'once'>('recurring');
  const [editScheduledTime, setEditScheduledTime] = useState('');
  const [editRepeatInterval, setEditRepeatInterval] = useState('5min');
  const [editStatus, setEditStatus] = useState<'active' | 'paused' | 'completed'>('active');
  const [savingEdit, setSavingEdit] = useState(false);

  // Set default initial schedule time (next minute)
  useEffect(() => {
    const next = new Date(Date.now() + 60000);
    const isoLocal = new Date(next.getTime() - next.getTimezoneOffset() * 60000)
      .toISOString()
      .slice(0, 16);
    setScheduledTime(isoLocal);
  }, []);

  const fetchData = async () => {
    try {
      setRefreshing(true);
      const res = await fetch('/api/promotions');
      if (res.ok) {
        const data = await res.json();
        if (data.promotions) setPromotions(data.promotions);
        if (data.logs) setLogs(data.logs);
        if (data.chats) setChats(data.chats);
      }
    } catch (err) {
      console.error('Failed to load promotions:', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const showNotice = (type: 'success' | 'error', text: string) => {
    setNotification({ type, message: text });
    setTimeout(() => setNotification(null), 4000);
  };

  const groupChats = chats.filter((c) => c.chat_type === 'group' || c.chat_type === 'supergroup');

  const handleCreatePromotion = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!message.trim()) {
      showNotice('error', 'Please enter your promotion message.');
      return;
    }

    try {
      setSubmitting(true);
      const res = await fetch('/api/promotions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: 'add',
          title: title.trim() || 'Promotional Message',
          message: message.trim(),
          link_url: linkUrl.trim(),
          button_text: buttonText.trim() || 'Visit Website',
          target_type: targetType,
          target_chat_ids: targetType === 'selected' ? selectedChatIds : [],
          schedule_type: scheduleType,
          scheduled_time: scheduledTime || new Date().toISOString().slice(0, 16),
          repeat_interval: scheduleType === 'recurring' ? repeatInterval : 'none',
        }),
      });

      const data = await res.json();
      if (res.ok && data.success) {
        showNotice('success', 'Promotion scheduled successfully!');
        setMessage('');
        setTitle('');
        setLinkUrl('');
        setShowLinkFields(false);
        setIsFormOpen(false);
        fetchData();
      } else {
        showNotice('error', data.error || 'Failed to save promotion');
      }
    } catch (err: any) {
      showNotice('error', err.message || 'Network error occurred');
    } finally {
      setSubmitting(false);
    }
  };

  const handleBroadcastNow = async (id: number) => {
    try {
      setBroadcastingId(id);
      const res = await fetch('/api/promotions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'broadcast', id }),
      });
      const data = await res.json();
      if (res.ok && data.success) {
        showNotice('success', `Sent immediately to ${data.total_targets} group chat(s)!`);
        fetchData();
      } else {
        showNotice('error', data.error || 'Broadcast failed on Telegram');
      }
    } catch (err: any) {
      showNotice('error', err.message || 'Failed to send');
    } finally {
      setBroadcastingId(null);
    }
  };

  const handleToggleStatus = async (id: number, currentStatus: string) => {
    const newStatus = currentStatus === 'active' ? 'paused' : 'active';
    try {
      const res = await fetch('/api/promotions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'toggle', id, status: newStatus }),
      });
      if (res.ok) {
        setPromotions((prev) =>
          prev.map((p) => (p.id === id ? { ...p, status: newStatus as any } : p))
        );
        showNotice('success', `Promotion is now ${newStatus}`);
      }
    } catch (err) {
      console.error('Toggle status failed:', err);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Are you sure you want to delete this promotion?')) return;
    try {
      const res = await fetch('/api/promotions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'delete', id }),
      });
      if (res.ok) {
        setPromotions((prev) => prev.filter((p) => p.id !== id));
        showNotice('success', 'Promotion deleted.');
      }
    } catch (err) {
      console.error('Delete failed:', err);
    }
  };

  const handleOpenEdit = (promo: ScheduledPromotion) => {
    setEditingPromo(promo);
    setEditTitle(promo.title || '');
    setEditMessage(promo.message || '');
    setEditLinkUrl(promo.link_url || '');
    setEditButtonText(promo.button_text || 'Visit Website');
    setEditTargetType(promo.target_type || 'all_gc');
    try {
      const ids = promo.target_chat_ids ? JSON.parse(promo.target_chat_ids) : [];
      setEditSelectedChatIds(Array.isArray(ids) ? ids : []);
    } catch {
      setEditSelectedChatIds([]);
    }
    setEditScheduleType(promo.schedule_type || 'recurring');
    setEditScheduledTime(promo.scheduled_time || '');
    setEditRepeatInterval(promo.repeat_interval || '5min');
    setEditStatus(promo.status || 'active');
  };

  const handleSaveEdit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingPromo) return;
    if (!editMessage.trim()) {
      showNotice('error', 'Please enter a promotion message.');
      return;
    }

    try {
      setSavingEdit(true);
      const res = await fetch('/api/promotions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: 'edit',
          id: editingPromo.id,
          title: editTitle.trim() || 'Promotional Message',
          message: editMessage.trim(),
          link_url: editLinkUrl.trim(),
          button_text: editButtonText.trim() || 'Visit Website',
          target_type: editTargetType,
          target_chat_ids: editTargetType === 'selected' ? editSelectedChatIds : [],
          schedule_type: editScheduleType,
          scheduled_time: editScheduledTime,
          repeat_interval: editScheduleType === 'recurring' ? editRepeatInterval : 'none',
          status: editStatus,
        }),
      });

      const data = await res.json();
      if (res.ok && data.success) {
        showNotice('success', 'Promotion updated successfully!');
        setEditingPromo(null);
        fetchData();
      } else {
        showNotice('error', data.error || 'Failed to update promotion');
      }
    } catch (err: any) {
      showNotice('error', err.message || 'Network error occurred');
    } finally {
      setSavingEdit(false);
    }
  };

  const formatIntervalLabel = (interval: string) => {
    const norm = (interval || '').toLowerCase().trim().replace(' ', '');
    const found = INTERVAL_OPTIONS.find((opt) => opt.value === norm);
    return found ? found.label : `Every ${interval}`;
  };

  const filteredPromotions = promotions.filter((p) => {
    if (filterTab === 'active') return p.status === 'active';
    if (filterTab === 'paused') return p.status === 'paused' || p.status === 'completed';
    return true;
  });

  return (
    <div className="flex-1 flex flex-col bg-black min-h-screen">
      <Header
        title="Promotions"
        description="Schedule promotional messages to be automatically sent to your Telegram Group Chats."
        badge="Automated Broadcasts"
      />

      <div className="flex-1 p-4 sm:p-6 lg:p-8 max-w-6xl mx-auto w-full space-y-6">
        
        {/* Notification Alert */}
        {notification && (
          <div
            className={`p-3.5 rounded-xl border text-sm flex items-center justify-between gap-3 shadow-md transition-all animate-in fade-in duration-150 ${
              notification.type === 'success'
                ? 'bg-zinc-900 border-zinc-700 text-zinc-100'
                : 'bg-red-950/90 border-red-800 text-red-200'
            }`}
          >
            <div className="flex items-center gap-2.5">
              {notification.type === 'success' ? (
                <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
              ) : (
                <AlertCircle className="w-4 h-4 text-red-400 shrink-0" />
              )}
              <span className="font-medium">{notification.message}</span>
            </div>
            <button onClick={() => setNotification(null)} className="p-1 hover:text-white cursor-pointer">
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* Top Control Bar */}
        <div className="flex flex-wrap items-center justify-between gap-3 bg-zinc-950 p-4 rounded-2xl border border-zinc-800">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-white text-black flex items-center justify-center font-bold">
              <Megaphone className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-base font-bold text-white">Promotions Manager</h2>
              <p className="text-xs text-zinc-400">
                {groupChats.length} Group Chats connected • {promotions.filter(p => p.status === 'active').length} Active
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={fetchData}
              disabled={refreshing}
              className="p-2 rounded-xl bg-zinc-900 hover:bg-zinc-800 text-zinc-300 border border-zinc-800 transition-colors cursor-pointer"
              title="Refresh"
            >
              <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
            </button>

            <button
              onClick={() => setIsFormOpen(!isFormOpen)}
              className="flex items-center gap-2 px-4 py-2 rounded-xl bg-white hover:bg-zinc-200 text-black text-xs font-bold transition-all shadow cursor-pointer active:scale-95"
            >
              {isFormOpen ? <X className="w-4 h-4" /> : <Plus className="w-4 h-4" />}
              <span>{isFormOpen ? 'Close Form' : 'New Promotion'}</span>
            </button>
          </div>
        </div>

        {/* Simple & Clean Creation Form */}
        {isFormOpen && (
          <div className="p-5 sm:p-6 rounded-2xl bg-zinc-950 border border-zinc-800 shadow-xl space-y-4 animate-in fade-in duration-200">
            <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
              <h3 className="font-bold text-sm text-white flex items-center gap-2">
                <Plus className="w-4 h-4 text-white" />
                <span>Create New Promotion</span>
              </h3>
              <span className="text-xs text-zinc-400">Step-by-step setup</span>
            </div>

            <form onSubmit={handleCreatePromotion} className="space-y-4">
              {/* 1. Message Text */}
              <div className="space-y-1.5">
                <label className="block text-xs font-semibold text-zinc-200">
                  Promotion Message <span className="text-red-400">*</span>
                </label>
                <textarea
                  rows={3}
                  required
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  placeholder="Enter the message you want the bot to send to your group chats..."
                  className="w-full px-3.5 py-2.5 rounded-xl bg-zinc-900 border border-zinc-800 text-sm text-white placeholder-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-400 leading-relaxed"
                />
              </div>

              {/* 2. Target Group Selection */}
              <div className="space-y-1.5">
                <label className="block text-xs font-semibold text-zinc-200">
                  Where should it send?
                </label>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => setTargetType('all_gc')}
                    className={`flex-1 py-2 px-3 rounded-xl border text-xs font-semibold flex items-center justify-center gap-2 transition-all cursor-pointer ${
                      targetType === 'all_gc'
                        ? 'bg-white text-black font-bold border-white'
                        : 'bg-zinc-900 text-zinc-400 hover:text-white border-zinc-800'
                    }`}
                  >
                    <Layers className="w-3.5 h-3.5" />
                    <span>All Group Chats ({groupChats.length})</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => setTargetType('selected')}
                    className={`flex-1 py-2 px-3 rounded-xl border text-xs font-semibold flex items-center justify-center gap-2 transition-all cursor-pointer ${
                      targetType === 'selected'
                        ? 'bg-white text-black font-bold border-white'
                        : 'bg-zinc-900 text-zinc-400 hover:text-white border-zinc-800'
                    }`}
                  >
                    <Users className="w-3.5 h-3.5" />
                    <span>Choose Specific Groups</span>
                  </button>
                </div>

                {targetType === 'selected' && (
                  <div className="p-3 rounded-xl bg-zinc-900/80 border border-zinc-800 max-h-36 overflow-y-auto space-y-1.5 mt-2">
                    {groupChats.length > 0 ? (
                      groupChats.map((c) => (
                        <label key={c.chat_id} className="flex items-center gap-2 text-xs text-zinc-300 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={selectedChatIds.includes(c.chat_id)}
                            onChange={(e) => {
                              if (e.target.checked) {
                                setSelectedChatIds([...selectedChatIds, c.chat_id]);
                              } else {
                                setSelectedChatIds(selectedChatIds.filter((id) => id !== c.chat_id));
                              }
                            }}
                            className="rounded bg-black border-zinc-700 text-white focus:ring-0"
                          />
                          <span>{c.chat_title}</span>
                        </label>
                      ))
                    ) : (
                      <p className="text-xs text-zinc-500">No active group chats found.</p>
                    )}
                  </div>
                )}
              </div>

              {/* 3. Send Frequency & Time Interval */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <label className="block text-xs font-semibold text-zinc-200">
                    How often should it send?
                  </label>
                  <select
                    value={scheduleType === 'recurring' ? repeatInterval : 'once'}
                    onChange={(e) => {
                      if (e.target.value === 'once') {
                        setScheduleType('once');
                      } else {
                        setScheduleType('recurring');
                        setRepeatInterval(e.target.value);
                      }
                    }}
                    className="w-full px-3.5 py-2.5 rounded-xl bg-zinc-900 border border-zinc-800 text-xs sm:text-sm text-white focus:outline-none focus:ring-1 focus:ring-zinc-400 cursor-pointer font-medium"
                  >
                    <optgroup label="Preset Time Intervals">
                      <option value="3min">Every 3 Minutes</option>
                      <option value="5min">Every 5 Minutes</option>
                      <option value="10min">Every 10 Minutes</option>
                      <option value="15min">Every 15 Minutes</option>
                      <option value="30min">Every 30 Minutes</option>
                      <option value="1hr">Every 1 Hour</option>
                      <option value="2h">Every 2 Hours</option>
                      <option value="6h">Every 6 Hours</option>
                      <option value="12h">Every 12 Hours</option>
                      <option value="daily">Daily (Every 24 Hours)</option>
                    </optgroup>
                    <optgroup label="One-Time Delivery">
                      <option value="once">Send Once at Scheduled Time</option>
                    </optgroup>
                  </select>
                </div>

                <div className="space-y-1.5">
                  <label className="block text-xs font-semibold text-zinc-200">
                    Start Time
                  </label>
                  <input
                    type="datetime-local"
                    value={scheduledTime}
                    onChange={(e) => setScheduledTime(e.target.value)}
                    className="w-full px-3.5 py-2.5 rounded-xl bg-zinc-900 border border-zinc-800 text-xs sm:text-sm text-white focus:outline-none focus:ring-1 focus:ring-zinc-400 cursor-pointer font-mono"
                  />
                </div>
              </div>

              {/* 4. Optional Button Link Toggle */}
              <div className="pt-1">
                <button
                  type="button"
                  onClick={() => setShowLinkFields(!showLinkFields)}
                  className="text-xs text-zinc-400 hover:text-white flex items-center gap-1.5 transition-colors cursor-pointer"
                >
                  <Globe className="w-3.5 h-3.5" />
                  <span>{showLinkFields ? '- Remove Button Link' : '+ Add Website or Channel Link Button (Optional)'}</span>
                </button>

                {showLinkFields && (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 p-3 rounded-xl bg-zinc-900/60 border border-zinc-800 mt-2">
                    <div className="space-y-1">
                      <label className="block text-[11px] text-zinc-300">Website or Channel URL</label>
                      <input
                        type="url"
                        value={linkUrl}
                        onChange={(e) => setLinkUrl(e.target.value)}
                        placeholder="https://t.me/your_channel or https://example.com"
                        className="w-full px-3 py-1.5 rounded-lg bg-black border border-zinc-800 text-xs text-white placeholder-zinc-500 focus:outline-none"
                      />
                    </div>
                    <div className="space-y-1">
                      <label className="block text-[11px] text-zinc-300">Button Label</label>
                      <input
                        type="text"
                        value={buttonText}
                        onChange={(e) => setButtonText(e.target.value)}
                        placeholder="Visit Website"
                        className="w-full px-3 py-1.5 rounded-lg bg-black border border-zinc-800 text-xs text-white placeholder-zinc-500 focus:outline-none"
                      />
                    </div>
                  </div>
                )}
              </div>

              {/* Submit Buttons */}
              <div className="flex items-center justify-end gap-2 pt-2 border-t border-zinc-800">
                <button
                  type="button"
                  onClick={() => setIsFormOpen(false)}
                  className="px-4 py-2 rounded-xl bg-zinc-900 hover:bg-zinc-800 text-zinc-300 text-xs font-semibold transition-colors cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-5 py-2 rounded-xl bg-white hover:bg-zinc-200 text-black text-xs font-bold transition-all shadow cursor-pointer active:scale-95 disabled:opacity-50 flex items-center gap-2"
                >
                  {submitting && <RefreshCw className="w-3.5 h-3.5 animate-spin text-black" />}
                  <span>Save & Schedule</span>
                </button>
              </div>
            </form>
          </div>
        )}

        {/* Promotions List Section */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <h3 className="font-bold text-sm sm:text-base text-white">Scheduled Promotions</h3>
              <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-zinc-900 text-zinc-300 border border-zinc-800">
                {promotions.length}
              </span>
            </div>

            {/* Simple Filter Pills */}
            <div className="flex items-center gap-1 p-0.5 rounded-lg bg-zinc-900 border border-zinc-800 text-xs">
              {(['all', 'active', 'paused'] as const).map((tab) => (
                <button
                  key={tab}
                  onClick={() => setFilterTab(tab)}
                  className={`px-3 py-1 rounded-md font-semibold capitalize transition-all cursor-pointer ${
                    filterTab === tab ? 'bg-white text-black font-bold' : 'text-zinc-400 hover:text-white'
                  }`}
                >
                  {tab}
                </button>
              ))}
            </div>
          </div>

          {loading ? (
            <div className="p-8 text-center rounded-2xl bg-zinc-950 border border-zinc-800 space-y-2">
              <div className="w-6 h-6 rounded-full border-2 border-white border-t-transparent animate-spin mx-auto" />
              <p className="text-xs text-zinc-400">Loading promotions...</p>
            </div>
          ) : filteredPromotions.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {filteredPromotions.map((item) => {
                const isBroadcasting = broadcastingId === item.id;
                const isPaused = item.status === 'paused';

                return (
                  <div
                    key={item.id}
                    className="p-4 sm:p-5 rounded-2xl bg-zinc-950 border border-zinc-800 hover:border-zinc-700 transition-all shadow-sm flex flex-col justify-between space-y-3"
                  >
                    <div>
                      {/* Top: Status & Target */}
                      <div className="flex items-center justify-between gap-2 mb-2">
                        <span className="text-xs font-mono text-zinc-400 flex items-center gap-1.5">
                          <Layers className="w-3.5 h-3.5 text-zinc-400" />
                          <span>{item.target_type === 'all_gc' ? `All GCs (${groupChats.length})` : 'Selected GCs'}</span>
                        </span>

                        <button
                          onClick={() => handleToggleStatus(item.id, item.status)}
                          className={`px-2 py-0.5 rounded-full text-[10px] font-bold font-mono uppercase border cursor-pointer transition-colors ${
                            item.status === 'active'
                              ? 'bg-emerald-950/80 text-emerald-300 border-emerald-800 hover:bg-emerald-900'
                              : 'bg-zinc-900 text-zinc-400 border-zinc-800 hover:text-white'
                          }`}
                          title="Click to toggle status"
                        >
                          {item.status}
                        </button>
                      </div>

                      {/* Message Content */}
                      <p className="text-xs sm:text-sm text-zinc-200 line-clamp-3 leading-relaxed whitespace-pre-wrap bg-zinc-900/60 p-3 rounded-xl border border-zinc-800/80">
                        {item.message}
                      </p>

                      {/* Link preview if attached */}
                      {item.link_url && (
                        <div className="mt-2 flex items-center justify-between text-xs text-zinc-400 bg-black/40 px-3 py-1.5 rounded-lg border border-zinc-800">
                          <span className="truncate max-w-[200px] text-zinc-300 font-mono text-[11px]">
                            🔗 {item.link_url}
                          </span>
                          <span className="text-[10px] px-1.5 py-0.5 bg-zinc-800 rounded text-white font-medium">
                            {item.button_text || 'Visit'}
                          </span>
                        </div>
                      )}

                      {/* Info Badges */}
                      <div className="flex flex-wrap items-center gap-2 pt-2.5 text-[11px] text-zinc-400">
                        <span className="flex items-center gap-1 px-2 py-0.5 rounded-md bg-zinc-900 border border-zinc-800">
                          <Clock className="w-3 h-3 text-zinc-400" />
                          <span>
                            {item.schedule_type === 'recurring'
                              ? formatIntervalLabel(item.repeat_interval)
                              : 'Once'}
                          </span>
                        </span>

                        <span className="flex items-center gap-1 px-2 py-0.5 rounded-md bg-zinc-900 border border-zinc-800">
                          <Calendar className="w-3 h-3 text-zinc-400" />
                          <span>Next: {new Date(item.scheduled_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                        </span>

                        <span className="text-zinc-500 font-mono text-[10px]">
                          Sent: {item.total_delivered}
                        </span>
                      </div>
                    </div>

                    {/* Action Buttons */}
                    <div className="pt-2 border-t border-zinc-800/80 flex items-center justify-between gap-1.5">
                      <button
                        onClick={() => handleBroadcastNow(item.id)}
                        disabled={isBroadcasting}
                        className="flex-1 py-1.5 px-3 rounded-xl bg-white hover:bg-zinc-200 text-black text-xs font-bold flex items-center justify-center gap-1.5 transition-all cursor-pointer disabled:opacity-50 active:scale-95"
                      >
                        {isBroadcasting ? (
                          <RefreshCw className="w-3.5 h-3.5 animate-spin text-black" />
                        ) : (
                          <Send className="w-3.5 h-3.5 text-black" />
                        )}
                        <span>{isBroadcasting ? 'Sending...' : 'Send Now'}</span>
                      </button>

                      <button
                        onClick={() => handleToggleStatus(item.id, item.status)}
                        className="p-1.5 rounded-xl bg-zinc-900 hover:bg-zinc-800 text-zinc-300 hover:text-white border border-zinc-800 transition-colors cursor-pointer"
                        title={isPaused ? 'Resume' : 'Pause'}
                      >
                        {isPaused ? <Play className="w-3.5 h-3.5" /> : <Pause className="w-3.5 h-3.5" />}
                      </button>

                      <button
                        onClick={() => handleOpenEdit(item)}
                        className="p-1.5 rounded-xl bg-zinc-900 hover:bg-zinc-800 text-zinc-300 hover:text-white border border-zinc-800 transition-colors cursor-pointer"
                        title="Edit Promotion"
                      >
                        <Pencil className="w-3.5 h-3.5" />
                      </button>

                      <button
                        onClick={() => handleDelete(item.id)}
                        className="p-1.5 rounded-xl bg-zinc-900 hover:bg-red-950/60 text-zinc-400 hover:text-red-400 border border-zinc-800 hover:border-red-800 transition-colors cursor-pointer"
                        title="Delete"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="p-8 text-center rounded-2xl bg-zinc-950 border border-zinc-800 space-y-3">
              <Megaphone className="w-7 h-7 text-zinc-600 mx-auto" />
              <p className="text-sm font-semibold text-zinc-300">No promotions found</p>
              <button
                onClick={() => setIsFormOpen(true)}
                className="px-4 py-2 rounded-xl bg-white text-black text-xs font-bold cursor-pointer hover:bg-zinc-200 transition-colors"
              >
                + Create Your First Promotion
              </button>
            </div>
          )}
        </div>

        {/* Collapsible Delivery Logs */}
        {logs.length > 0 && (
          <div className="rounded-2xl bg-zinc-950 border border-zinc-800 overflow-hidden">
            <button
              onClick={() => setShowLogs(!showLogs)}
              className="w-full p-4 flex items-center justify-between text-left text-xs font-semibold text-zinc-300 hover:text-white transition-colors cursor-pointer"
            >
              <div className="flex items-center gap-2">
                <Clock className="w-3.5 h-3.5 text-zinc-400" />
                <span>Recent Delivery Logs ({logs.length})</span>
              </div>
              {showLogs ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
            </button>

            {showLogs && (
              <div className="p-4 border-t border-zinc-800 divide-y divide-zinc-800/60 text-xs">
                {logs.slice(0, 8).map((log) => (
                  <div key={log.id} className="py-2 flex items-center justify-between gap-3 text-zinc-300">
                    <div className="flex items-center gap-2 truncate">
                      <span className="font-semibold text-white truncate">{log.chat_title}</span>
                      <span className="text-zinc-500">•</span>
                      <span className="text-zinc-400 truncate">{log.details || log.status}</span>
                    </div>
                    <span className="text-[10px] text-zinc-500 font-mono shrink-0">
                      {new Date(log.sent_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Clean Edit Modal */}
        {editingPromo && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in">
            <div className="w-full max-w-lg p-5 sm:p-6 rounded-2xl bg-zinc-950 border border-zinc-800 shadow-2xl space-y-4">
              <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
                <h3 className="font-bold text-sm text-white flex items-center gap-2">
                  <Pencil className="w-4 h-4 text-white" />
                  <span>Edit Promotion</span>
                </h3>
                <button onClick={() => setEditingPromo(null)} className="p-1 hover:text-white cursor-pointer">
                  <X className="w-4 h-4" />
                </button>
              </div>

              <form onSubmit={handleSaveEdit} className="space-y-3.5 text-xs">
                <div className="space-y-1">
                  <label className="font-semibold text-zinc-300">Message</label>
                  <textarea
                    rows={3}
                    required
                    value={editMessage}
                    onChange={(e) => setEditMessage(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl bg-zinc-900 border border-zinc-800 text-white text-xs focus:outline-none"
                  />
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <div className="space-y-1">
                    <label className="font-semibold text-zinc-300">Target</label>
                    <select
                      value={editTargetType}
                      onChange={(e) => setEditTargetType(e.target.value as any)}
                      className="w-full px-3 py-2 rounded-xl bg-zinc-900 border border-zinc-800 text-white text-xs cursor-pointer focus:outline-none"
                    >
                      <option value="all_gc">All GCs ({groupChats.length})</option>
                      <option value="selected">Selected GCs</option>
                    </select>
                  </div>

                  <div className="space-y-1">
                    <label className="font-semibold text-zinc-300">Time Interval</label>
                    <select
                      value={editScheduleType === 'recurring' ? editRepeatInterval : 'once'}
                      onChange={(e) => {
                        if (e.target.value === 'once') {
                          setEditScheduleType('once');
                        } else {
                          setEditScheduleType('recurring');
                          setEditRepeatInterval(e.target.value);
                        }
                      }}
                      className="w-full px-3 py-2 rounded-xl bg-zinc-900 border border-zinc-800 text-white text-xs cursor-pointer focus:outline-none"
                    >
                      <option value="3min">Every 3 Minutes</option>
                      <option value="5min">Every 5 Minutes</option>
                      <option value="10min">Every 10 Minutes</option>
                      <option value="15min">Every 15 Minutes</option>
                      <option value="30min">Every 30 Minutes</option>
                      <option value="1hr">Every 1 Hour</option>
                      <option value="2h">Every 2 Hours</option>
                      <option value="daily">Daily (24h)</option>
                      <option value="once">Send Once</option>
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <div className="space-y-1">
                    <label className="font-semibold text-zinc-300">Button Link (Optional)</label>
                    <input
                      type="url"
                      value={editLinkUrl}
                      onChange={(e) => setEditLinkUrl(e.target.value)}
                      placeholder="https://..."
                      className="w-full px-3 py-1.5 rounded-xl bg-zinc-900 border border-zinc-800 text-white text-xs focus:outline-none"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="font-semibold text-zinc-300">Button Label</label>
                    <input
                      type="text"
                      value={editButtonText}
                      onChange={(e) => setEditButtonText(e.target.value)}
                      placeholder="Visit Website"
                      className="w-full px-3 py-1.5 rounded-xl bg-zinc-900 border border-zinc-800 text-white text-xs focus:outline-none"
                    />
                  </div>
                </div>

                <div className="space-y-1">
                  <label className="font-semibold text-zinc-300">Status</label>
                  <select
                    value={editStatus}
                    onChange={(e) => setEditStatus(e.target.value as any)}
                    className="w-full px-3 py-2 rounded-xl bg-zinc-900 border border-zinc-800 text-white text-xs cursor-pointer focus:outline-none"
                  >
                    <option value="active">Active (Sending Automatically)</option>
                    <option value="paused">Paused</option>
                    <option value="completed">Completed</option>
                  </select>
                </div>

                <div className="flex items-center justify-end gap-2 pt-3 border-t border-zinc-800">
                  <button
                    type="button"
                    onClick={() => setEditingPromo(null)}
                    className="px-4 py-1.5 rounded-xl bg-zinc-900 hover:bg-zinc-800 text-zinc-300 text-xs font-semibold cursor-pointer"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={savingEdit}
                    className="px-4 py-1.5 rounded-xl bg-white hover:bg-zinc-200 text-black text-xs font-bold cursor-pointer disabled:opacity-50"
                  >
                    {savingEdit ? 'Saving...' : 'Save Changes'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

      </div>
    </div>
  );
}
