import type { Metadata } from 'next';
import { Inter, JetBrains_Mono } from 'next/font/google';
import './globals.css';
import AppShell from '@/components/AppShell';
import { UserModalProvider } from '@/context/UserModalContext';

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
        className={`${inter.variable} ${jetbrainsMono.variable} font-sans min-h-screen bg-black text-zinc-100 antialiased selection:bg-white/20 selection:text-white`}
      >
        <UserModalProvider>
          <AppShell>{children}</AppShell>
        </UserModalProvider>
      </body>
    </html>
  );
}