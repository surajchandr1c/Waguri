'use client';

import React, { useState, useEffect } from 'react';
import Header from '@/components/Header';
import { 
  Sticker, 
  Clock, 
  Trash2, 
  Play, 
  Pause, 
  CheckCircle2, 
  AlertCircle, 
  RefreshCw, 
  Plus, 
  X, 
  Pencil, 
  Layers, 
  Users,
  Sparkles
} from 'lucide-react';

interface ScheduledStickerItem {
  id: number;
  chat_id: number;
  chat_title: string;
  sticker_url: string;
  sticker_name: string;
  target_type?: 'single' | 'all_gc' | 'selected';
  target_chat_ids?: string | null;
  schedule_type: 'once' | 'recurring';
  scheduled_time: string;
  repeat_interval: string;
  status: 'active' | 'paused' | 'completed';
  last_sent_at?: string | null;
  sticker_pack_name?: string | null;
  current_index?: number;
  created_at?: string;
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
];

export default function StickersPage() {
  const [stickers, setStickers] = useState<ScheduledStickerItem[]>([]);
  const [chats, setChats] = useState<ChatOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [togglingId, setTogglingId] = useState<number | null>(null);

  // UI State
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [filterTab, setFilterTab] = useState<'all' | 'active' | 'paused'>('all');
  const [notification, setNotification] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  // Create Form State
  const [targetType, setTargetType] = useState<'all_gc' | 'single'>('all_gc');
  const [selectedChatId, setSelectedChatId] = useState<string>('');
  const [customChatId, setCustomChatId] = useState<string>('');
  const [stickerUrl, setStickerUrl] = useState<string>('');
  const [stickerName, setStickerName] = useState<string>('');
  const [repeatInterval, setRepeatInterval] = useState<string>('3min');

  // Edit State
  const [editingSticker, setEditingSticker] = useState<ScheduledStickerItem | null>(null);
  const [editTargetType, setEditTargetType] = useState<'all_gc' | 'single'>('all_gc');
  const [editSelectedChatId, setEditSelectedChatId] = useState<string>('');
  const [editStickerUrl, setEditStickerUrl] = useState<string>('');
  const [editStickerName, setEditStickerName] = useState<string>('');
  const [editRepeatInterval, setEditRepeatInterval] = useState<string>('3min');
  const [editStatus, setEditStatus] = useState<'active' | 'paused' | 'completed'>('active');
  const [savingEdit, setSavingEdit] = useState(false);

  const fetchData = async () => {
    try {
      setRefreshing(true);
      const res = await fetch('/api/stickers');
      if (res.ok) {
        const data = await res.json();
        if (data.scheduled_stickers) setStickers(data.scheduled_stickers);
        if (data.chats) {
          setChats(data.chats);
          const firstGC = data.chats.find((c: ChatOption) => c.chat_type === 'group' || c.chat_type === 'supergroup');
          if (firstGC && !selectedChatId) {
            setSelectedChatId(String(firstGC.chat_id));
          }
        }
      }
    } catch (err) {
      console.error('Failed to load stickers:', err);
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

  const handleCreateSticker = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!stickerUrl.trim()) {
      showNotice('error', 'Please enter a sticker pack link or sticker file ID.');
      return;
    }

    const effectiveChatId = targetType === 'all_gc' ? 0 : (selectedChatId === 'custom' ? customChatId : selectedChatId);
    if (targetType === 'single' && !effectiveChatId) {
      showNotice('error', 'Please select a target group chat.');
      return;
    }

    const selectedChat = chats.find((c) => String(c.chat_id) === String(effectiveChatId));
    const chatTitle = targetType === 'all_gc' ? 'All Group Chats' : (selectedChat ? selectedChat.chat_title : `Group ${effectiveChatId}`);

    try {
      setSubmitting(true);
      const res = await fetch('/api/stickers', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: 'add',
          target_type: targetType,
          chat_id: effectiveChatId,
          chat_title: chatTitle,
          sticker_url: stickerUrl.trim(),
          sticker_name: stickerName.trim() || 'Sticker Broadcast',
          schedule_type: 'recurring',
          repeat_interval: repeatInterval,
        }),
      });

      const data = await res.json();
      if (res.ok && data.success) {
        showNotice('success', 'Sticker broadcast activated! First sticker sent; recurring sends started.');
        setStickerUrl('');
        setStickerName('');
        setIsFormOpen(false);
        fetchData();
      } else {
        showNotice('error', data.error || 'Failed to save scheduled sticker');
      }
    } catch (err: any) {
      showNotice('error', err.message || 'Network error occurred');
    } finally {
      setSubmitting(false);
    }
  };

  const handleToggleStatus = async (id: number, currentStatus: string) => {
    const newStatus = currentStatus === 'active' ? 'paused' : 'active';
    try {
      setTogglingId(id);
      const res = await fetch('/api/stickers', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'toggle', id, status: newStatus }),
      });
      const data = await res.json();
      if (res.ok) {
        setStickers((prev) =>
          prev.map((s) => (s.id === id ? { ...s, status: newStatus as any } : s))
        );
        showNotice(
          'success',
          newStatus === 'active'
            ? 'Sticker activated! Sent sticker immediately & recurring sends running.'
            : 'Sticker schedule paused.'
        );
        fetchData();
      }
    } catch (err) {
      console.error('Toggle failed:', err);
    } finally {
      setTogglingId(null);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Are you sure you want to delete this sticker schedule?')) return;
    try {
      const res = await fetch('/api/stickers', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'delete', id }),
      });
      if (res.ok) {
        setStickers((prev) => prev.filter((s) => s.id !== id));
        showNotice('success', 'Sticker schedule deleted.');
      }
    } catch (err) {
      console.error('Delete failed:', err);
    }
  };

  const handleOpenEdit = (stk: ScheduledStickerItem) => {
    setEditingSticker(stk);
    setEditTargetType(stk.target_type === 'all_gc' || stk.chat_id === 0 ? 'all_gc' : 'single');
    setEditSelectedChatId(String(stk.chat_id || ''));
    setEditStickerUrl(stk.sticker_url || '');
    setEditStickerName(stk.sticker_name || '');
    setEditRepeatInterval(stk.repeat_interval || '5min');
    setEditStatus(stk.status || 'active');
  };

  const handleSaveEdit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingSticker) return;
    if (!editStickerUrl.trim()) {
      showNotice('error', 'Sticker pack link or identifier is required.');
      return;
    }

    const effectiveChatId = editTargetType === 'all_gc' ? 0 : Number(editSelectedChatId);
    const selectedChat = chats.find((c) => String(c.chat_id) === String(effectiveChatId));
    const chatTitle = editTargetType === 'all_gc' ? 'All Group Chats' : (selectedChat ? selectedChat.chat_title : `Group ${effectiveChatId}`);

    try {
      setSavingEdit(true);
      const res = await fetch('/api/stickers', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: 'edit',
          id: editingSticker.id,
          target_type: editTargetType,
          chat_id: effectiveChatId,
          chat_title: chatTitle,
          sticker_url: editStickerUrl.trim(),
          sticker_name: editStickerName.trim() || 'Sticker Broadcast',
          schedule_type: 'recurring',
          repeat_interval: editRepeatInterval,
          status: editStatus,
        }),
      });

      const data = await res.json();
      if (res.ok && data.success) {
        showNotice('success', 'Sticker schedule updated successfully!');
        setEditingSticker(null);
        fetchData();
      } else {
        showNotice('error', data.error || 'Failed to update schedule');
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

  const filteredStickers = stickers.filter((item) => {
    if (filterTab === 'active') return item.status === 'active';
    if (filterTab === 'paused') return item.status === 'paused' || item.status === 'completed';
    return true;
  });

  return (
    <div className="flex-1 flex flex-col bg-black min-h-screen">
      <Header
        title="Stickers"
        description="Schedule stickers to automatically send to your Telegram Group Chats at set intervals."
        badge="Sticker Automation"
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
              <Sticker className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-base font-bold text-white">Stickers Scheduler</h2>
              <p className="text-xs text-zinc-400">
                {groupChats.length} Group Chats connected • {stickers.filter(s => s.status === 'active').length} Active
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
              <span>{isFormOpen ? 'Close Form' : 'New Sticker'}</span>
            </button>
          </div>
        </div>

        {/* Simple & Clean Creation Form (No Date/Time Picker - Sends at Interval When Active) */}
        {isFormOpen && (
          <div className="p-5 sm:p-6 rounded-2xl bg-zinc-950 border border-zinc-800 shadow-xl space-y-4 animate-in fade-in duration-200">
            <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
              <h3 className="font-bold text-sm text-white flex items-center gap-2">
                <Plus className="w-4 h-4 text-white" />
                <span>Schedule New Sticker Broadcast</span>
              </h3>
              <span className="text-xs text-emerald-400 flex items-center gap-1">
                <Sparkles className="w-3 h-3" />
                <span>Sends different stickers from pack</span>
              </span>
            </div>

            <form onSubmit={handleCreateSticker} className="space-y-4">
              {/* 1. Sticker Identifier */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <label className="block text-xs font-semibold text-zinc-200">
                    Sticker Pack Link or File ID <span className="text-red-400">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    value={stickerUrl}
                    onChange={(e) => setStickerUrl(e.target.value)}
                    placeholder="https://t.me/addstickers/HotCherry or pack name"
                    className="w-full px-3.5 py-2.5 rounded-xl bg-zinc-900 border border-zinc-800 text-xs sm:text-sm text-white placeholder-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-400 font-mono"
                  />
                  <p className="text-[11px] text-zinc-500">
                    ✨ Tip: Give a pack link to automatically rotate and send a different sticker every time!
                  </p>
                </div>

                <div className="space-y-1.5">
                  <label className="block text-xs font-semibold text-zinc-200">
                    Sticker Name (Optional)
                  </label>
                  <input
                    type="text"
                    value={stickerName}
                    onChange={(e) => setStickerName(e.target.value)}
                    placeholder="e.g. Welcome Stickers, Fun Reactions"
                    className="w-full px-3.5 py-2.5 rounded-xl bg-zinc-900 border border-zinc-800 text-xs sm:text-sm text-white placeholder-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-400"
                  />
                </div>
              </div>

              {/* 2. Target Group Selection */}
              <div className="space-y-1.5">
                <label className="block text-xs font-semibold text-zinc-200">
                  Target Group Chat
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
                    onClick={() => setTargetType('single')}
                    className={`flex-1 py-2 px-3 rounded-xl border text-xs font-semibold flex items-center justify-center gap-2 transition-all cursor-pointer ${
                      targetType === 'single'
                        ? 'bg-white text-black font-bold border-white'
                        : 'bg-zinc-900 text-zinc-400 hover:text-white border-zinc-800'
                    }`}
                  >
                    <Users className="w-3.5 h-3.5" />
                    <span>Specific Group Chat</span>
                  </button>
                </div>

                {targetType === 'single' && (
                  <div className="pt-1.5 space-y-2">
                    <select
                      value={selectedChatId}
                      onChange={(e) => setSelectedChatId(e.target.value)}
                      className="w-full px-3.5 py-2.5 rounded-xl bg-zinc-900 border border-zinc-800 text-xs sm:text-sm text-white focus:outline-none focus:ring-1 focus:ring-zinc-400 cursor-pointer"
                    >
                      {groupChats.length > 0 ? (
                        groupChats.map((c) => (
                          <option key={c.chat_id} value={c.chat_id}>
                            {c.chat_title}
                          </option>
                        ))
                      ) : (
                        <option value="">No active groups found</option>
                      )}
                      <option value="custom">+ Enter Custom Chat ID</option>
                    </select>

                    {selectedChatId === 'custom' && (
                      <input
                        type="text"
                        value={customChatId}
                        onChange={(e) => setCustomChatId(e.target.value)}
                        placeholder="Enter Telegram Group ID (e.g. -1001234567890)"
                        className="w-full px-3.5 py-2 rounded-xl bg-black border border-zinc-800 text-xs font-mono text-white placeholder-zinc-500 focus:outline-none"
                      />
                    )}
                  </div>
                )}
              </div>

              {/* 3. Send Frequency / Time Interval */}
              <div className="space-y-1.5">
                <label className="block text-xs font-semibold text-zinc-200">
                  Time Interval (How often to send stickers)
                </label>
                <select
                  value={repeatInterval}
                  onChange={(e) => setRepeatInterval(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl bg-zinc-900 border border-zinc-800 text-xs sm:text-sm text-white focus:outline-none focus:ring-1 focus:ring-zinc-400 cursor-pointer font-medium"
                >
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
                </select>
                <p className="text-[11px] text-zinc-500">
                  When active, the bot automatically sends stickers to the target group at this interval.
                </p>
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
                  <span>Activate & Start Sending</span>
                </button>
              </div>
            </form>
          </div>
        )}

        {/* Stickers List Section */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <h3 className="font-bold text-sm sm:text-base text-white">Scheduled Stickers</h3>
              <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-zinc-900 text-zinc-300 border border-zinc-800">
                {stickers.length}
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
              <p className="text-xs text-zinc-400">Loading scheduled stickers...</p>
            </div>
          ) : filteredStickers.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {filteredStickers.map((item) => {
                const isPaused = item.status === 'paused';
                const isAllGC = item.target_type === 'all_gc' || item.chat_id === 0;
                const isToggling = togglingId === item.id;

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
                          <span>{isAllGC ? `All GCs (${groupChats.length})` : item.chat_title}</span>
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

                      {/* Sticker Preview / Title */}
                      <div className="bg-zinc-900/60 p-3 rounded-xl border border-zinc-800/80 space-y-1">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <Sticker className="w-4 h-4 text-zinc-300" />
                            <h4 className="font-semibold text-white text-sm truncate">{item.sticker_name}</h4>
                          </div>
                          {item.sticker_pack_name && (
                            <span className="text-[10px] px-2 py-0.5 rounded-md bg-zinc-800 text-zinc-300 font-mono">
                              Pack: {item.sticker_pack_name}
                            </span>
                          )}
                        </div>
                        <p className="text-[11px] font-mono text-zinc-400 truncate">
                          {item.sticker_url}
                        </p>
                      </div>

                      {/* Info Badge: Only Interval (Date/Next Time Removed) */}
                      <div className="flex items-center gap-2 pt-2.5 text-[11px] text-zinc-400">
                        <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-zinc-900 border border-zinc-800 font-medium">
                          <Clock className="w-3.5 h-3.5 text-zinc-300" />
                          <span className="text-white font-semibold">
                            {formatIntervalLabel(item.repeat_interval)}
                          </span>
                        </span>

                        <span className="text-[10px] text-zinc-500 font-mono">
                          {item.status === 'active' ? '• Sending automatically' : '• Paused'}
                        </span>
                      </div>
                    </div>

                    {/* Action Buttons: ONLY Pause/Resume, Edit, Delete (Send Now Removed) */}
                    <div className="pt-2 border-t border-zinc-800/80 flex items-center justify-end gap-2">
                      {/* 1. Pause / Resume icon button */}
                      <button
                        onClick={() => handleToggleStatus(item.id, item.status)}
                        disabled={isToggling}
                        className={`p-2.5 rounded-xl border transition-all cursor-pointer ${
                          isPaused
                            ? 'bg-emerald-950/80 hover:bg-emerald-900 text-emerald-300 border-emerald-800'
                            : 'bg-zinc-900 hover:bg-zinc-800 text-zinc-300 hover:text-white border-zinc-800'
                        }`}
                        title={isPaused ? 'Resume & Start Sending' : 'Pause Sending'}
                      >
                        {isToggling ? (
                          <RefreshCw className="w-4 h-4 animate-spin" />
                        ) : isPaused ? (
                          <Play className="w-4 h-4 text-emerald-400" />
                        ) : (
                          <Pause className="w-4 h-4 text-zinc-300" />
                        )}
                      </button>

                      {/* 2. Edit icon button */}
                      <button
                        onClick={() => handleOpenEdit(item)}
                        className="p-2.5 rounded-xl bg-zinc-900 hover:bg-zinc-800 text-zinc-300 hover:text-white border border-zinc-800 transition-colors cursor-pointer"
                        title="Edit Sticker Schedule"
                      >
                        <Pencil className="w-4 h-4" />
                      </button>

                      {/* 3. Delete icon button */}
                      <button
                        onClick={() => handleDelete(item.id)}
                        className="p-2.5 rounded-xl bg-zinc-900 hover:bg-red-950/60 text-zinc-400 hover:text-red-400 border border-zinc-800 hover:border-red-800 transition-colors cursor-pointer"
                        title="Delete"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="p-8 text-center rounded-2xl bg-zinc-950 border border-zinc-800 space-y-3">
              <Sticker className="w-7 h-7 text-zinc-600 mx-auto" />
              <p className="text-sm font-semibold text-zinc-300">No scheduled stickers found</p>
              <button
                onClick={() => setIsFormOpen(true)}
                className="px-4 py-2 rounded-xl bg-white text-black text-xs font-bold cursor-pointer hover:bg-zinc-200 transition-colors"
              >
                + Schedule Your First Sticker
              </button>
            </div>
          )}
        </div>

        {/* Clean Edit Modal (No Date/Time Picker - Just Pack Link, Target, Interval, and Status) */}
        {editingSticker && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in">
            <div className="w-full max-w-lg p-5 sm:p-6 rounded-2xl bg-zinc-950 border border-zinc-800 shadow-2xl space-y-4">
              <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
                <h3 className="font-bold text-sm text-white flex items-center gap-2">
                  <Pencil className="w-4 h-4 text-white" />
                  <span>Edit Sticker Schedule</span>
                </h3>
                <button onClick={() => setEditingSticker(null)} className="p-1 hover:text-white cursor-pointer">
                  <X className="w-4 h-4" />
                </button>
              </div>

              <form onSubmit={handleSaveEdit} className="space-y-3.5 text-xs">
                <div className="space-y-1">
                  <label className="font-semibold text-zinc-300">Sticker Pack Link or File ID</label>
                  <input
                    type="text"
                    required
                    value={editStickerUrl}
                    onChange={(e) => setEditStickerUrl(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl bg-zinc-900 border border-zinc-800 text-white font-mono text-xs focus:outline-none"
                  />
                  <p className="text-[10px] text-zinc-500">
                    Enter a pack link to send different stickers on each interval.
                  </p>
                </div>

                <div className="space-y-1">
                  <label className="font-semibold text-zinc-300">Sticker Name</label>
                  <input
                    type="text"
                    value={editStickerName}
                    onChange={(e) => setEditStickerName(e.target.value)}
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
                      <option value="single">Specific GC</option>
                    </select>
                  </div>

                  <div className="space-y-1">
                    <label className="font-semibold text-zinc-300">Time Interval</label>
                    <select
                      value={editRepeatInterval}
                      onChange={(e) => setEditRepeatInterval(e.target.value)}
                      className="w-full px-3 py-2 rounded-xl bg-zinc-900 border border-zinc-800 text-white text-xs cursor-pointer focus:outline-none"
                    >
                      <option value="3min">Every 3 Minutes</option>
                      <option value="5min">Every 5 Minutes</option>
                      <option value="10min">Every 10 Minutes</option>
                      <option value="15min">Every 15 Minutes</option>
                      <option value="30min">Every 30 Minutes</option>
                      <option value="1hr">Every 1 Hour</option>
                      <option value="2h">Every 2 Hours</option>
                      <option value="6h">Every 6 Hours</option>
                      <option value="12h">Every 12 Hours</option>
                      <option value="daily">Daily (24h)</option>
                    </select>
                  </div>
                </div>

                {editTargetType === 'single' && (
                  <div className="space-y-1">
                    <label className="font-semibold text-zinc-300">Select Specific Group</label>
                    <select
                      value={editSelectedChatId}
                      onChange={(e) => setEditSelectedChatId(e.target.value)}
                      className="w-full px-3 py-2 rounded-xl bg-zinc-900 border border-zinc-800 text-white text-xs cursor-pointer focus:outline-none"
                    >
                      {groupChats.map((c) => (
                        <option key={c.chat_id} value={c.chat_id}>
                          {c.chat_title}
                        </option>
                      ))}
                    </select>
                  </div>
                )}

                <div className="space-y-1">
                  <label className="font-semibold text-zinc-300">Status</label>
                  <select
                    value={editStatus}
                    onChange={(e) => setEditStatus(e.target.value as any)}
                    className="w-full px-3 py-2 rounded-xl bg-zinc-900 border border-zinc-800 text-white text-xs cursor-pointer focus:outline-none"
                  >
                    <option value="active">Active (Sends automatically at interval)</option>
                    <option value="paused">Paused</option>
                    <option value="completed">Completed</option>
                  </select>
                </div>

                <div className="flex items-center justify-end gap-2 pt-3 border-t border-zinc-800">
                  <button
                    type="button"
                    onClick={() => setEditingSticker(null)}
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
