import type { TimedDriver } from './types';

export interface Ranking {
  position: number; // 1-based; you
  total: number; // drivers + you
  sorted: TimedDriver[]; // the grid, fastest first
  aheadCount: number; // drivers faster than (or equal to) you
}

/**
 * Where would userMs have finished on this grid?
 * If a driver has exactly the same time, the driver is placed ahead of you.
 */
export function rankAgainstGrid(userMs: number, drivers: TimedDriver[]): Ranking {
  const sorted = [...drivers].sort((a, b) => a.reactionMs - b.reactionMs);
  const aheadCount = sorted.filter((d) => d.reactionMs <= userMs).length;
  return {
    position: aheadCount + 1,
    total: sorted.length + 1,
    sorted,
    aheadCount,
  };
}

export function ordinal(n: number): string {
  const rem100 = n % 100;
  if (rem100 >= 11 && rem100 <= 13) return `${n}th`;
  switch (n % 10) {
    case 1: return `${n}st`;
    case 2: return `${n}nd`;
    case 3: return `${n}rd`;
    default: return `${n}th`;
  }
}
