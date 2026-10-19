import type { CSSProperties } from 'react';
import { formatGap, formatSec } from './format';
import { ordinal, rankAgainstGrid } from './ranking';
import { teamColour } from './teams';
import type { TimedDriver } from './types';

interface Props {
  drivers: TimedDriver[];
  bestMs: number;
}

export default function ResultPanel({ drivers, bestMs }: Props) {
  const { sorted, position, total, aheadCount } = rankAgainstGrid(bestMs, drivers);

  // slot "you" into the grid at your finishing position
  const rows = [
    ...sorted.slice(0, aheadCount).map((d) => ({ kind: 'driver' as const, d })),
    { kind: 'you' as const },
    ...sorted.slice(aheadCount).map((d) => ({ kind: 'driver' as const, d })),
  ];

  return (
    <section className="tower" aria-label="Timing tower">
      <h3 className="tower-title">
        Your best would be {ordinal(position)} of {total}
      </h3>
      <ol className="tower-list">
        {rows.map((row, i) => {
          const style = { '--i': i } as CSSProperties;
          if (row.kind === 'you') {
            return (
              <li key="you" className={i === 0 ? 'row you fastest' : 'row you'} style={style}>
                <span className="pos">{i + 1}</span>
                <span className="bar" />
                <span className="code">YOU</span>
                <span className="name">Your best</span>
                <span className="time">{formatSec(bestMs)}</span>
                <span className="gap" />
              </li>
            );
          }
          const diff = row.d.reactionMs - bestMs; // + means you beat them
          const cls = ['row', i === 0 ? 'fastest' : '', diff > 0 ? 'beaten' : ''].join(' ').trim();
          return (
            <li key={row.d.number} className={cls} style={style}>
              <span className="pos">{i + 1}</span>
              <span className="bar" style={{ background: teamColour(row.d.team) }} />
              <span className="code">{row.d.code}</span>
              <span className="name">{row.d.name}</span>
              <span className="time">{formatSec(row.d.reactionMs)}</span>
              <span className={diff > 0 ? 'gap up' : 'gap down'}>{formatGap(diff)}</span>
            </li>
          );
        })}
      </ol>
      <p className="note">
        Driver times are estimated from telemetry. Gaps show each driver against you: green means you beat them.
      </p>
    </section>
  );
}
