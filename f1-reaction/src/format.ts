/** 231 -> "0.231" */
export function formatSec(ms: number): string {
  return (ms / 1000).toFixed(3);
}

/** Signed gap in seconds: 12 -> "+0.012", -40 -> "-0.040" */
export function formatGap(ms: number): string {
  const sign = ms > 0 ? '+' : ms < 0 ? '-' : '';
  return `${sign}${(Math.abs(ms) / 1000).toFixed(3)}`;
}
