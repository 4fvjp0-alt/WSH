/**
 * Stock-and-flow economy. Deliberately small: food decides whether people live, materials decide
 * whether they can build, and the treasury decides whether the state can raise walls and palaces.
 */
import { ERA_PROFILES, Era } from '../era/eras.ts';

export interface EconomyState {
  /** Person-years of food in store. */
  foodStock: number;
  /** Cubic-metre-equivalents of timber, stone, clay. */
  timber: number;
  stone: number;
  clay: number;
  /** Abstract state revenue used for monumental building. */
  treasury: number;
}

export interface EconomyInputs {
  era: Era;
  /** A capital draws harder on the wider country's grain. */
  isCapital: boolean;
  workers: number;
  population: number;
  /** Sum of fertility over the settlement's farm cells. */
  farmQuality: number;
  /** Sum of woodland/stone/clay over the claimed cells. */
  woodland: number;
  stone: number;
  clay: number;
  /** 0..1 weather modifier for the year: drought and flood pull it down. */
  harvestModifier: number;
  years: number;
}

export interface EconomyResult {
  foodProduced: number;
  foodImported: number;
  foodConsumed: number;
  /** Food per person over the step; 1.0 is subsistence. */
  foodRatio: number;
  materialsProduced: number;
}

export function newEconomy(population: number): EconomyState {
  return {
    foodStock: population * 0.35,
    timber: population * 0.1,
    stone: population * 0.02,
    clay: population * 0.05,
    treasury: 0,
  };
}

/**
 * Share of a settlement's food that arrives from beyond the play area.
 *
 * The map is 38 x 32 km: it holds the city, not the country that fed it. Hanseong Baekje lived
 * largely off its own floodplain; Hanyang was provisioned by grain tribute shipped up the Han from
 * the whole peninsula; modern Seoul imports essentially all of it.
 */
export function tradeShare(era: Era, isCapital: boolean): number {
  const base = [0.2, 0.34, 0.45, 0.76, 0.82, 0.9, 0.95, 0.99, 0.995][era] ?? 0.5;
  return Math.min(0.995, base + (isCapital ? 0.08 : 0));
}

export function stepEconomy(state: EconomyState, input: EconomyInputs): EconomyResult {
  const p = ERA_PROFILES[input.era];
  const { years, population, workers } = input;

  // Farmers are whoever is not doing urban work.
  const farmers = workers * (1 - p.urbanShare);
  // One farmer works about a hectare; a hectare of good land feeds roughly 17 people in antiquity
  // and far more once there are modern inputs.
  const landLimit = input.farmQuality * p.farmYield * 15;
  const labourLimit = farmers * p.farmYield * 4;
  const local = Math.min(labourLimit, landLimit) * input.harvestModifier * years;

  const needed = population * years;
  const share = tradeShare(input.era, input.isCapital);
  // A bad year is bad everywhere, but long-distance trade smooths it a little.
  const imported = needed * share * (1 - (1 - input.harvestModifier) * 0.6);

  state.foodStock += local + imported - needed;
  const cap = population * 2.5;
  if (state.foodStock > cap) state.foodStock = cap;
  if (state.foodStock < 0) state.foodStock = 0;

  const supply = local + imported + Math.min(state.foodStock, needed * 0.5);
  const foodRatio = needed > 0 ? supply / needed : 1;

  const urbanWorkers = workers * p.urbanShare;
  const materials = urbanWorkers * years * 0.5;
  state.timber += materials * 0.5 * (0.3 + input.woodland);
  state.stone += materials * 0.2 * (0.3 + input.stone);
  state.clay += materials * 0.3 * (0.3 + input.clay);

  const taxRate = input.era >= Era.Colonial ? 0.18 : 0.08;
  state.treasury += Math.max(0, local + imported - needed) * taxRate + urbanWorkers * years * 0.02;

  return { foodProduced: local, foodImported: imported, foodConsumed: needed, foodRatio, materialsProduced: materials };
}

/** Yearly weather. Monsoon failures and floods are the main shocks before modern flood control. */
export function harvestModifier(_year: number, rand: number, era: Era): number {
  const base = 0.85 + rand * 0.3;
  const modernBuffer = era >= Era.Industrial ? 0.8 : era >= Era.Colonial ? 0.4 : 0;
  return 1 + (base - 1) * (1 - modernBuffer);
}
