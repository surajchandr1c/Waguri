'use client';

import React, { useState, useEffect } from 'react';
import Header from '@/components/Header';
import { 
  Database, 
  CheckCircle2, 
  Shield, 
  Save, 
  RefreshCw, 
  AlertCircle, 
  Sliders
} from 'lucide-react';
import { SystemSettings } from '@/types/schema';

export default function SettingsPage() {
  const [telemetry, setTelemetry] = useState<any>(null);
  const [settings, setSettings] = useState<SystemSettings>({
    anti_link_enabled: true,
    anti_bio_link_enabled: true,
    clean_service_enabled: true,
    anti_spam_enabled: true,
    flood_detection_enabled: true,
    flood_message_limit: 8,
    flood_window_seconds: 10,
    spam_window_seconds: 30,
    spam_warning_limit: 2,
    spam_restriction_seconds: 86400,
    warning_delete_after_seconds: 10,
    abuse_detection_enabled: true,
    abuse_sexual_language: true,
    abuse_general_language: true,
    abuse_hindi_hinglish: true,
    abuse_harassment: true,
    abuse_threats: true,
    abuse_bypass_detection: true,
    abuse_warning_system: true,
    abuse_warning_limit: 3,
    abuse_mute_duration_minutes: 30,
    global_emergency_overrides: {},
  });

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [notification, setNotification] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  const loadData = async () => {
    try {
      setLoading(true);
      const [telemetryRes, settingsRes] = await Promise.all([
        fetch('/api/telemetry'),
        fetch('/api/settings'),
      ]);

      if (telemetryRes.ok) {
        const tData = await telemetryRes.json();
        setTelemetry(tData);
      }

      if (settingsRes.ok) {
        const sData = await settingsRes.json();
        if (sData && !sData.error) {
          setSettings((prev) => ({ ...prev, ...sData }));
        }
      }
    } catch (err) {
      console.error('Failed to load settings data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleToggle = (key: keyof SystemSettings) => {
    setSettings((prev) => ({
      ...prev,
      [key]: !prev[key],
    }));
  };

  const handleNumberChange = (key: keyof SystemSettings, value: number) => {
    setSettings((prev) => ({
      ...prev,
      [key]: isNaN(value) ? 0 : value,
    }));
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setSaving(true);
      setNotification(null);

      const res = await fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings),
      });

      const result = await res.json();
      if (res.ok && result.success !== false) {
        setNotification({
          type: 'success',
          message: 'Settings successfully persisted to MongoDB Atlas!',
        });
        if (result.settings) {
          setSettings((prev) => ({ ...prev, ...result.settings }));
        }
      } else {
        setNotification({
          type: 'error',
          message: result.error || 'Failed to save settings to MongoDB.',
        });
      }
    } catch (err: any) {
      setNotification({
        type: 'error',
        message: err.message || 'Error occurred while saving settings.',
      });
    } finally {
      setSaving(false);
      setTimeout(() => setNotification(null), 5000);
    }
  };

  return (
    <div className="flex-1 flex flex-col bg-black">
      <Header
        title="Settings & System Overview"
        description="Configure MongoDB Atlas persistence, multi-tenant moderation defaults, and real-time security rules."
        badge="MongoDB Atlas Active"
      />

      <div className="flex-1 p-4 sm:p-6 lg:p-8 max-w-7xl mx-auto w-full space-y-6">

        {/* Toast / Notification Banner */}
        {notification && (
          <div
            className={`p-4 rounded-2xl border flex items-center justify-between gap-3 text-xs font-semibold animate-in fade-in slide-in-from-top-2 duration-200 ${
              notification.type === 'success'
                ? 'bg-emerald-950/60 border-emerald-800 text-emerald-200'
                : 'bg-red-950/60 border-red-800 text-red-200'
            }`}
          >
            <div className="flex items-center gap-2.5">
              {notification.type === 'success' ? (
                <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
              ) : (
                <AlertCircle className="w-4 h-4 text-red-400 shrink-0" />
              )}
              <span>{notification.message}</span>
            </div>
            <button
              onClick={() => setNotification(null)}
              className="text-zinc-400 hover:text-white transition-colors"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Database & System Health (Compact & Clean) */}
        <div className="p-5 rounded-2xl bg-zinc-900/80 border border-zinc-800 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-xs font-semibold text-zinc-300">
              <Database className="w-4 h-4 text-white" />
              <span>MongoDB Engine & Cloud Replica Status</span>
            </div>
            <button
              onClick={loadData}
              disabled={loading}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-300 hover:text-white border border-zinc-700 text-xs transition-colors cursor-pointer"
            >
              <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
              <span>Refresh</span>
            </button>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="p-3.5 rounded-xl bg-zinc-950 border border-zinc-800 space-y-1">
              <span className="text-[10px] text-zinc-500 uppercase font-semibold">Database Engine</span>
              <div className="text-sm font-bold text-white font-mono">MongoDB Atlas</div>
              <div className="text-[10px] text-emerald-400 flex items-center gap-1">
                <CheckCircle2 className="w-3 h-3 text-emerald-400" /> Connected
              </div>
            </div>

            <div className="p-3.5 rounded-xl bg-zinc-950 border border-zinc-800 space-y-1">
              <span className="text-[10px] text-zinc-500 uppercase font-semibold">Database Name</span>
              <div className="text-sm font-bold text-white font-mono">waguri_db</div>
              <div className="text-[10px] text-zinc-400">Cloud Clustered</div>
            </div>

            <div className="p-3.5 rounded-xl bg-zinc-950 border border-zinc-800 space-y-1">
              <span className="text-[10px] text-zinc-500 uppercase font-semibold">Cluster URL</span>
              <div className="text-sm font-bold text-white font-mono truncate">waguri.y7u511m</div>
              <div className="text-[10px] text-zinc-400">AWS / Replica Set</div>
            </div>

            <div className="p-3.5 rounded-xl bg-zinc-950 border border-zinc-800 space-y-1">
              <span className="text-[10px] text-zinc-500 uppercase font-semibold">Registered Chats</span>
              <div className="text-sm font-bold text-white font-mono">
                {telemetry?.chats?.length || 0} active
              </div>
              <div className="text-[10px] text-zinc-400">Multi-Tenant Isolation</div>
            </div>
          </div>
        </div>

        {/* Global Moderation & Protection Configuration (Editable & Saveable) */}
        <form onSubmit={handleSave} className="p-5 rounded-2xl bg-zinc-900/80 border border-zinc-800 space-y-5">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-zinc-800/80 pb-4">
            <div>
              <div className="flex items-center gap-2 text-sm font-bold text-white">
                <Sliders className="w-4 h-4 text-white" />
                <span>Global Protection Defaults (Stored in MongoDB)</span>
              </div>
              <p className="text-xs text-zinc-400 mt-0.5">
                These defaults automatically govern all newly added groups and platform security limits.
              </p>
            </div>

            <button
              type="submit"
              disabled={saving}
              className="flex items-center justify-center gap-2 px-4 py-2 rounded-xl bg-white hover:bg-zinc-200 text-black text-xs font-bold shadow-sm transition-all cursor-pointer disabled:opacity-50"
            >
              <Save className="w-3.5 h-3.5" />
              <span>{saving ? 'Saving...' : 'Save Settings to MongoDB'}</span>
            </button>
          </div>

          {/* Toggle Switches Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            
            {/* Anti-Link */}
            <div 
              onClick={() => handleToggle('anti_link_enabled')}
              className="p-3.5 rounded-xl bg-zinc-950 border border-zinc-800 flex items-center justify-between cursor-pointer hover:border-zinc-700 transition-colors"
            >
              <div>
                <div className="text-xs font-bold text-white">Anti-Link Protection</div>
                <div className="text-[11px] text-zinc-400">Delete unauthorized external links</div>
              </div>
              <div className={`w-9 h-5 rounded-full p-0.5 transition-colors ${settings.anti_link_enabled ? 'bg-white' : 'bg-zinc-800'}`}>
                <div className={`w-4 h-4 rounded-full bg-black transition-transform ${settings.anti_link_enabled ? 'translate-x-4' : 'translate-x-0'}`} />
              </div>
            </div>

            {/* Anti-Bio Link */}
            <div 
              onClick={() => handleToggle('anti_bio_link_enabled')}
              className="p-3.5 rounded-xl bg-zinc-950 border border-zinc-800 flex items-center justify-between cursor-pointer hover:border-zinc-700 transition-colors"
            >
              <div>
                <div className="text-xs font-bold text-white">Anti-Bio Link Scan</div>
                <div className="text-[11px] text-zinc-400">Check user bio for suspicious links</div>
              </div>
              <div className={`w-9 h-5 rounded-full p-0.5 transition-colors ${settings.anti_bio_link_enabled ? 'bg-white' : 'bg-zinc-800'}`}>
                <div className={`w-4 h-4 rounded-full bg-black transition-transform ${settings.anti_bio_link_enabled ? 'translate-x-4' : 'translate-x-0'}`} />
              </div>
            </div>

            {/* Clean Service */}
            <div 
              onClick={() => handleToggle('clean_service_enabled')}
              className="p-3.5 rounded-xl bg-zinc-950 border border-zinc-800 flex items-center justify-between cursor-pointer hover:border-zinc-700 transition-colors"
            >
              <div>
                <div className="text-xs font-bold text-white">Clean Service Messages</div>
                <div className="text-[11px] text-zinc-400">Auto-delete joins, leaves & pin notices</div>
              </div>
              <div className={`w-9 h-5 rounded-full p-0.5 transition-colors ${settings.clean_service_enabled ? 'bg-white' : 'bg-zinc-800'}`}>
                <div className={`w-4 h-4 rounded-full bg-black transition-transform ${settings.clean_service_enabled ? 'translate-x-4' : 'translate-x-0'}`} />
              </div>
            </div>

            {/* Anti-Spam */}
            <div 
              onClick={() => handleToggle('anti_spam_enabled')}
              className="p-3.5 rounded-xl bg-zinc-950 border border-zinc-800 flex items-center justify-between cursor-pointer hover:border-zinc-700 transition-colors"
            >
              <div>
                <div className="text-xs font-bold text-white">Anti-Spam Engine</div>
                <div className="text-[11px] text-zinc-400">Detect message repetition & flood</div>
              </div>
              <div className={`w-9 h-5 rounded-full p-0.5 transition-colors ${settings.anti_spam_enabled ? 'bg-white' : 'bg-zinc-800'}`}>
                <div className={`w-4 h-4 rounded-full bg-black transition-transform ${settings.anti_spam_enabled ? 'translate-x-4' : 'translate-x-0'}`} />
              </div>
            </div>

            {/* Flood Detection */}
            <div 
              onClick={() => handleToggle('flood_detection_enabled')}
              className="p-3.5 rounded-xl bg-zinc-950 border border-zinc-800 flex items-center justify-between cursor-pointer hover:border-zinc-700 transition-colors"
            >
              <div>
                <div className="text-xs font-bold text-white">Flood Burst Shield</div>
                <div className="text-[11px] text-zinc-400">Block rapid burst spam attacks</div>
              </div>
              <div className={`w-9 h-5 rounded-full p-0.5 transition-colors ${settings.flood_detection_enabled ? 'bg-white' : 'bg-zinc-800'}`}>
                <div className={`w-4 h-4 rounded-full bg-black transition-transform ${settings.flood_detection_enabled ? 'translate-x-4' : 'translate-x-0'}`} />
              </div>
            </div>

            {/* Abuse Master Shield */}
            <div 
              onClick={() => handleToggle('abuse_detection_enabled')}
              className="p-3.5 rounded-xl bg-zinc-950 border border-zinc-800 flex items-center justify-between cursor-pointer hover:border-zinc-700 transition-colors"
            >
              <div>
                <div className="text-xs font-bold text-white flex items-center gap-1.5">
                  <Shield className="w-3.5 h-3.5 text-red-400" />
                  <span>Abuse Master Shield</span>
                </div>
                <div className="text-[11px] text-zinc-400">Detect vulgarity, slurs & harassment</div>
              </div>
              <div className={`w-9 h-5 rounded-full p-0.5 transition-colors ${settings.abuse_detection_enabled ? 'bg-red-500' : 'bg-zinc-800'}`}>
                <div className={`w-4 h-4 rounded-full bg-black transition-transform ${settings.abuse_detection_enabled ? 'translate-x-4' : 'translate-x-0'}`} />
              </div>
            </div>

            {/* Abuse Bypass Detection */}
            <div 
              onClick={() => handleToggle('abuse_bypass_detection')}
              className="p-3.5 rounded-xl bg-zinc-950 border border-zinc-800 flex items-center justify-between cursor-pointer hover:border-zinc-700 transition-colors"
            >
              <div>
                <div className="text-xs font-bold text-white">Abuse Bypass Shield</div>
                <div className="text-[11px] text-zinc-400">Catch leet, spaced & homoglyph tricks</div>
              </div>
              <div className={`w-9 h-5 rounded-full p-0.5 transition-colors ${settings.abuse_bypass_detection ? 'bg-white' : 'bg-zinc-800'}`}>
                <div className={`w-4 h-4 rounded-full bg-black transition-transform ${settings.abuse_bypass_detection ? 'translate-x-4' : 'translate-x-0'}`} />
              </div>
            </div>

            {/* Hindi & Hinglish Detection */}
            <div 
              onClick={() => handleToggle('abuse_hindi_hinglish')}
              className="p-3.5 rounded-xl bg-zinc-950 border border-zinc-800 flex items-center justify-between cursor-pointer hover:border-zinc-700 transition-colors"
            >
              <div>
                <div className="text-xs font-bold text-white">Hindi & Hinglish Slurs</div>
                <div className="text-[11px] text-zinc-400">Devanagari and Roman transliterations</div>
              </div>
              <div className={`w-9 h-5 rounded-full p-0.5 transition-colors ${settings.abuse_hindi_hinglish ? 'bg-white' : 'bg-zinc-800'}`}>
                <div className={`w-4 h-4 rounded-full bg-black transition-transform ${settings.abuse_hindi_hinglish ? 'translate-x-4' : 'translate-x-0'}`} />
              </div>
            </div>

          </div>

          {/* Threshold Inputs */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 pt-2">
            
            <div className="p-3.5 rounded-xl bg-zinc-950 border border-zinc-800 space-y-1.5">
              <label className="text-[10px] text-zinc-400 uppercase font-semibold block">
                Flood Limit (Msgs)
              </label>
              <input
                type="number"
                min={3}
                max={50}
                value={settings.flood_message_limit}
                onChange={(e) => handleNumberChange('flood_message_limit', parseInt(e.target.value))}
                className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-1.5 text-xs text-white font-mono focus:outline-none focus:border-zinc-600"
              />
            </div>

            <div className="p-3.5 rounded-xl bg-zinc-950 border border-zinc-800 space-y-1.5">
              <label className="text-[10px] text-zinc-400 uppercase font-semibold block">
                Flood Window (Sec)
              </label>
              <input
                type="number"
                min={3}
                max={60}
                value={settings.flood_window_seconds}
                onChange={(e) => handleNumberChange('flood_window_seconds', parseInt(e.target.value))}
                className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-1.5 text-xs text-white font-mono focus:outline-none focus:border-zinc-600"
              />
            </div>

            <div className="p-3.5 rounded-xl bg-zinc-950 border border-zinc-800 space-y-1.5">
              <label className="text-[10px] text-zinc-400 uppercase font-semibold block">
                Spam Window (Sec)
              </label>
              <input
                type="number"
                min={5}
                max={120}
                value={settings.spam_window_seconds}
                onChange={(e) => handleNumberChange('spam_window_seconds', parseInt(e.target.value))}
                className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-1.5 text-xs text-white font-mono focus:outline-none focus:border-zinc-600"
              />
            </div>

            <div className="p-3.5 rounded-xl bg-zinc-950 border border-zinc-800 space-y-1.5">
              <label className="text-[10px] text-zinc-400 uppercase font-semibold block">
                Max Warnings Limit
              </label>
              <input
                type="number"
                min={1}
                max={10}
                value={settings.spam_warning_limit}
                onChange={(e) => handleNumberChange('spam_warning_limit', parseInt(e.target.value))}
                className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-1.5 text-xs text-white font-mono focus:outline-none focus:border-zinc-600"
              />
            </div>

            <div className="p-3.5 rounded-xl bg-zinc-950 border border-zinc-800 space-y-1.5">
              <label className="text-[10px] text-zinc-400 uppercase font-semibold block">
                Abuse Warn Threshold
              </label>
              <input
                type="number"
                min={1}
                max={10}
                value={settings.abuse_warning_limit || 3}
                onChange={(e) => handleNumberChange('abuse_warning_limit', parseInt(e.target.value))}
                className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-1.5 text-xs text-white font-mono focus:outline-none focus:border-zinc-600"
              />
            </div>

            <div className="p-3.5 rounded-xl bg-zinc-950 border border-zinc-800 space-y-1.5">
              <label className="text-[10px] text-zinc-400 uppercase font-semibold block">
                Abuse Mute (Mins)
              </label>
              <input
                type="number"
                min={5}
                max={1440}
                value={settings.abuse_mute_duration_minutes || 30}
                onChange={(e) => handleNumberChange('abuse_mute_duration_minutes', parseInt(e.target.value))}
                className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-1.5 text-xs text-white font-mono focus:outline-none focus:border-zinc-600"
              />
            </div>

          </div>

          <div className="flex justify-end pt-2">
            <button
              type="submit"
              disabled={saving}
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-white hover:bg-zinc-200 text-black text-xs font-bold shadow-md transition-all cursor-pointer disabled:opacity-50"
            >
              <Save className="w-3.5 h-3.5" />
              <span>{saving ? 'Saving...' : 'Save Settings to MongoDB'}</span>
            </button>
          </div>
        </form>

      </div>
    </div>
  );
}
