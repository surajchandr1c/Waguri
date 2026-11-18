'use client';

import React, { useState, useEffect, useMemo } from 'react';
import Header from '@/components/Header';
import { 
  Heart, 
  Send, 
  Plus, 
  Trash2, 
  Search, 
  RefreshCw, 
  CheckCircle2, 
  AlertCircle, 
  X, 
  Clock, 
  Calendar, 
  Pencil, 
  Play, 
  Pause,
  Layers,
  Users,
  ChevronDown,
  ChevronUp,
  BookOpen
} from 'lucide-react';

interface ShayariItem {
  id: number;
  category: string;
  content: string;
  author?: string | null;
  language?: string | null;
  media_url?: string | null;
  tags?: string | null;
  created_at?: string;
  updated_at?: string;
}

interface ScheduledShayariItem {
  id: number;
  title: string;
  category: string;
  content_id?: number | null;
  custom_text?: string | null;
  target_type: 'all_gc' | 'selected';
  target_chat_ids?: string | null;
  schedule_type: 'once' | 'recurring';
  scheduled_time: string;
  repeat_interval: string;
  status: 'active' | 'paused' | 'completed';
  total_delivered: number;
  last_sent_at?: string | null;
  created_at?: string;
  updated_at?: string;
}

interface ChatOption {
  chat_id: number;
  chat_title: string;
  chat_type: string;
}

const CATEGORY_LABELS: Record<string, string> = {
  all: 'All Categories',
  shayari: 'Shayari (शायरी)',
  quote: 'Quotes (सुविचार)',
  joke: 'Jokes (चुटकुले)',
  meme: 'Memes (मीम)',
  roast: 'Roasts (रोस्ट)',
  poem: 'Poems (कविता)',
  pickup_line: 'Pickup Lines',
};

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

