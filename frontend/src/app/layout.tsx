import type { Metadata } from 'next';
import { Inter, JetBrains_Mono } from 'next/font/google';
import './globals.css';
import Sidebar from '@/components/Sidebar';
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
          <div className="flex flex-col lg:flex-row min-h-screen bg-black w-full overflow-x-hidden">
            {/* Fixed Responsive Sidebar with Live User Panel Quick Access */}
            <Sidebar />

            {/* Main Content Area */}
            <main className="flex-1 lg:pl-72 flex flex-col min-w-0 w-full transition-all bg-black pb-16 lg:pb-12">
              {children}
            </main>
          </div>
        </UserModalProvider>
      </body>
    </html>
  );
}