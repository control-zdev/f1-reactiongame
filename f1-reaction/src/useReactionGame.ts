import { useCallback, useEffect, useRef, useState } from 'react';

export type Phase = 'idle' | 'countdown' | 'running' | 'finished' | 'jumpStart';

export const LIGHT_COUNT = 5;
const LIGHT_INTERVAL_MS = 1000; // one more light every second
const HOLD_MIN_MS = 200; // all five lit for a random time...
const HOLD_MAX_MS = 3000; // ...so nobody can predict lights out
const RESTART_LOCK_MS = 400; // ignore a second Space tap right after a result

interface Options {
  onFinish?: (reactionMs: number) => void;
}

/** Key events carry their own timestamp, which is more exact than "now" inside the handler. */
function eventTime(e: KeyboardEvent): number {
  const now = performance.now();
  return e.timeStamp > 0 && Math.abs(e.timeStamp - now) < 1000 ? e.timeStamp : now;
}

export function useReactionGame({ onFinish }: Options = {}) {
  const [phase, setPhase] = useState<Phase>('idle');
  const [lightsOn, setLightsOn] = useState(0);
  const [elapsedMs, setElapsedMs] = useState(0);
  const [reactionMs, setReactionMs] = useState<number | null>(null);

  // Refs hold values that must not trigger a re-render
  const phaseRef = useRef<Phase>('idle'); // what the key handler reads
  const timers = useRef<number[]>([]);
  const lightsOutAt = useRef(0);
  const lockedUntil = useRef(0);
  const onFinishRef = useRef(onFinish);

  useEffect(() => {
    onFinishRef.current = onFinish; // always call the latest callback
  });

  const goTo = useCallback((next: Phase) => {
    phaseRef.current = next;
    setPhase(next);
  }, []);

  const clearTimers = useCallback(() => {
    timers.current.forEach((id) => window.clearTimeout(id));
    timers.current = [];
  }, []);

  const start = useCallback(() => {
    if (performance.now() < lockedUntil.current) return;
    clearTimers();
    setReactionMs(null);
    setElapsedMs(0);
    setLightsOn(0);
    goTo('countdown');

    for (let i = 1; i <= LIGHT_COUNT; i++) {
      timers.current.push(window.setTimeout(() => setLightsOn(i), i * LIGHT_INTERVAL_MS));
    }

    const hold = HOLD_MIN_MS + Math.random() * (HOLD_MAX_MS - HOLD_MIN_MS);
    timers.current.push(
      window.setTimeout(() => {
        lightsOutAt.current = performance.now(); // the clock starts here
        setLightsOn(0);
        goTo('running');
      }, LIGHT_COUNT * LIGHT_INTERVAL_MS + hold),
    );
  }, [clearTimers, goTo]);

  const jumpStart = useCallback(() => {
    clearTimers();
    lockedUntil.current = performance.now() + RESTART_LOCK_MS;
    goTo('jumpStart');
  }, [clearTimers, goTo]);

  const finish = useCallback(
    (at: number) => {
      const ms = Math.max(0, Math.round(at - lightsOutAt.current));
      lockedUntil.current = performance.now() + RESTART_LOCK_MS;
      setReactionMs(ms);
      setElapsedMs(ms);
      goTo('finished');
      onFinishRef.current?.(ms);
    },
    [goTo],
  );

  // Space bar: stops the clock, or starts a new run when no run is active
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.code !== 'Space' || e.repeat) return;
      const current = phaseRef.current;

      if (current === 'countdown') {
        e.preventDefault();
        jumpStart();
      } else if (current === 'running') {
        e.preventDefault();
        finish(eventTime(e));
      } else if (!(e.target instanceof HTMLElement && e.target.closest('select, input, textarea'))) {
        e.preventDefault(); // stops the page scrolling
        start();
      }
    }
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [start, jumpStart, finish]);

  // The on-screen clock, redrawn every frame while running
  useEffect(() => {
    if (phase !== 'running') return;
    let frame = 0;
    const tick = () => {
      setElapsedMs(performance.now() - lightsOutAt.current);
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [phase]);

  // Stop any pending timers if the component goes away mid-sequence
  useEffect(() => clearTimers, [clearTimers]);

  return { phase, lightsOn, elapsedMs, reactionMs, start };
}
