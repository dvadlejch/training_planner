/** Five-zone HRmax model. Each boundary belongs to the next zone, except 100%. */
export const heartRateZones = [
  { zone: 1, label: "Very light / recovery", lowerPercent: 50, upperPercent: 60 },
  { zone: 2, label: "Easy / aerobic endurance", lowerPercent: 60, upperPercent: 70 },
  { zone: 3, label: "Moderate / steady", lowerPercent: 70, upperPercent: 80 },
  { zone: 4, label: "Hard", lowerPercent: 80, upperPercent: 90 },
  { zone: 5, label: "Very hard", lowerPercent: 90, upperPercent: 100 },
] as const;

export function isValidMaxHeartRate(value: number): boolean {
  return Number.isInteger(value) && value >= 50 && value <= 300;
}

export function calculateHeartRateZones(maxHeartRate: number) {
  if (!isValidMaxHeartRate(maxHeartRate)) {
    throw new RangeError("Enter a whole number from 50 to 300 bpm.");
  }
  return heartRateZones.map((zone) => ({
    ...zone,
    minBpm: Math.ceil(maxHeartRate * zone.lowerPercent / 100),
    maxBpm: zone.zone === 5 ? maxHeartRate
      : Math.ceil(maxHeartRate * zone.upperPercent / 100) - 1,
  }));
}
