import React, { useMemo } from 'react';

// Helper to generate random box shadows
const generateBoxShadows = (n) => {
  let value = `${Math.floor(Math.random() * 2000)}px ${Math.floor(Math.random() * 2000)}px #FFF`;
  for (let i = 2; i <= n; i++) {
    value += `, ${Math.floor(Math.random() * 2000)}px ${Math.floor(Math.random() * 2000)}px #FFF`;
  }
  return value;
};

export function ParallaxStarsBackground({
  children,
  className = "",
  speed = 1
}) {
  // Memoize shadows so they don't regenerate on re-renders
  const shadowsSmall = useMemo(() => generateBoxShadows(700), []);
  const shadowsMedium = useMemo(() => generateBoxShadows(200), []);
  const shadowsBig = useMemo(() => generateBoxShadows(100), []);

  return (
    <div className={`fixed inset-0 w-full h-full overflow-hidden bg-[#000000] ${className}`} style={{ zIndex: -1 }}>
      {/* Inline styles for the animations */}
      <style>{`
        @keyframes animStar {
          from { transform: translateY(0px); }
          to { transform: translateY(-2000px); }
        }
      `}</style>

      {/* Stars Layer 1 (Small) */}
      <div 
        className="absolute left-0 top-0 w-[1px] h-[1px] bg-transparent z-0 animate-[animStar_50s_linear_infinite]"
        style={{ 
          boxShadow: shadowsSmall,
          animationDuration: `${50 / speed}s`
        }}
      >
        <div 
          className="absolute top-[2000px] w-[1px] h-[1px] bg-transparent"
          style={{ boxShadow: shadowsSmall }}
        />
      </div>

      {/* Stars Layer 2 (Medium) */}
      <div 
        className="absolute left-0 top-0 w-[2px] h-[2px] bg-transparent z-0 animate-[animStar_100s_linear_infinite]"
        style={{ 
          boxShadow: shadowsMedium,
          animationDuration: `${100 / speed}s`
        }}
      >
        <div 
          className="absolute top-[2000px] w-[2px] h-[2px] bg-transparent"
          style={{ boxShadow: shadowsMedium }}
        />
      </div>

      {/* Stars Layer 3 (Big) */}
      <div 
        className="absolute left-0 top-0 w-[3px] h-[3px] bg-transparent z-0 animate-[animStar_150s_linear_infinite]"
        style={{ 
          boxShadow: shadowsBig,
          animationDuration: `${150 / speed}s`
        }}
      >
        <div 
          className="absolute top-[2000px] w-[3px] h-[3px] bg-transparent"
          style={{ boxShadow: shadowsBig }}
        />
      </div>

      {/* Noise Overlay to keep Neo-Brutalist aesthetic */}
      <div 
        className="absolute inset-0 w-full h-full pointer-events-none z-0"
        style={{
          backgroundImage: 'url("data:image/svg+xml,%3Csvg viewBox=\'0 0 200 200\' xmlns=\'http://www.w3.org/2000/svg\'%3E%3Cfilter id=\'noiseFilter\'%3E%3CfeTurbulence type=\'fractalNoise\' baseFrequency=\'0.85\' numOctaves=\'3\' stitchTiles=\'stitch\'/%3E%3C/filter%3E%3Crect width=\'100%25\' height=\'100%25\' filter=\'url(%23noiseFilter)\' opacity=\'0.08\'/%3E%3C/svg%3E")',
        }}
      />

      {/* Content Overlay */}
      <div className="relative z-10 w-full h-full">
        {children}
      </div>
    </div>
  );
}

export default ParallaxStarsBackground;
