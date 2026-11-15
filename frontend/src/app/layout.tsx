import type { Metadata } from 'next';
import { Inter, JetBrains_Mono } from 'next/font/google';
import './globals.css';
import Sidebar from '@/components/Sidebar';

const inter = Inter({
  variable: '--font-inter',
  subsets: ['latin'],
});

const jetbrainsMono = JetBrains_Mono({
  variable: '--font-mono',
  subsets: ['latin'],
});

export const metadata: Metadata = {
  title: 'Waguri Bot - Telegram Moderation & Business Secretary Dashboard',
  description: 'Official interactive documentation and commands dashboard for Waguri Telegram Bot (@Ms_Waguri_bot).',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark h-full">
      <body
        className={`${inter.variable} ${jetbrainsMono.variable} font-sans min-h-screen bg-slate-950 text-slate-100 antialiased selection:bg-indigo-500/30 selection:text-indigo-200`}
      >
        <div className="flex min-h-screen">
          {/* Fixed Responsive Sidebar */}
          <Sidebar />

          {/* Main Content Area */}
          <main className="flex-1 lg:pl-72 flex flex-col min-w-0 transition-all">
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
