'use client';

import React from 'react';
import { usePathname } from 'next/navigation';
import Sidebar from '@/components/Sidebar';

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isLoginPage = pathname === '/login';

  if (isLoginPage) {
    return <div className="min-h-screen w-full bg-black">{children}</div>;
  }

  return (
    <div className="flex flex-col lg:flex-row min-h-screen bg-black w-full overflow-x-hidden">
      {/* Fixed Responsive Sidebar with Live User Panel Quick Access */}
      <Sidebar />

      {/* Main Content Area */}
      <main className="flex-1 lg:pl-72 flex flex-col min-w-0 w-full transition-all bg-black pb-16 lg:pb-12">
        {children}
      </main>
    </div>
  );
}
