import { useState } from "react";
import { calculateHeartRateZones, isValidMaxHeartRate } from "../heartRate";

/** Calculate integer bpm ranges live without guessing or storing the user's HRmax. */
export default function HeartRateCalculator() {
  const [maxHeartRate, setMaxHeartRate] = useState("");
  const value = Number(maxHeartRate);
  const valid = maxHeartRate !== "" && isValidMaxHeartRate(value);
  const invalid = maxHeartRate !== "" && !valid;
  const zones = valid ? calculateHeartRateZones(value) : [];

  return (
    <div>
      <h3>Calculate your zones</h3>
      <label>Maximum heart rate (bpm)
        <input type="number" inputMode="numeric" min="50" max="300" step="1"
          placeholder="e.g. 180" value={maxHeartRate}
          aria-invalid={invalid}
          aria-describedby="max-heart-rate-help max-heart-rate-error"
          onChange={(event) => setMaxHeartRate(event.target.value)} />
      </label>
      <p id="max-heart-rate-help" className="muted">
        Enter your known maximum heart rate to calculate ranges instantly.
        This value is used only for this calculator and is cleared when you reload.
      </p>
      <p id="max-heart-rate-error" role="status">
        {invalid ? "Enter a whole number from 50 to 300 bpm." : ""}
      </p>
      {valid && <div className="table-scroll">
        <table>
          <caption>Heart-rate zones for a maximum of {value} bpm</caption>
          <thead><tr>
            <th scope="col">Zone</th><th scope="col">Intensity</th>
            <th scope="col">% of maximum HR</th><th scope="col">Range (bpm)</th>
          </tr></thead>
          <tbody>{zones.map((zone) => <tr key={zone.zone}>
            <th scope="row">Z{zone.zone}</th><td>{zone.label}</td>
            <td>{zone.lowerPercent}-{zone.upperPercent}%</td>
            <td>{zone.minBpm}-{zone.maxBpm} bpm</td>
          </tr>)}</tbody>
        </table>
        <p className="muted">Ranges use whole beats per minute without overlaps.
          Each percentage boundary belongs to the higher zone; Z5 includes your maximum.</p>
      </div>}
    </div>
  );
}
