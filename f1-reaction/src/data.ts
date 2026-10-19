import type { RaceData, RaceIndexEntry } from './types';

export async function loadIndex(): Promise<RaceIndexEntry[]> {
  const res = await fetch('/data/index.json');
  if (!res.ok) throw new Error(`Could not load race index (${res.status})`);
  const all: RaceIndexEntry[] = await res.json();
  return all.filter((r) => r.usable);
}

export async function loadRace(file: string): Promise<RaceData> {
  const res = await fetch(`/data/${file}`);
  if (!res.ok) throw new Error(`Could not load ${file} (${res.status})`);
  return res.json();
}
