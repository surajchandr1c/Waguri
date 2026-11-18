'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  Lock,
  Mail,
  Eye,
  EyeOff,
  ShieldAlert,
  ShieldCheck,
  Bot,
  ArrowRight,
  Loader2,
} from 'lucide-react';

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);
    setSuccessMessage(null);

    // Client-side validation
    const trimmedEmail = email.trim();
    if (!trimmedEmail) {
      setErrorMessage('Please enter your admin email address.');
      return;
    }

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(trimmedEmail)) {
      setErrorMessage('Please enter a valid email address format.');
      return;
    }

    if (!password) {
      setErrorMessage('Please enter your admin password.');
      return;
    }

    setIsLoading(true);

    try {
      const response = await fetch('/api/admin/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          email: trimmedEmail,
          password,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        setErrorMessage(data.error || 'Authentication failed. Please check your credentials.');
        setIsLoading(false);
        return;
      }

      setSuccessMessage('Access granted. Redirecting to Admin Dashboard...');
      
      // Smooth redirect to dashboard
      setTimeout(() => {
        window.location.href = '/';
      }, 600);
    } catch (err: any) {
      console.error('Login request error:', err);
      setErrorMessage('Network or server error encountered. Please try again.');
      setIsLoading(false);
    }
  };

  return (
    <div className="relative min-h-screen w-full flex items-center justify-center p-4 sm:p-6 overflow-hidden select-none">
      {/* 1. Cinematic Background Image (waguri.png with cover positioning & entrance animation) */}
      <div
        className="fixed inset-0 w-full h-full bg-cover bg-center bg-no-repeat login-bg-animation pointer-events-none"
        style={{
          backgroundImage: "url('/waguri.png')",
        }}
      />

      {/* 2. Dark Purple & Black Vignette Overlay for optimal contrast and aesthetics */}
      <div className="fixed inset-0 bg-gradient-to-b from-black/65 via-purple-950/45 to-black/85 backdrop-blur-[1px] pointer-events-none" />
      <div className="fixed inset-0 bg-[radial-gradient(circle_at_center,_var(--tw-gradient-stops))] from-transparent via-black/40 to-black/80 pointer-events-none" />

      {/* 3. Glassmorphism Login Card with Upward Entrance Animation */}
      <div className="relative w-full max-w-md z-10 login-card-animation">
        {/* Glow halo behind the card */}
        <div className="absolute -inset-1 bg-gradient-to-r from-purple-600/30 to-indigo-600/30 rounded-3xl blur-xl opacity-75 group-hover:opacity-100 transition duration-1000 -z-10" />

        <div className="relative backdrop-blur-2xl bg-zinc-950/75 border border-purple-500/25 shadow-2xl shadow-purple-950/60 rounded-3xl p-6 sm:p-8 overflow-hidden">
          {/* Subtle top neon border accent */}
          <div className="absolute top-0 left-8 right-8 h-px bg-gradient-to-r from-transparent via-purple-400/60 to-transparent" />

          {/* Branding & Header Section */}
          <div className="text-center space-y-3 mb-6 login-stagger-1">
            <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-gradient-to-br from-purple-600/20 to-purple-900/40 border border-purple-500/30 shadow-inner shadow-purple-500/20 text-purple-300">
              <Bot className="w-7 h-7 drop-shadow-[0_0_12px_rgba(168,85,247,0.7)]" />
            </div>

            <div>
              <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-purple-950/80 text-purple-300 border border-purple-500/40 shadow-sm uppercase tracking-wider mb-1.5">
                <ShieldCheck className="w-3.5 h-3.5 text-purple-400" />
                <span>Admin Login</span>
              </div>
              <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
                Waguri Bot
              </h1>
              <p className="text-xs sm:text-sm text-purple-200/70 font-medium">
                Secure Admin Panel
              </p>
            </div>
          </div>

          {/* Error & Success Feedback Banners */}
          {errorMessage && (
            <div className="mb-5 p-3.5 rounded-xl bg-red-950/60 border border-red-500/30 text-red-200 text-xs sm:text-sm flex items-start gap-2.5 shadow-sm animate-in fade-in duration-200">
              <ShieldAlert className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
              <div className="flex-1 font-medium leading-relaxed">{errorMessage}</div>
            </div>
          )}

          {successMessage && (
            <div className="mb-5 p-3.5 rounded-xl bg-emerald-950/60 border border-emerald-500/30 text-emerald-200 text-xs sm:text-sm flex items-start gap-2.5 shadow-sm animate-in fade-in duration-200">
              <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
              <div className="flex-1 font-medium leading-relaxed">{successMessage}</div>
            </div>
          )}

          {/* Login Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Email Field */}
            <div className="space-y-1.5 login-stagger-2">
              <label
                htmlFor="admin-email"
                className="block text-xs font-semibold text-zinc-300 uppercase tracking-wider"
              >
                Email Address
              </label>
              <div className="relative group">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-zinc-400 group-focus-within:text-purple-400 transition-colors">
                  <Mail className="w-4 h-4" />
                </div>
                <input
                  id="admin-email"
                  type="email"
                  required
                  autoComplete="username"
                  disabled={isLoading}
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="admin@waguri.bot"
                  className="w-full pl-10 pr-4 py-2.5 sm:py-3 rounded-xl bg-zinc-900/80 border border-zinc-800 text-zinc-100 placeholder:text-zinc-500 text-sm focus:outline-none focus:border-purple-500/80 focus:ring-2 focus:ring-purple-500/20 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                />
              </div>
            </div>

            {/* Password Field with Show/Hide Toggle */}
            <div className="space-y-1.5 login-stagger-3">
              <label
                htmlFor="admin-password"
                className="block text-xs font-semibold text-zinc-300 uppercase tracking-wider"
              >
                Password
              </label>
              <div className="relative group">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-zinc-400 group-focus-within:text-purple-400 transition-colors">
                  <Lock className="w-4 h-4" />
                </div>
                <input
                  id="admin-password"
                  type={showPassword ? 'text' : 'password'}
                  required
                  autoComplete="current-password"
                  disabled={isLoading}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••••••"
                  className="w-full pl-10 pr-11 py-2.5 sm:py-3 rounded-xl bg-zinc-900/80 border border-zinc-800 text-zinc-100 placeholder:text-zinc-500 text-sm focus:outline-none focus:border-purple-500/80 focus:ring-2 focus:ring-purple-500/20 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                />
                <button
                  type="button"
                  tabIndex={-1}
                  onClick={() => setShowPassword((prev) => !prev)}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                  className="absolute inset-y-0 right-0 pr-3.5 flex items-center text-zinc-400 hover:text-purple-300 transition-colors focus:outline-none"
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {/* Purple Gradient Login Button */}
            <div className="pt-2 login-stagger-4">
              <button
                type="submit"
                disabled={isLoading}
                className="w-full py-3 px-4 rounded-xl font-semibold text-sm text-white bg-gradient-to-r from-purple-600 via-purple-700 to-indigo-600 hover:from-purple-500 hover:via-purple-600 hover:to-indigo-500 active:scale-[0.99] shadow-lg shadow-purple-600/30 hover:shadow-purple-600/50 transition-all flex items-center justify-center gap-2 cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed disabled:transform-none"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin text-purple-200" />
                    <span>Verifying Credentials...</span>
                  </>
                ) : (
                  <>
                    <span>Sign In to Admin Panel</span>
                    <ArrowRight className="w-4 h-4" />
                  </>
                )}
              </button>
            </div>
          </form>

          {/* Security & Official Bot Footnote */}
          <div className="mt-6 pt-4 border-t border-zinc-800/60 text-center space-y-1.5 login-stagger-5">
            <div className="flex items-center justify-center gap-1.5 text-[11px] text-zinc-400">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
              <span>Encrypted Session • Bcrypt Protected</span>
            </div>
            <p className="text-[10px] text-zinc-500">
              Authorized personnel only. All access attempts are audited.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
