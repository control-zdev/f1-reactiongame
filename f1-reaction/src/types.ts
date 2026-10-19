export type DriverStatus =
  | 'ok'
  | 'outlier'
  | 'jump_start'
  | 'no_launch'
  | 'no_data'
  | 'already_moving'
  | 'bad_fit'
  | 'too_fast';

export interface DriverStart {
  number: string;
  code: string;
  name: string;
  team: string;
  grid: number | null;
  launchMs: number | null;
  reactionMs: number | null; // null = no valid time, left off the grid
  reactionSec: number | null;
  status: DriverStatus;
}

// A driver who has a valid time (what the ranking works with)
export type TimedDriver = DriverStart & { reactionMs: number; reactionSec: number };

export interface RaceIndexEntry {
  year: number;
  round: number;
  eventName: string;
  location: string;
  country: string;
  file: string;
  usable: boolean;
  validDrivers: number;
}

export interface RaceData {
  year: number;
  round: number;
  eventName: string;
  location: string;
  usable: boolean;
  drivers: DriverStart[];
}
