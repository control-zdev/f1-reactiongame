import { useMemo, useState } from 'react';
import Clock from './Clock';
import Confetti from './Confetti';
import LightGantry from './LightGantry';
import ResultPanel from './ResultPanel';
import { formatSec } from './format';
import { rankAgainstGrid } from './ranking';
import { readBest, writeBest } from './storage';
import type { DriverStart, RaceData, TimedDriver } from './types';
import { useReactionGame, type Phase } from './useReactionGame';
import './game.css';

const STATUS: Record<Phase, string> = {
  idle: 'Start when you are ready',
  countdown: 'Wait for lights out',
  running: 'Go! Hit Space',
  finished: 'Clock stopped',
  jumpStart: 'Jump start. You moved before lights out.',
};

const isTimed = (d: DriverStart): d is TimedDriver =>
  d.reactionMs !== null && d.reactionSec !== null;

interface Props {
  race: RaceData;
}

export default function Game({ race }: Props) {
  const raceKey = `${race.year}-${race.round}`;
  const drivers = useMemo(() => race.drivers.filter(isTimed), [race]);
  const [best, setBest] = useState<number | null>(() => readBest(raceKey));
  const [newBest, setNewBest] = useState(false);

  const { phase, lightsOn, elapsedMs, reactionMs, start } = useReactionGame({
    onFinish: (ms) => {
      const improved = best === null || ms < best;
      setNewBest(improved);
      if (improved) {
        setBest(ms);
        writeBest(raceKey, ms);
      }
    },
  });

  const canStart = phase === 'idle' || phase === 'finished' || phase === 'jumpStart';
  const attempt = reactionMs !== null ? rankAgainstGrid(reactionMs, drivers) : null;
  const beaten = attempt ? drivers.length - attempt.aheadCount : 0;
  const wonGrid = attempt?.position === 1;

  return (
    <>
      <section className="game" data-phase={phase}>
        <header className="game-head">
          <span className="year">{race.year}</span>
          <h2>{race.eventName}</h2>
        </header>

        <LightGantry lightsOn={lightsOn} />

        <div className="clock-plate">
          <Clock ms={elapsedMs} />
        </div>

        <p className="status" aria-live="polite">
          {STATUS[phase]}
        </p>

        {phase === 'finished' && attempt && reactionMs !== null && (
          <div className={wonGrid ? 'lower-third win' : 'lower-third'}>
            <div className="lt-pos">
              <span className="lt-rank">P{attempt.position}</span>
              <span className="lt-of">of {attempt.total}</span>
            </div>
            <div className="lt-body">
              <span className="lt-time">{formatSec(reactionMs)}s</span>
              <span className="lt-line">
                {wonGrid
                  ? 'Faster than the whole grid'
                  : beaten === 0
                    ? 'No drivers beaten this time'
                    : `You beat ${beaten} of ${drivers.length} drivers`}
              </span>
            </div>
            {newBest ? (
              <span className="chip pb">New personal best</span>
            ) : (
              best !== null && <span className="chip">Best {formatSec(best)}s</span>
            )}
          </div>
        )}

        {canStart && (
          <div className="actions">
            <button type="button" className="start" onClick={start}>
              {phase === 'idle' ? 'Start' : 'Try again'}
            </button>
            <span className="hint">
              or press <kbd>Space</kbd>
            </span>
          </div>
        )}
      </section>

      {phase === 'finished' && wonGrid && <Confetti />}
      {best !== null && canStart && <ResultPanel drivers={drivers} bestMs={best} />}
    </>
  );
}
