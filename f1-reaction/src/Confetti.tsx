import type { CSSProperties } from 'react';

const COLOURS = ['#e10600', '#f5f5f7', '#b34cff', '#ffd400', '#00d26a'];
const PIECES = 70;

// Deterministic "random" so the component stays pure (same pieces every render)
function rnd(i: number, salt: number): number {
  const x = Math.sin(i * 127.1 + salt * 311.7) * 43758.5453;
  return x - Math.floor(x);
}

export default function Confetti() {
  return (
    <div className="confetti" aria-hidden="true">
      {Array.from({ length: PIECES }, (_, i) => {
        const style = {
          left: `${rnd(i, 1) * 100}%`,
          width: `${6 + rnd(i, 2) * 6}px`,
          height: `${10 + rnd(i, 3) * 8}px`,
          background: COLOURS[i % COLOURS.length],
          animationDelay: `${rnd(i, 4) * 0.5}s`,
          animationDuration: `${1.9 + rnd(i, 5) * 1.4}s`,
          '--dx': `${(rnd(i, 6) - 0.5) * 240}px`,
          '--spin': `${360 + rnd(i, 7) * 720}deg`,
        } as CSSProperties;
        return <i key={i} style={style} />;
      })}
    </div>
  );
}
