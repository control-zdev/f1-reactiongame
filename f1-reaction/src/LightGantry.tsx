import { LIGHT_COUNT } from './useReactionGame';

interface Props {
  lightsOn: number;
}

export default function LightGantry({ lightsOn }: Props) {
  return (
    <div
      className="gantry"
      data-lit={lightsOn}
      role="img"
      aria-label={`Start lights: ${lightsOn} of ${LIGHT_COUNT} on`}
    >
      {Array.from({ length: LIGHT_COUNT }, (_, i) => (
        <div key={i} className={i < lightsOn ? 'unit on' : 'unit'}>
          <span className="lamp" />
          <span className="lamp" />
        </div>
      ))}
    </div>
  );
}
