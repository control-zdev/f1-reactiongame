// Approximate team colours for the bar beside each driver. Matching is by name
// fragment because team names changed between 2021 and 2026.
export function teamColour(team: string): string {
  const t = team.toLowerCase().trim();
  if (t.includes('red bull')) return '#3671c6';
  if (t.includes('mercedes')) return '#27f4d2';
  if (t.includes('ferrari')) return '#e80020';
  if (t.includes('mclaren')) return '#ff8000';
  if (t.includes('alpine')) return '#0093cc';
  if (t.includes('aston')) return '#229971';
  if (t.includes('alphatauri')) return '#5e8faa';
  if (t === 'rb' || t.includes('racing bulls')) return '#6692ff';
  if (t.includes('alfa')) return '#c92d4b';
  if (t.includes('haas')) return '#b6babd';
  if (t.includes('williams')) return '#64c4ff';
  if (t.includes('sauber')) return '#52e252';
  if (t.includes('audi')) return '#f50537';
  if (t.includes('cadillac')) return '#9aa0a6';
  return '#8c8f9a';
}