export default function ShayariPage() {
  const [activeTab, setActiveTab] = useState<'schedules' | 'vault'>('schedules');
  const [items, setItems] = useState<ShayariItem[]>([]);
  const [scheduledShayari, setScheduledShayari] = useState<ScheduledShayariItem[]>([]);
  const [logs, setLogs] = useState<any[]>([]);
  const [chats, setChats] = useState<ChatOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [broadcastingId, setBroadcastingId] = useState<number | null>(null);

  // UI State
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [showLogs, setShowLogs] = useState(false);
  const [notification, setNotification] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  // Vault State
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [isVaultModalOpen, setIsVaultModalOpen] = useState(false);
  const [vaultContent, setVaultContent] = useState('');
  const [vaultCategory, setVaultCategory] = useState('shayari');
  const [vaultAuthor, setVaultAuthor] = useState('');
  const [editingVaultItem, setEditingVaultItem] = useState<ShayariItem | null>(null);

  // Schedule Creator Form State
  const [title, setTitle] = useState('');
  const [scheduleCategory, setScheduleCategory] = useState('shayari');
  const [customText, setCustomText] = useState('');
  const [targetType, setTargetType] = useState<'all_gc' | 'selected'>('all_gc');
  const [selectedChatIds, setSelectedChatIds] = useState<number[]>([]);
  const [scheduleType, setScheduleType] = useState<'recurring' | 'once'>('recurring');
  const [scheduledTime, setScheduledTime] = useState('');
  const [repeatInterval, setRepeatInterval] = useState('5min');

  // Edit Schedule Modal State
  const [editingSchedule, setEditingSchedule] = useState<ScheduledShayariItem | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [editCategory, setEditCategory] = useState('all');
  const [editCustomText, setEditCustomText] = useState('');
  const [editTargetType, setEditTargetType] = useState<'all_gc' | 'selected'>('all_gc');
  const [editSelectedChatIds, setEditSelectedChatIds] = useState<number[]>([]);
  const [editScheduleType, setEditScheduleType] = useState<'recurring' | 'once'>('recurring');
  const [editScheduledTime, setEditScheduledTime] = useState('');
  const [editRepeatInterval, setEditRepeatInterval] = useState('5min');
  const [editStatus, setEditStatus] = useState<'active' | 'paused' | 'completed'>('active');
  const [savingEdit, setSavingEdit] = useState(false);

  // Default time
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
      const res = await fetch('/api/shayari');
      if (res.ok) {
        const data = await res.json();
        if (data.items) setItems(data.items);
        if (data.scheduled_shayari) setScheduledShayari(data.scheduled_shayari);
        if (data.logs) setLogs(data.logs);
        if (data.chats) setChats(data.chats);
      }
    } catch (err) {
      console.error('Failed to load shayari:', err);
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

  // Handle Schedule Creation
  const handleCreateSchedule = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setSubmitting(true);
      const res = await fetch('/api/shayari', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: 'add_schedule',
          title: title.trim() || `${CATEGORY_LABELS[scheduleCategory] || 'Shayari'} Broadcast`,
          category: scheduleCategory,
          custom_text: customText.trim(),
          target_type: targetType,
          target_chat_ids: targetType === 'selected' ? selectedChatIds : [],
          schedule_type: scheduleType,
          scheduled_time: scheduledTime || new Date().toISOString().slice(0, 16),
          repeat_interval: scheduleType === 'recurring' ? repeatInterval : 'none',
        }),
      });

      const data = await res.json();
      if (res.ok && data.success) {
        showNotice('success', 'Broadcast scheduled successfully!');
        setCustomText('');
        setTitle('');
        setIsFormOpen(false);
        fetchData();
      } else {
        showNotice('error', data.error || 'Failed to save schedule');
      }
    } catch (err: any) {
      showNotice('error', err.message || 'Network error occurred');
    } finally {
      setSubmitting(false);
    }
  };

  // Broadcast now
  const handleBroadcastScheduleNow = async (id: number) => {
    try {
      setBroadcastingId(id);
      const res = await fetch('/api/shayari', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'broadcast_schedule', id }),
      });
      const data = await res.json();
      if (res.ok && data.success) {
        showNotice('success', `Sent immediately to ${data.total_targets} group chat(s)!`);
        fetchData();
      } else {
        showNotice('error', data.error || 'Broadcast failed on Telegram');
      }
    } catch (err: any) {
      showNotice('error', err.message || 'Failed to trigger broadcast');
    } finally {
      setBroadcastingId(null);
    }
  };

  // Toggle Schedule Status
  const handleToggleSchedule = async (id: number, currentStatus: string) => {
    const newStatus = currentStatus === 'active' ? 'paused' : 'active';
    try {
      const res = await fetch('/api/shayari', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'toggle_schedule', id, status: newStatus }),
      });
      if (res.ok) {
        setScheduledShayari((prev) =>
          prev.map((s) => (s.id === id ? { ...s, status: newStatus as any } : s))
        );
        showNotice('success', `Broadcast is now ${newStatus}`);
      }
    } catch (err) {
      console.error('Toggle failed:', err);
    }
  };

  // Delete Schedule
  const handleDeleteSchedule = async (id: number) => {
    if (!confirm('Are you sure you want to delete this broadcast schedule?')) return;
    try {
      const res = await fetch('/api/shayari', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'delete_schedule', id }),
      });
      if (res.ok) {
        setScheduledShayari((prev) => prev.filter((s) => s.id !== id));
        showNotice('success', 'Broadcast schedule deleted.');
      }
    } catch (err) {
      console.error('Delete failed:', err);
    }
  };

  // Open Edit Schedule
  const handleOpenEditSchedule = (s: ScheduledShayariItem) => {
    setEditingSchedule(s);
    setEditTitle(s.title || '');
    setEditCategory(s.category || 'all');
    setEditCustomText(s.custom_text || '');
    setEditTargetType(s.target_type || 'all_gc');
    try {
      const ids = s.target_chat_ids ? JSON.parse(s.target_chat_ids) : [];
      setEditSelectedChatIds(Array.isArray(ids) ? ids : []);
    } catch {
      setEditSelectedChatIds([]);
    }
    setEditScheduleType(s.schedule_type || 'recurring');
    setEditScheduledTime(s.scheduled_time || '');
    setEditRepeatInterval(s.repeat_interval || '5min');
    setEditStatus(s.status || 'active');
  };

  // Save Edit Schedule
  const handleSaveEditSchedule = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingSchedule) return;

    try {
      setSavingEdit(true);
      const res = await fetch('/api/shayari', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: 'edit_schedule',
          id: editingSchedule.id,
          title: editTitle.trim() || 'Shayari Broadcast',
          category: editCategory,
          custom_text: editCustomText.trim(),
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
        showNotice('success', 'Broadcast schedule updated successfully!');
        setEditingSchedule(null);
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

  // Vault Add / Edit
  const handleSaveVaultItem = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!vaultContent.trim()) {
      showNotice('error', 'Content text is required.');
      return;
    }

    try {
      const action = editingVaultItem ? 'edit_item' : 'add';
      const body: any = {
        action,
        category: vaultCategory,
        content: vaultContent.trim(),
        author: vaultAuthor.trim() || 'Anonymous',
      };
      if (editingVaultItem) body.id = editingVaultItem.id;

      const res = await fetch('/api/shayari', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      const data = await res.json();
      if (res.ok && data.success) {
        showNotice('success', editingVaultItem ? 'Item updated in vault!' : 'Item saved to vault!');
        setVaultContent('');
        setVaultAuthor('');
        setEditingVaultItem(null);
        setIsVaultModalOpen(false);
        fetchData();
      } else {
        showNotice('error', data.error || 'Failed to save item');
      }
    } catch (err: any) {
      showNotice('error', err.message || 'Network error');
    }
  };

  const handleDeleteVaultItem = async (id: number) => {
    if (!confirm('Delete this item from vault?')) return;
    try {
      const res = await fetch('/api/shayari', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'delete', id }),
      });
      if (res.ok) {
        setItems((prev) => prev.filter((it) => it.id !== id));
        showNotice('success', 'Item removed from vault.');
      }
    } catch (err) {
      console.error('Delete failed:', err);
    }
  };

  const handleQuickScheduleFromVault = (item: ShayariItem) => {
    setActiveTab('schedules');
    setIsFormOpen(true);
    setScheduleCategory(item.category);
    setCustomText(item.content);
    setTitle(`${CATEGORY_LABELS[item.category] || 'Shayari'} Broadcast`);
    showNotice('success', 'Content pre-filled into scheduler!');
  };

  const formatIntervalLabel = (interval: string) => {
    const norm = (interval || '').toLowerCase().trim().replace(' ', '');
    const found = INTERVAL_OPTIONS.find((opt) => opt.value === norm);
    return found ? found.label : `Every ${interval}`;
  };

  const filteredVaultItems = useMemo(() => {
    return items.filter((it) => {
      const matchesCategory = selectedCategory === 'all' || it.category === selectedCategory;
      const matchesSearch = !searchQuery || 
        it.content.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (it.author && it.author.toLowerCase().includes(searchQuery.toLowerCase()));
      return matchesCategory && matchesSearch;
    });
  }, [items, selectedCategory, searchQuery]);

  return (
    <div className="flex-1 flex flex-col bg-black min-h-screen">
      <Header
        title="Shayari & Quotes"
        description="Schedule automated poetry, quotes, jokes, and creative messages to your Telegram Group Chats."
        badge="Engagement Engine"
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

        {/* Top Control Bar with Clean View Switcher */}
        <div className="flex flex-wrap items-center justify-between gap-3 bg-zinc-950 p-4 rounded-2xl border border-zinc-800">
          <div className="flex items-center gap-2">
            <div className="flex p-1 rounded-xl bg-zinc-900 border border-zinc-800 text-xs">
              <button
                onClick={() => setActiveTab('schedules')}
                className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg font-bold transition-all cursor-pointer ${
                  activeTab === 'schedules'
                    ? 'bg-white text-black shadow-sm'
                    : 'text-zinc-400 hover:text-white'
                }`}
              >
                <Clock className="w-3.5 h-3.5" />
                <span>Scheduled Broadcasts ({scheduledShayari.length})</span>
              </button>

              <button
                onClick={() => setActiveTab('vault')}
                className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg font-bold transition-all cursor-pointer ${
                  activeTab === 'vault'
                    ? 'bg-white text-black shadow-sm'
                    : 'text-zinc-400 hover:text-white'
                }`}
              >
                <BookOpen className="w-3.5 h-3.5" />
                <span>Content Vault ({items.length})</span>
              </button>
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

            {activeTab === 'schedules' ? (
              <button
                onClick={() => setIsFormOpen(!isFormOpen)}
                className="flex items-center gap-2 px-4 py-2 rounded-xl bg-white hover:bg-zinc-200 text-black text-xs font-bold transition-all shadow cursor-pointer active:scale-95"
              >
                {isFormOpen ? <X className="w-4 h-4" /> : <Plus className="w-4 h-4" />}
                <span>{isFormOpen ? 'Close Form' : 'New Broadcast'}</span>
              </button>
            ) : (
              <button
                onClick={() => {
                  setEditingVaultItem(null);
                  setVaultContent('');
                  setVaultAuthor('');
                  setIsVaultModalOpen(true);
                }}
                className="flex items-center gap-2 px-4 py-2 rounded-xl bg-white hover:bg-zinc-200 text-black text-xs font-bold transition-all shadow cursor-pointer active:scale-95"
              >
                <Plus className="w-4 h-4" />
                <span>Add to Vault</span>
              </button>
            )}
          </div>
        </div>

        {/* TAB 1: SCHEDULED BROADCASTS */}
        {activeTab === 'schedules' && (
          <div className="space-y-4">
            
            {/* Simple Create Broadcast Form */}
            {isFormOpen && (
              <div className="p-5 sm:p-6 rounded-2xl bg-zinc-950 border border-zinc-800 shadow-xl space-y-4 animate-in fade-in duration-200">
                <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
                  <h3 className="font-bold text-sm text-white flex items-center gap-2">
                    <Plus className="w-4 h-4 text-white" />
                    <span>Create Shayari Broadcast Schedule</span>
                  </h3>
                  <span className="text-xs text-zinc-400">Automated delivery</span>
                </div>

                <form onSubmit={handleCreateSchedule} className="space-y-4">
                  {/* Category Selection */}
                  <div className="space-y-1.5">
                    <label className="block text-xs font-semibold text-zinc-200">
                      Content Category
                    </label>
                    <select
                      value={scheduleCategory}
                      onChange={(e) => setScheduleCategory(e.target.value)}
                      className="w-full px-3.5 py-2.5 rounded-xl bg-zinc-900 border border-zinc-800 text-xs sm:text-sm text-white focus:outline-none focus:ring-1 focus:ring-zinc-400 cursor-pointer font-medium"
                    >
                      <option value="shayari">Shayari (शायरी - Romantic & Emotional)</option>
                      <option value="quote">Quotes (सुविचार - Motivation & Wisdom)</option>
                      <option value="joke">Jokes (चुटकुले - Desi Humor & Laughs)</option>
                      <option value="meme">Memes (Funny & Relatable)</option>
                      <option value="roast">Savage Roasts (Banter & Comebacks)</option>
                      <option value="poem">Poems (Classic Poetry)</option>
                      <option value="pickup_line">Pickup Lines (Flirty & Cheesy)</option>
                      <option value="custom">Custom Text Only</option>
                    </select>
                  </div>

                  {/* Custom Message / Override Text */}
                  <div className="space-y-1.5">
                    <label className="block text-xs font-semibold text-zinc-200">
                      Message Text {scheduleCategory === 'custom' ? <span className="text-red-400">*</span> : '(Optional - leave blank to pick randomly from vault)'}
                    </label>
                    <textarea
                      rows={3}
                      required={scheduleCategory === 'custom'}
                      value={customText}
                      onChange={(e) => setCustomText(e.target.value)}
                      placeholder={
                        scheduleCategory === 'custom'
                          ? 'Enter your custom message to broadcast...'
                          : 'Enter specific text or leave blank to automatically draw from selected category vault...'
                      }
                      className="w-full px-3.5 py-2.5 rounded-xl bg-zinc-900 border border-zinc-800 text-xs sm:text-sm text-white placeholder-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-400 leading-relaxed font-sans"
                    />
                  </div>

                  {/* Target Groups */}
                  <div className="space-y-1.5">
                    <label className="block text-xs font-semibold text-zinc-200">
                      Target Group Chats
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
                        <span>Choose Groups</span>
                      </button>
                    </div>

                    {targetType === 'selected' && (
                      <div className="p-3 rounded-xl bg-zinc-900/80 border border-zinc-800 max-h-36 overflow-y-auto space-y-1.5 mt-2">
                        {groupChats.map((c) => (
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
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Send Frequency & Time Interval */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div className="space-y-1.5">
                      <label className="block text-xs font-semibold text-zinc-200">
                        How often should it broadcast?
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

            {/* Schedules Grid */}
            {loading ? (
              <div className="p-8 text-center rounded-2xl bg-zinc-950 border border-zinc-800 space-y-2">
                <div className="w-6 h-6 rounded-full border-2 border-white border-t-transparent animate-spin mx-auto" />
                <p className="text-xs text-zinc-400">Loading scheduled broadcasts...</p>
              </div>
            ) : scheduledShayari.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {scheduledShayari.map((item) => {
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
                            onClick={() => handleToggleSchedule(item.id, item.status)}
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

                        {/* Title & Excerpt */}
                        <div className="bg-zinc-900/60 p-3 rounded-xl border border-zinc-800/80 space-y-1.5">
                          <div className="flex items-center justify-between">
                            <h4 className="font-semibold text-white text-xs sm:text-sm truncate">
                              {item.title}
                            </h4>
                            <span className="text-[10px] px-2 py-0.5 rounded-full bg-zinc-800 text-zinc-300 font-medium capitalize">
                              {item.category}
                            </span>
                          </div>
                          <p className="text-xs text-zinc-300 line-clamp-3 leading-relaxed whitespace-pre-wrap">
                            {item.custom_text || `Picks random ${item.category} from vault on each trigger.`}
                          </p>
                        </div>

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
                          onClick={() => handleBroadcastScheduleNow(item.id)}
                          disabled={isBroadcasting}
                          className="flex-1 py-1.5 px-3 rounded-xl bg-white hover:bg-zinc-200 text-black text-xs font-bold flex items-center justify-center gap-1.5 transition-all cursor-pointer disabled:opacity-50 active:scale-95"
                        >
                          {isBroadcasting ? (
                            <RefreshCw className="w-3.5 h-3.5 animate-spin text-black" />
                          ) : (
                            <Send className="w-3.5 h-3.5 text-black" />
                          )}
                          <span>{isBroadcasting ? 'Broadcasting...' : 'Send Now'}</span>
                        </button>

                        <button
                          onClick={() => handleToggleSchedule(item.id, item.status)}
                          className="p-1.5 rounded-xl bg-zinc-900 hover:bg-zinc-800 text-zinc-300 hover:text-white border border-zinc-800 transition-colors cursor-pointer"
                          title={isPaused ? 'Resume' : 'Pause'}
                        >
                          {isPaused ? <Play className="w-3.5 h-3.5" /> : <Pause className="w-3.5 h-3.5" />}
                        </button>

                        <button
                          onClick={() => handleOpenEditSchedule(item)}
                          className="p-1.5 rounded-xl bg-zinc-900 hover:bg-zinc-800 text-zinc-300 hover:text-white border border-zinc-800 transition-colors cursor-pointer"
                          title="Edit Broadcast"
                        >
                          <Pencil className="w-3.5 h-3.5" />
                        </button>

                        <button
                          onClick={() => handleDeleteSchedule(item.id)}
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
                <Heart className="w-7 h-7 text-zinc-600 mx-auto" />
                <p className="text-sm font-semibold text-zinc-300">No shayari schedules active</p>
                <button
                  onClick={() => setIsFormOpen(true)}
                  className="px-4 py-2 rounded-xl bg-white text-black text-xs font-bold cursor-pointer hover:bg-zinc-200 transition-colors"
                >
                  + Create Your First Schedule
                </button>
              </div>
            )}

            {/* Collapsible Delivery Logs */}
            {logs.length > 0 && (
              <div className="rounded-2xl bg-zinc-950 border border-zinc-800 overflow-hidden mt-4">
                <button
                  onClick={() => setShowLogs(!showLogs)}
                  className="w-full p-4 flex items-center justify-between text-left text-xs font-semibold text-zinc-300 hover:text-white transition-colors cursor-pointer"
                >
                  <div className="flex items-center gap-2">
                    <Clock className="w-3.5 h-3.5 text-zinc-400" />
                    <span>Recent Broadcast Logs ({logs.length})</span>
                  </div>
                  {showLogs ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                </button>

                {showLogs && (
                  <div className="p-4 border-t border-zinc-800 divide-y divide-zinc-800/60 text-xs">
                    {logs.slice(0, 8).map((log, idx) => (
                      <div key={idx} className="py-2 flex items-center justify-between gap-3 text-zinc-300">
                        <div className="flex items-center gap-2 truncate">
                          <span className="font-semibold text-white truncate">{log.chat_title || `Group ${log.chat_id}`}</span>
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
          </div>
        )}

        {/* TAB 2: CONTENT VAULT */}
        {activeTab === 'vault' && (
          <div className="space-y-4">
            
            {/* Filter Pills & Search */}
            <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
              <div className="flex items-center gap-1.5 overflow-x-auto pb-1 sm:pb-0">
                {Object.keys(CATEGORY_LABELS).map((cat) => (
                  <button
                    key={cat}
                    onClick={() => setSelectedCategory(cat)}
                    className={`px-3 py-1.5 rounded-xl text-xs font-semibold shrink-0 transition-all cursor-pointer ${
                      selectedCategory === cat
                        ? 'bg-white text-black font-bold'
                        : 'bg-zinc-900 text-zinc-400 hover:text-white border border-zinc-800'
                    }`}
                  >
                    {CATEGORY_LABELS[cat]}
                  </button>
                ))}
              </div>

              <div className="relative min-w-[200px]">
                <Search className="w-3.5 h-3.5 text-zinc-500 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search vault..."
                  className="w-full pl-9 pr-3 py-1.5 rounded-xl bg-zinc-900 border border-zinc-800 text-xs text-white placeholder-zinc-500 focus:outline-none"
                />
              </div>
            </div>

            {/* Vault Cards Grid */}
            {filteredVaultItems.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {filteredVaultItems.map((item) => (
                  <div
                    key={item.id}
                    className="p-4 rounded-2xl bg-zinc-950 border border-zinc-800 flex flex-col justify-between space-y-3"
                  >
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-zinc-800 text-zinc-300 uppercase font-mono">
                          {item.category}
                        </span>
                        {item.author && (
                          <span className="text-[11px] text-zinc-500 italic">
                            — {item.author}
                          </span>
                        )}
                      </div>
                      <p className="text-xs sm:text-sm text-zinc-200 whitespace-pre-wrap leading-relaxed">
                        {item.content}
                      </p>
                    </div>

                    <div className="pt-2 border-t border-zinc-800/80 flex items-center justify-between gap-1.5">
                      <button
                        onClick={() => handleQuickScheduleFromVault(item)}
                        className="flex-1 py-1 px-2.5 rounded-xl bg-white hover:bg-zinc-200 text-black text-xs font-bold transition-all cursor-pointer flex items-center justify-center gap-1.5"
                      >
                        <Clock className="w-3 h-3 text-black" />
                        <span>Schedule This</span>
                      </button>

                      <button
                        onClick={() => {
                          setEditingVaultItem(item);
                          setVaultCategory(item.category);
                          setVaultContent(item.content);
                          setVaultAuthor(item.author || '');
                          setIsVaultModalOpen(true);
                        }}
                        className="p-1.5 rounded-xl bg-zinc-900 hover:bg-zinc-800 text-zinc-300 hover:text-white border border-zinc-800 transition-colors cursor-pointer"
                        title="Edit Item"
                      >
                        <Pencil className="w-3.5 h-3.5" />
                      </button>

                      <button
                        onClick={() => handleDeleteVaultItem(item.id)}
                        className="p-1.5 rounded-xl bg-zinc-900 hover:bg-red-950/60 text-zinc-400 hover:text-red-400 border border-zinc-800 hover:border-red-800 transition-colors cursor-pointer"
                        title="Delete"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-8 text-center rounded-2xl bg-zinc-950 border border-zinc-800 space-y-2">
                <p className="text-xs text-zinc-400">No content found matching criteria.</p>
              </div>
            )}
          </div>
        )}

        {/* Clean Edit Schedule Modal */}
        {editingSchedule && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in">
            <div className="w-full max-w-lg p-5 sm:p-6 rounded-2xl bg-zinc-950 border border-zinc-800 shadow-2xl space-y-4">
              <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
                <h3 className="font-bold text-sm text-white flex items-center gap-2">
                  <Pencil className="w-4 h-4 text-white" />
                  <span>Edit Shayari Schedule</span>
                </h3>
                <button onClick={() => setEditingSchedule(null)} className="p-1 hover:text-white cursor-pointer">
                  <X className="w-4 h-4" />
                </button>
              </div>

              <form onSubmit={handleSaveEditSchedule} className="space-y-3.5 text-xs">
                <div className="space-y-1">
                  <label className="font-semibold text-zinc-300">Broadcast Title</label>
                  <input
                    type="text"
                    value={editTitle}
                    onChange={(e) => setEditTitle(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl bg-zinc-900 border border-zinc-800 text-white text-xs focus:outline-none"
                  />
                </div>

                <div className="space-y-1">
                  <label className="font-semibold text-zinc-300">Custom Content (or leave blank to pick from vault)</label>
                  <textarea
                    rows={3}
                    value={editCustomText}
                    onChange={(e) => setEditCustomText(e.target.value)}
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
                    onClick={() => setEditingSchedule(null)}
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

        {/* Clean Add/Edit Vault Item Modal */}
        {isVaultModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in">
            <div className="w-full max-w-lg p-5 sm:p-6 rounded-2xl bg-zinc-950 border border-zinc-800 shadow-2xl space-y-4">
              <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
                <h3 className="font-bold text-sm text-white flex items-center gap-2">
                  <BookOpen className="w-4 h-4 text-white" />
                  <span>{editingVaultItem ? 'Edit Vault Content' : 'Add Content to Vault'}</span>
                </h3>
                <button onClick={() => setIsVaultModalOpen(false)} className="p-1 hover:text-white cursor-pointer">
                  <X className="w-4 h-4" />
                </button>
              </div>

              <form onSubmit={handleSaveVaultItem} className="space-y-3.5 text-xs">
                <div className="space-y-1">
                  <label className="font-semibold text-zinc-300">Category</label>
                  <select
                    value={vaultCategory}
                    onChange={(e) => setVaultCategory(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl bg-zinc-900 border border-zinc-800 text-white text-xs cursor-pointer focus:outline-none"
                  >
                    <option value="shayari">Shayari (शायरी)</option>
                    <option value="quote">Quote (सुविचार)</option>
                    <option value="joke">Joke (चुटकुले)</option>
                    <option value="meme">Meme (मीम)</option>
                    <option value="roast">Roast (रोस्ट)</option>
                    <option value="poem">Poem (कविता)</option>
                    <option value="pickup_line">Pickup Line</option>
                  </select>
                </div>

                <div className="space-y-1">
                  <label className="font-semibold text-zinc-300">Text Content <span className="text-red-400">*</span></label>
                  <textarea
                    rows={4}
                    required
                    value={vaultContent}
                    onChange={(e) => setVaultContent(e.target.value)}
                    placeholder="Enter poetry, quote, joke or roast text here..."
                    className="w-full px-3 py-2 rounded-xl bg-zinc-900 border border-zinc-800 text-white text-xs focus:outline-none leading-relaxed"
                  />
                </div>

                <div className="space-y-1">
                  <label className="font-semibold text-zinc-300">Author / Source (Optional)</label>
                  <input
                    type="text"
                    value={vaultAuthor}
                    onChange={(e) => setVaultAuthor(e.target.value)}
                    placeholder="e.g. Mirza Ghalib, APJ Abdul Kalam, Anonymous"
                    className="w-full px-3 py-2 rounded-xl bg-zinc-900 border border-zinc-800 text-white text-xs focus:outline-none"
                  />
                </div>

                <div className="flex items-center justify-end gap-2 pt-3 border-t border-zinc-800">
                  <button
                    type="button"
                    onClick={() => setIsVaultModalOpen(false)}
                    className="px-4 py-1.5 rounded-xl bg-zinc-900 hover:bg-zinc-800 text-zinc-300 text-xs font-semibold cursor-pointer"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="px-4 py-1.5 rounded-xl bg-white hover:bg-zinc-200 text-black text-xs font-bold cursor-pointer"
                  >
                    {editingVaultItem ? 'Save Changes' : 'Save to Vault'}
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
