// Personal bests live in the browser. Every call is wrapped in try/catch because
// localStorage can be blocked (private mode, strict settings) or full.

const key = (race: string) => `f1rt:best:${race}`;

export function readBest(race: string): number | null {
  try {
    const raw = localStorage.getItem(key(race));
    const n = raw === null ? NaN : Number(raw);
    return Number.isFinite(n) ? n : null;
  } catch {
    return null;
  }
}

export function writeBest(race: string, ms: number): void {
  try {
    localStorage.setItem(key(race), String(ms));
  } catch {
    // ignore: the best simply won't persist
  }
}
