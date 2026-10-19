import { useEffect, useMemo, useState } from 'react';
import { loadIndex, loadRace } from './data';
import Game from './Game';
import './App.css';
import type { RaceData, RaceIndexEntry } from './types';

export default function App() {
  const [index, setIndex] = useState<RaceIndexEntry[]>([]);
  const [location, setLocation] = useState('');
  const [file, setFile] = useState('');
  const [race, setRace] = useState<RaceData | null>(null);
  const [error, setError] = useState<string | null>(null);

  // load the race list once
  useEffect(() => {
    loadIndex()
      .then(setIndex)
      .catch((e: Error) => setError(e.message));
  }, []);

  // load the chosen race whenever the selection changes
  useEffect(() => {
    if (!file) return;
    let cancelled = false;
    loadRace(file)
      .then((data) => {
        if (!cancelled) setRace(data);
      })
      .catch((e: Error) => setError(e.message));
    return () => {
      cancelled = true; // ignore a slow response if the user already picked another race
    };
  }, [file]);

  const locations = useMemo(
    () => [...new Set(index.map((r) => r.location))].sort(),
    [index],
  );

  const races = useMemo(
    () =>
      index
        .filter((r) => r.location === location)
        .sort((a, b) => b.year - a.year || a.round - b.round),
    [index, location],
  );

  function onLocationChange(value: string) {
    setLocation(value);
    setFile('');
    setRace(null);
  }

  function onRaceChange(value: string) {
    setFile(value);
    setRace(null); // clear the old race while the new one loads
  }

  return (
    <main className="app">
      <header className="masthead">
        <h1>Lights out</h1>
        <p>Pick a real race, wait for the five lights to go out, then stop the clock faster than the grid.</p>
      </header>

      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}

      <div className="picker">
        <label className="field">
          <span>Track</span>
          <select value={location} onChange={(e) => onLocationChange(e.target.value)}>
            <option value="">Choose a track…</option>
            {locations.map((l) => (
              <option key={l} value={l}>{l}</option>
            ))}
          </select>
        </label>

        <label className="field">
          <span>Race</span>
          <select value={file} onChange={(e) => onRaceChange(e.target.value)} disabled={!location}>
            <option value="">{location ? 'Choose a race…' : 'Pick a track first'}</option>
            {races.map((r) => (
              <option key={r.file} value={r.file}>
                {r.year} {r.eventName}
              </option>
            ))}
          </select>
        </label>
      </div>

      {/* key = remount the game (fresh state) whenever a different race is chosen */}
      {race && <Game key={`${race.year}-${race.round}`} race={race} />}
    </main>
  );
}
