/** The speed buttons on the time bar, and which simulation layers each one runs. */
import { SECONDS_PER_DAY } from './julian.ts';

export const DAYS_PER_YEAR = 365.25;
export const DAYS_PER_MONTH = DAYS_PER_YEAR / 12;

export enum TimeScale {
  Paused = 0,
  RealTime = 1,
  MinutePerSecond = 2,
  HourPerSecond = 3,
  DayPerSecond = 4,
  MonthPerSecond = 5,
  YearPerSecond = 6,
  DecadePerSecond = 7,
}

export const ALL_SCALES: TimeScale[] = [
  TimeScale.Paused,
  TimeScale.RealTime,
  TimeScale.MinutePerSecond,
  TimeScale.HourPerSecond,
  TimeScale.DayPerSecond,
  TimeScale.MonthPerSecond,
  TimeScale.YearPerSecond,
  TimeScale.DecadePerSecond,
];

export enum SimLayers {
  None = 0,
  /** Individual agents near the camera. */
  Micro = 1,
  /** Settlements, building slots, roads. */
  Meso = 2,
  /** Cohorts, economy, polities. */
  Macro = 4,
}

export function simSecondsPerRealSecond(scale: TimeScale): number {
  switch (scale) {
    case TimeScale.Paused: return 0;
    case TimeScale.RealTime: return 1;
    case TimeScale.MinutePerSecond: return 60;
    case TimeScale.HourPerSecond: return 3600;
    case TimeScale.DayPerSecond: return SECONDS_PER_DAY;
    case TimeScale.MonthPerSecond: return DAYS_PER_MONTH * SECONDS_PER_DAY;
    case TimeScale.YearPerSecond: return DAYS_PER_YEAR * SECONDS_PER_DAY;
    case TimeScale.DecadePerSecond: return 10 * DAYS_PER_YEAR * SECONDS_PER_DAY;
  }
}

/** Micro agents are simulated only up to one hour per second; beyond that they become crowd density. */
export function activeLayers(scale: TimeScale): number {
  switch (scale) {
    case TimeScale.Paused: return SimLayers.None;
    case TimeScale.RealTime:
    case TimeScale.MinutePerSecond: return SimLayers.Micro;
    case TimeScale.HourPerSecond: return SimLayers.Micro | SimLayers.Macro;
    case TimeScale.DayPerSecond: return SimLayers.Meso | SimLayers.Macro;
    default: return SimLayers.Meso | SimLayers.Macro;
  }
}

/** Adaptive macro step length in days: daily up to a day per second, monthly and yearly beyond. */
export function macroStepDays(scale: TimeScale): number {
  switch (scale) {
    case TimeScale.MonthPerSecond: return DAYS_PER_MONTH;
    case TimeScale.YearPerSecond:
    case TimeScale.DecadePerSecond: return DAYS_PER_YEAR;
    default: return 1;
  }
}

export function scaleLabel(scale: TimeScale): string {
  switch (scale) {
    case TimeScale.Paused: return '일시정지';
    case TimeScale.RealTime: return '실시간';
    case TimeScale.MinutePerSecond: return '1분/초';
    case TimeScale.HourPerSecond: return '1시간/초';
    case TimeScale.DayPerSecond: return '1일/초';
    case TimeScale.MonthPerSecond: return '1개월/초';
    case TimeScale.YearPerSecond: return '1년/초';
    case TimeScale.DecadePerSecond: return '10년/초';
  }
}

export function scaleShortLabel(scale: TimeScale): string {
  switch (scale) {
    case TimeScale.Paused: return '❚❚';
    case TimeScale.RealTime: return '1×';
    case TimeScale.MinutePerSecond: return '분';
    case TimeScale.HourPerSecond: return '시';
    case TimeScale.DayPerSecond: return '일';
    case TimeScale.MonthPerSecond: return '월';
    case TimeScale.YearPerSecond: return '년';
    case TimeScale.DecadePerSecond: return '10년';
  }
}
