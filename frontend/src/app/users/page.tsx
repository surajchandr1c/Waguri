'use client';

import React, { useState, useEffect } from 'react';
import { 
  Users, 
  Search, 
  Check, 
  Copy, 
  LayoutGrid, 
  List, 
  RefreshCw,
  Eye,
  MessagesSquare,
  Radio,
  UserX,
  X,
  CheckCircle2,
  Sliders
} from 'lucide-react';
import Header from '@/components/Header';
import { useUserModal } from '@/context/UserModalContext';
import { BotUser, BotGroupChat, BotChannel } from '@/types/user';

export default function UsersPage() {
  const [users, setUsers] = useState<BotUser[]>([]);
  const [groups, setGroups] = useState<BotGroupChat[]>([]);
  const [channels, setChannels] = useState<BotChannel[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [activeTab, setActiveTab] = useState<'users' | 'gc' | 'channels'>('users');
  const [viewMode, setViewMode] = useState<'grid' | 'table'>('grid');
  const [copiedId, setCopiedId] = useState<number | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [removedAlert, setRemovedAlert] = useState<string | null>(null);

  const { openUserModal } = useUserModal();

  const fetchEntities = async () => {
    try {
      setRefreshing(true);
      const res = await fetch('/api/users');
      if (res.ok) {
        const data = await res.json();
        if (data.users) setUsers(data.users);
        if (data.groups) setGroups(data.groups);
        if (data.channels) setChannels(data.channels);
      }
    } catch (err) {
      console.error('Failed to load bot entities:', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchEntities();
  }, []);

  // Real-time listener: when an entity removes the bot, instantly remove from page
  useEffect(() => {
    const handleEntityRemoved = (e: any) => {
      const { id, type, title } = e.detail || {};
      const numId = Number(id);

      if (type === 'user') {
        setUsers((prev) => prev.filter((u) => u.telegramId !== numId && u.id !== `usr_${id}`));
      } else if (type === 'gc' || type === 'group' || type === 'supergroup') {
        setGroups((prev) =>
          prev.filter((g) => g.chatId !== numId && Math.abs(g.chatId) !== Math.abs(numId))
        );
      } else if (type === 'channel') {
        setChannels((prev) =>
          prev.filter((c) => c.channelId !== numId && Math.abs(c.channelId) !== Math.abs(numId))
        );
      }

      setRemovedAlert(`Bot removed from ${title || id}. Data purged from this page.`);
      setTimeout(() => setRemovedAlert(null), 4000);
    };

    window.addEventListener('bot_entity_removed', handleEntityRemoved);
    return () => window.removeEventListener('bot_entity_removed', handleEntityRemoved);
  }, []);

  const handleDirectRemove = async (
    e: React.MouseEvent,
    id: number | string,
    type: 'user' | 'gc' | 'channel',
    title: string
  ) => {
    e.stopPropagation();
    try {
      const res = await fetch('/api/users', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id, type }),
      });
      if (res.ok) {
        window.dispatchEvent(
          new CustomEvent('bot_entity_removed', {
            detail: { id, type, title },
          })
        );
      }
    } catch (err) {
      console.error('Failed to remove bot:', err);
    }
  };

  const handleCopyId = (e: React.MouseEvent, id: number) => {
    e.stopPropagation();
    navigator.clipboard.writeText(id.toString());
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 1500);
  };

  // Search filtering
  const filteredUsers = users.filter((u) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return (
      u.firstName.toLowerCase().includes(q) ||
      (u.lastName && u.lastName.toLowerCase().includes(q)) ||
      (u.username && u.username.toLowerCase().includes(q)) ||
      u.telegramId.toString().includes(q) ||
      (u.gcName && u.gcName.toLowerCase().includes(q)) ||
      (u.gcId && u.gcId.toString().includes(q)) ||
      (u.channelName && u.channelName.toLowerCase().includes(q)) ||
      (u.channelId && u.channelId.toString().includes(q))
    );
  });

  const filteredGroups = groups.filter((g) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return g.title.toLowerCase().includes(q) || g.chatId.toString().includes(q);
  });

  const filteredChannels = channels.filter((c) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return c.title.toLowerCase().includes(q) || c.channelId.toString().includes(q);
  });

  return (
    <div className="flex-1 flex flex-col bg-black">
      <Header
        title="Bot Users, Connected GCs & Channels"
        description="Active users, group chats (GC), and broadcast channels using the bot."
      />

      <div className="flex-1 p-4 sm:p-6 lg:p-8 max-w-7xl mx-auto w-full space-y-5">
        
        {/* Real-time Bot Removed Notification */}
        {removedAlert && (
          <div className="p-3.5 rounded-xl bg-zinc-900 border border-zinc-700 text-zinc-200 text-xs flex items-center justify-between gap-3 shadow-sm">
            <div className="flex items-center gap-2">
              <UserX className="w-4 h-4 text-white" />
              <span>{removedAlert}</span>
            </div>
            <button
              onClick={() => setRemovedAlert(null)}
              className="p-1 text-zinc-400 hover:text-white transition-colors cursor-pointer"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        {/* Search Bar & Mode Toggle */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="relative flex-1 max-w-md">
            <Search className="w-4 h-4 text-zinc-500 absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by account name, username, or ID..."
              className="w-full pl-10 pr-10 py-2 rounded-xl bg-zinc-900 border border-zinc-800 text-xs sm:text-sm text-zinc-200 placeholder:text-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-500 transition-all"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery('')}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-zinc-400 hover:text-white cursor-pointer"
              >
                Clear
              </button>
            )}
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={fetchEntities}
              disabled={refreshing}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-zinc-900 hover:bg-zinc-800 text-zinc-300 text-xs font-medium border border-zinc-800 transition-colors cursor-pointer"
              title="Refresh"
            >
              <RefreshCw className={`w-3.5 h-3.5 text-zinc-400 ${refreshing ? 'animate-spin' : ''}`} />
              <span>Refresh</span>
            </button>

            <div className="flex items-center p-1 rounded-xl bg-zinc-900 border border-zinc-800">
              <button
                onClick={() => setViewMode('grid')}
                className={`p-1.5 rounded-lg text-xs transition-colors cursor-pointer ${
                  viewMode === 'grid' ? 'bg-white text-black font-bold' : 'text-zinc-400 hover:text-white'
                }`}
                title="Grid View"
              >
                <LayoutGrid className="w-3.5 h-3.5" />
              </button>
              <button
                onClick={() => setViewMode('table')}
                className={`p-1.5 rounded-lg text-xs transition-colors cursor-pointer ${
                  viewMode === 'table' ? 'bg-white text-black font-bold' : 'text-zinc-400 hover:text-white'
                }`}
                title="Table View"
              >
                <List className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </div>

        {/* Primary Tabs */}
        <div className="flex items-center gap-2 border-b border-zinc-800 pb-3 overflow-x-auto no-scrollbar whitespace-nowrap min-w-0">
          {[
            { id: 'users', label: `Users & Connected Chats (${users.length})`, icon: Users },
            { id: 'gc', label: `Group Chats (${groups.length})`, icon: MessagesSquare },
            { id: 'channels', label: `Broadcast Channels (${channels.length})`, icon: Radio },
          ].map((tab) => {
            const isSelected = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl text-xs font-semibold transition-all shrink-0 cursor-pointer ${
                  isSelected
                    ? 'bg-white text-black font-bold border border-white'
                    : 'bg-zinc-900 text-zinc-400 hover:text-white hover:bg-zinc-800 border border-zinc-800'
                }`}
              >
                <tab.icon className="w-3.5 h-3.5" />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>

        {/* Content Area */}
        {loading ? (
          <div className="p-12 text-center rounded-2xl bg-zinc-900/40 border border-zinc-800 space-y-3">
            <div className="w-7 h-7 rounded-full border-2 border-white border-t-transparent animate-spin mx-auto" />
            <p className="text-xs text-zinc-400">Loading active bot accounts...</p>
          </div>
        ) : (
          <div>
            {/* 1. USERS WITH CONNECTED GC AND CHANNELS */}
            {activeTab === 'users' && (
              <div>
                {filteredUsers.length === 0 ? (
                  <div className="p-8 text-center rounded-xl bg-zinc-900/40 border border-zinc-800 text-xs text-zinc-400">
                    No bot users found matching your search.
                  </div>
                ) : viewMode === 'grid' ? (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {filteredUsers.map((user) => {
                      const initials = user.firstName ? user.firstName.slice(0, 2).toUpperCase() : 'US';

                      return (
                        <div
                          key={user.id}
                          onClick={() => openUserModal(user)}
                          className="p-5 rounded-2xl bg-zinc-900/80 hover:bg-zinc-900 border border-zinc-800 hover:border-zinc-700 transition-all group flex flex-col justify-between cursor-pointer space-y-4"
                        >
                          <div className="space-y-3.5">
                            {/* User Header */}
                            <div className="flex items-start justify-between gap-3">
                              <div className="flex items-center gap-3">
                                <div className="w-11 h-11 rounded-xl bg-white flex items-center justify-center text-black font-extrabold text-sm shrink-0">
                                  {initials}
                                </div>
                                <div className="min-w-0">
                                  <div className="text-base font-bold text-white group-hover:text-zinc-200 transition-colors">
                                    {user.firstName} {user.lastName || ''}
                                  </div>
                                  <div className="text-xs text-zinc-400 font-mono">
                                    {user.username ? `@${user.username}` : `ID: ${user.telegramId}`}
                                  </div>
                                </div>
                              </div>

                              <span className="px-2.5 py-1 rounded-full text-[10px] font-bold bg-white text-black shrink-0">
                                Bot Active
                              </span>
                            </div>

                            {/* Telegram ID Row */}
                            <div className="flex items-center justify-between px-3 py-1.5 rounded-xl bg-zinc-950 border border-zinc-800 text-xs font-mono text-zinc-400">
                              <span>Telegram User ID: {user.telegramId}</span>
                              <div className="flex items-center gap-2">
                                <button
                                  onClick={(e) => handleCopyId(e, user.telegramId)}
                                  className="hover:text-white p-0.5 cursor-pointer"
                                  title="Copy User ID"
                                >
                                  {copiedId === user.telegramId ? (
                                    <Check className="w-3.5 h-3.5 text-white" />
                                  ) : (
                                    <Copy className="w-3.5 h-3.5 text-zinc-500 hover:text-zinc-300" />
                                  )}
                                </button>
                                <button
                                  onClick={(e) => handleDirectRemove(e, user.telegramId, 'user', user.firstName)}
                                  className="p-0.5 text-zinc-500 hover:text-white cursor-pointer"
                                  title="Remove bot from this account"
                                >
                                  <UserX className="w-3.5 h-3.5" />
                                </button>
                              </div>
                            </div>

                            {/* Connected GC & Channel Cards */}
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                              {/* Group Chat (GC) Box */}
                              <div className="p-3 rounded-xl bg-zinc-950 border border-zinc-800 space-y-1">
                                <div className="flex items-center gap-1.5 text-[10px] font-semibold text-zinc-400 uppercase tracking-wider">
                                  <MessagesSquare className="w-3.5 h-3.5 text-sky-400 shrink-0" />
                                  <span>Group Chat (GC)</span>
                                </div>
                                <div className="text-xs font-bold text-white truncate" title={user.gcName || 'Couple chatting 😉'}>
                                  {user.gcName || 'Couple chatting 😉'}
                                </div>
                                {user.gcId && (
                                  <div className="text-[10px] font-mono text-zinc-500">
                                    Chat ID: {user.gcId}
                                  </div>
                                )}
                              </div>

                              {/* Broadcast Channel Box */}
                              <div className="p-3 rounded-xl bg-zinc-950 border border-zinc-800 space-y-1">
                                <div className="flex items-center gap-1.5 text-[10px] font-semibold text-zinc-400 uppercase tracking-wider">
                                  <Radio className="w-3.5 h-3.5 text-pink-400 shrink-0" />
                                  <span>Channel</span>
                                </div>
                                <div className="text-xs font-bold text-white truncate" title={user.channelName || 'Waguri Official Announcements'}>
                                  {user.channelName || 'Waguri Official Announcements'}
                                </div>
                                {user.channelId && (
                                  <div className="text-[10px] font-mono text-zinc-500">
                                    Channel ID: {user.channelId}
                                  </div>
                                )}
                              </div>
                            </div>

                            {/* Features In Use Section */}
                            <div className="p-3.5 rounded-xl bg-zinc-950 border border-zinc-800 space-y-2">
                              <div className="flex items-center gap-1.5 text-[11px] font-semibold text-zinc-400 uppercase tracking-wider">
                                <Sliders className="w-3.5 h-3.5 text-white" />
                                <span>Features In Use ({user.featuresUsed.length})</span>
                              </div>

                              <div className="flex flex-wrap gap-1.5 pt-0.5">
                                {user.featuresUsed.map((feat) => (
                                  <span
                                    key={feat.id}
                                    className="px-2.5 py-1 rounded-lg text-xs font-medium bg-zinc-900 text-zinc-200 border border-zinc-800 flex items-center gap-1.5"
                                  >
                                    <CheckCircle2 className="w-3 h-3 text-white shrink-0" />
                                    <span>{feat.name}</span>
                                  </span>
                                ))}
                              </div>
                            </div>
                          </div>

                          <div className="flex items-center justify-between pt-3 border-t border-zinc-800 text-xs">
                            <span className="text-[11px] text-zinc-500">Connected: {user.connectedAt}</span>
                            <div className="flex items-center gap-1 text-xs font-semibold text-white group-hover:underline">
                              <Eye className="w-3.5 h-3.5" />
                              <span>View User & Chat Details</span>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  /* USERS TABLE */
                  <div className="overflow-x-auto rounded-xl border border-zinc-800 bg-zinc-950">
                    <table className="w-full text-left text-xs">
                      <thead className="bg-zinc-900 border-b border-zinc-800 text-zinc-400 font-semibold uppercase tracking-wider">
                        <tr>
                          <th className="p-3.5">User</th>
                          <th className="p-3.5">Username / ID</th>
                          <th className="p-3.5">GC (Group Chat) Name</th>
                          <th className="p-3.5">Channel Name</th>
                          <th className="p-3.5">Features In Use</th>
                          <th className="p-3.5 text-right">Action</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-zinc-800">
                        {filteredUsers.map((user) => (
                          <tr
                            key={user.id}
                            onClick={() => openUserModal(user)}
                            className="hover:bg-zinc-900/60 transition-colors cursor-pointer"
                          >
                            <td className="p-3.5">
                              <div className="font-bold text-white text-sm">
                                {user.firstName} {user.lastName || ''}
                              </div>
                              <div className="text-[11px] text-zinc-500">
                                Connected {user.connectedAt}
                              </div>
                            </td>
                            <td className="p-3.5 font-mono text-zinc-300">
                              <div>{user.username ? `@${user.username}` : '—'}</div>
                              <div className="text-[11px] text-zinc-500">{user.telegramId}</div>
                            </td>
                            <td className="p-3.5">
                              <div className="flex items-center gap-1.5 font-medium text-white">
                                <MessagesSquare className="w-3.5 h-3.5 text-sky-400 shrink-0" />
                                <span className="truncate max-w-[160px]">{user.gcName || 'Couple chatting 😉'}</span>
                              </div>
                              {user.gcId && (
                                <div className="text-[10px] font-mono text-zinc-500">
                                  ID: {user.gcId}
                                </div>
                              )}
                            </td>
                            <td className="p-3.5">
                              <div className="flex items-center gap-1.5 font-medium text-white">
                                <Radio className="w-3.5 h-3.5 text-pink-400 shrink-0" />
                                <span className="truncate max-w-[160px]">{user.channelName || 'Waguri Official Announcements'}</span>
                              </div>
                              {user.channelId && (
                                <div className="text-[10px] font-mono text-zinc-500">
                                  ID: {user.channelId}
                                </div>
                              )}
                            </td>
                            <td className="p-3.5">
                              <div className="flex flex-wrap gap-1 max-w-xs">
                                {user.featuresUsed.map((f) => (
                                  <span key={f.id} className="px-2 py-0.5 rounded text-[11px] bg-zinc-900 text-zinc-200 border border-zinc-800 whitespace-nowrap">
                                    {f.name}
                                  </span>
                                ))}
                              </div>
                            </td>
                            <td className="p-3.5 text-right">
                              <div className="flex items-center justify-end gap-2">
                                <button
                                  onClick={(e) => { e.stopPropagation(); openUserModal(user); }}
                                  className="px-3 py-1 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-white text-xs font-semibold border border-zinc-700 cursor-pointer"
                                >
                                  Details
                                </button>
                                <button
                                  onClick={(e) => handleDirectRemove(e, user.telegramId, 'user', user.firstName)}
                                  className="p-1 text-zinc-400 hover:text-white cursor-pointer"
                                  title="Remove bot"
                                >
                                  <UserX className="w-4 h-4" />
                                </button>
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}

            {/* 2. GROUP CHATS (GC) THAT ADDED THE BOT */}
            {activeTab === 'gc' && (
              <div>
                {filteredGroups.length === 0 ? (
                  <div className="p-8 text-center rounded-xl bg-zinc-900/40 border border-zinc-800 text-xs text-zinc-400">
                    No group chats found matching your search.
                  </div>
                ) : viewMode === 'grid' ? (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {filteredGroups.map((group) => {
                      const initials = group.title.slice(0, 2).toUpperCase();

                      return (
                        <div
                          key={group.id}
                          onClick={() => openUserModal(group)}
                          className="p-5 rounded-2xl bg-zinc-900/80 hover:bg-zinc-900 border border-zinc-800 hover:border-zinc-700 transition-all group flex flex-col justify-between cursor-pointer space-y-4"
                        >
                          <div className="space-y-3.5">
                            <div className="flex items-start justify-between gap-3">
                              <div className="flex items-center gap-3">
                                <div className="w-11 h-11 rounded-xl bg-zinc-800 border border-zinc-700 flex items-center justify-center text-white font-bold text-sm shrink-0">
                                  {initials}
                                </div>
                                <div className="min-w-0">
                                  <div className="text-base font-bold text-white group-hover:text-zinc-200 transition-colors truncate">
                                    {group.title}
                                  </div>
                                  <div className="text-xs text-zinc-400 font-mono uppercase">
                                    {group.type}
                                  </div>
                                </div>
                              </div>

                              <span className="px-2.5 py-1 rounded-full text-[10px] font-bold bg-white text-black">
                                Bot Active
                              </span>
                            </div>

                            <div className="flex items-center justify-between px-3 py-1.5 rounded-xl bg-zinc-950 border border-zinc-800 text-xs font-mono text-zinc-400">
                              <span>Chat ID: {group.chatId}</span>
                              <div className="flex items-center gap-2">
                                <button
                                  onClick={(e) => handleCopyId(e, group.chatId)}
                                  className="hover:text-white p-0.5 cursor-pointer"
                                  title="Copy Chat ID"
                                >
                                  {copiedId === group.chatId ? (
                                    <Check className="w-3.5 h-3.5 text-white" />
                                  ) : (
                                    <Copy className="w-3.5 h-3.5 text-zinc-500 hover:text-zinc-300" />
                                  )}
                                </button>
                                <button
                                  onClick={(e) => handleDirectRemove(e, group.chatId, 'gc', group.title)}
                                  className="p-0.5 text-zinc-500 hover:text-white cursor-pointer"
                                  title="Remove bot from this group"
                                >
                                  <UserX className="w-3.5 h-3.5" />
                                </button>
                              </div>
                            </div>

                            {/* Features In Use */}
                            <div className="p-3.5 rounded-xl bg-zinc-950 border border-zinc-800 space-y-2">
                              <div className="flex items-center gap-1.5 text-[11px] font-semibold text-zinc-400 uppercase tracking-wider">
                                <Sliders className="w-3.5 h-3.5 text-white" />
                                <span>Features In Use ({group.featuresUsed.length})</span>
                              </div>

                              <div className="flex flex-wrap gap-1.5 pt-0.5">
                                {group.featuresUsed.map((feat) => (
                                  <span
                                    key={feat.id}
                                    className="px-2.5 py-1 rounded-lg text-xs font-medium bg-zinc-900 text-zinc-200 border border-zinc-800 flex items-center gap-1.5"
                                  >
                                    <CheckCircle2 className="w-3 h-3 text-white shrink-0" />
                                    <span>{feat.name}</span>
                                  </span>
                                ))}
                              </div>
                            </div>
                          </div>

                          <div className="flex items-center justify-between pt-3 border-t border-zinc-800 text-xs">
                            <span className="text-[11px] text-zinc-500">Added: {group.addedAt}</span>
                            <div className="flex items-center gap-1 text-xs font-semibold text-white group-hover:underline">
                              <Eye className="w-3.5 h-3.5" />
                              <span>View GC Details</span>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  /* GROUPS TABLE */
                  <div className="overflow-x-auto rounded-xl border border-zinc-800 bg-zinc-950">
                    <table className="w-full text-left text-xs">
                      <thead className="bg-zinc-900 border-b border-zinc-800 text-zinc-400 font-semibold uppercase tracking-wider">
                        <tr>
                          <th className="p-3.5">Group Chat Name</th>
                          <th className="p-3.5">Chat ID</th>
                          <th className="p-3.5">Type</th>
                          <th className="p-3.5">Features In Use</th>
                          <th className="p-3.5 text-right">Action</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-zinc-800">
                        {filteredGroups.map((group) => (
                          <tr
                            key={group.id}
                            onClick={() => openUserModal(group)}
                            className="hover:bg-zinc-900/60 transition-colors cursor-pointer"
                          >
                            <td className="p-3.5 font-bold text-white text-sm">{group.title}</td>
                            <td className="p-3.5 font-mono text-zinc-300">{group.chatId}</td>
                            <td className="p-3.5 uppercase font-mono text-zinc-400">{group.type}</td>
                            <td className="p-3.5">
                              <div className="flex flex-wrap gap-1">
                                {group.featuresUsed.map((f) => (
                                  <span key={f.id} className="px-2 py-0.5 rounded text-[11px] bg-zinc-900 text-zinc-200 border border-zinc-800">
                                    {f.name}
                                  </span>
                                ))}
                              </div>
                            </td>
                            <td className="p-3.5 text-right">
                              <div className="flex items-center justify-end gap-2">
                                <button
                                  onClick={(e) => { e.stopPropagation(); openUserModal(group); }}
                                  className="px-3 py-1 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-white text-xs font-semibold border border-zinc-700 cursor-pointer"
                                >
                                  Details
                                </button>
                                <button
                                  onClick={(e) => handleDirectRemove(e, group.chatId, 'gc', group.title)}
                                  className="p-1 text-zinc-400 hover:text-white cursor-pointer"
                                  title="Remove bot"
                                >
                                  <UserX className="w-4 h-4" />
                                </button>
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}

            {/* 3. CHANNELS THAT ADDED THE BOT */}
            {activeTab === 'channels' && (
              <div>
                {filteredChannels.length === 0 ? (
                  <div className="p-8 text-center rounded-xl bg-zinc-900/40 border border-zinc-800 text-xs text-zinc-400">
                    No broadcast channels found matching your search.
                  </div>
                ) : viewMode === 'grid' ? (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {filteredChannels.map((chan) => {
                      const initials = chan.title.slice(0, 2).toUpperCase();

                      return (
                        <div
                          key={chan.id}
                          onClick={() => openUserModal(chan)}
                          className="p-5 rounded-2xl bg-zinc-900/80 hover:bg-zinc-900 border border-zinc-800 hover:border-zinc-700 transition-all group flex flex-col justify-between cursor-pointer space-y-4"
                        >
                          <div className="space-y-3.5">
                            <div className="flex items-start justify-between gap-3">
                              <div className="flex items-center gap-3">
                                <div className="w-11 h-11 rounded-xl bg-zinc-800 border border-zinc-700 flex items-center justify-center text-white font-bold text-sm shrink-0">
                                  {initials}
                                </div>
                                <div className="min-w-0">
                                  <div className="text-base font-bold text-white group-hover:text-zinc-200 transition-colors truncate">
                                    {chan.title}
                                  </div>
                                  <div className="text-xs text-zinc-400 font-mono uppercase">
                                    Broadcast Channel
                                  </div>
                                </div>
                              </div>

                              <span className="px-2.5 py-1 rounded-full text-[10px] font-bold bg-white text-black">
                                Bot Active
                              </span>
                            </div>

                            <div className="flex items-center justify-between px-3 py-1.5 rounded-xl bg-zinc-950 border border-zinc-800 text-xs font-mono text-zinc-400">
                              <span>Channel ID: {chan.channelId}</span>
                              <div className="flex items-center gap-2">
                                <button
                                  onClick={(e) => handleCopyId(e, chan.channelId)}
                                  className="hover:text-white p-0.5 cursor-pointer"
                                  title="Copy Channel ID"
                                >
                                  {copiedId === chan.channelId ? (
                                    <Check className="w-3.5 h-3.5 text-white" />
                                  ) : (
                                    <Copy className="w-3.5 h-3.5 text-zinc-500 hover:text-zinc-300" />
                                  )}
                                </button>
                                <button
                                  onClick={(e) => handleDirectRemove(e, chan.channelId, 'channel', chan.title)}
                                  className="p-0.5 text-zinc-500 hover:text-white cursor-pointer"
                                  title="Remove bot from this channel"
                                >
                                  <UserX className="w-3.5 h-3.5" />
                                </button>
                              </div>
                            </div>

                            {/* Features In Use */}
                            <div className="p-3.5 rounded-xl bg-zinc-950 border border-zinc-800 space-y-2">
                              <div className="flex items-center gap-1.5 text-[11px] font-semibold text-zinc-400 uppercase tracking-wider">
                                <Sliders className="w-3.5 h-3.5 text-white" />
                                <span>Features In Use ({chan.featuresUsed.length})</span>
                              </div>

                              <div className="flex flex-wrap gap-1.5 pt-0.5">
                                {chan.featuresUsed.map((feat) => (
                                  <span
                                    key={feat.id}
                                    className="px-2.5 py-1 rounded-lg text-xs font-medium bg-zinc-900 text-zinc-200 border border-zinc-800 flex items-center gap-1.5"
                                  >
                                    <CheckCircle2 className="w-3 h-3 text-white shrink-0" />
                                    <span>{feat.name}</span>
                                  </span>
                                ))}
                              </div>
                            </div>
                          </div>

                          <div className="flex items-center justify-between pt-3 border-t border-zinc-800 text-xs">
                            <span className="text-[11px] text-zinc-500">Added: {chan.addedAt}</span>
                            <div className="flex items-center gap-1 text-xs font-semibold text-white group-hover:underline">
                              <Eye className="w-3.5 h-3.5" />
                              <span>View Channel Details</span>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  /* CHANNELS TABLE */
                  <div className="overflow-x-auto rounded-xl border border-zinc-800 bg-zinc-950">
                    <table className="w-full text-left text-xs">
                      <thead className="bg-zinc-900 border-b border-zinc-800 text-zinc-400 font-semibold uppercase tracking-wider">
                        <tr>
                          <th className="p-3.5">Channel Title</th>
                          <th className="p-3.5">Channel ID</th>
                          <th className="p-3.5">Features In Use</th>
                          <th className="p-3.5 text-right">Action</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-zinc-800">
                        {filteredChannels.map((chan) => (
                          <tr
                            key={chan.id}
                            onClick={() => openUserModal(chan)}
                            className="hover:bg-zinc-900/60 transition-colors cursor-pointer"
                          >
                            <td className="p-3.5 font-bold text-white text-sm">{chan.title}</td>
                            <td className="p-3.5 font-mono text-zinc-300">{chan.channelId}</td>
                            <td className="p-3.5">
                              <div className="flex flex-wrap gap-1">
                                {chan.featuresUsed.map((f) => (
                                  <span key={f.id} className="px-2 py-0.5 rounded text-[11px] bg-zinc-900 text-zinc-200 border border-zinc-800">
                                    {f.name}
                                  </span>
                                ))}
                              </div>
                            </td>
                            <td className="p-3.5 text-right">
                              <div className="flex items-center justify-end gap-2">
                                <button
                                  onClick={(e) => { e.stopPropagation(); openUserModal(chan); }}
                                  className="px-3 py-1 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-white text-xs font-semibold border border-zinc-700 cursor-pointer"
                                >
                                  Details
                                </button>
                                <button
                                  onClick={(e) => handleDirectRemove(e, chan.channelId, 'channel', chan.title)}
                                  className="p-1 text-zinc-400 hover:text-white cursor-pointer"
                                  title="Remove bot"
                                >
                                  <UserX className="w-4 h-4" />
                                </button>
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

      </div>
    </div>
  );
}
