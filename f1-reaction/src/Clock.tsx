import { formatSec } from './format';

interface Props {
  ms: number;
}

// Each character sits in a fixed-width cell so the digits don't jiggle while counting.
export default function Clock({ ms }: Props) {
  const text = formatSec(ms);
  return (
    <div className="clock" role="timer" aria-label={`${text} seconds`}>
      {[...text].map((ch, i) => (
        <span key={i} className={ch === '.' ? 'dot' : 'digit'} aria-hidden="true">
          {ch}
        </span>
      ))}
      <span className="unit" aria-hidden="true">s</span>
    </div>
  );
}
