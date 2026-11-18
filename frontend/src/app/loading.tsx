import Image from 'next/image';

export default function Loading() {
  return (
    <div className="flex-1 min-h-[60vh] w-full flex flex-col items-center justify-center p-6 select-none animate-in fade-in duration-300">
      <div className="relative flex flex-col items-center">
        {/* Glowing backdrop halo */}
        <div className="absolute -inset-4 bg-purple-600/20 rounded-full blur-2xl animate-pulse pointer-events-none" />

        {/* Logo Container */}
        <div className="relative w-16 h-16 sm:w-20 sm:h-20 rounded-2xl overflow-hidden border border-purple-500/40 bg-purple-950/40 p-2 shadow-xl shadow-purple-950/60 flex items-center justify-center animate-bounce duration-1000">
          <Image
            src="/logo.png"
            alt="Waguri Bot Logo"
            width={64}
            height={64}
            priority
            className="w-full h-full object-contain rounded-xl drop-shadow-[0_0_12px_rgba(168,85,247,0.7)]"
          />
        </div>

        {/* Label & Status */}
        <div className="mt-5 text-center space-y-1.5">
          <h2 className="text-sm sm:text-base font-bold text-white tracking-wide">
            Waguri Bot
          </h2>
          <div className="flex items-center justify-center gap-2 text-xs text-purple-300/80 font-mono">
            <span className="w-2 h-2 rounded-full bg-purple-400 animate-ping" />
            <span>Loading dashboard...</span>
          </div>
        </div>
      </div>
    </div>
  );
}
