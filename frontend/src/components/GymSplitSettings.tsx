import { gymPrimaryGroups, gymAccessoryGroups, muscleGroupLabel, type GymSplit } from "../api/types";

/** Configure the smaller groups and abs paired with each rotating primary group. */
export default function GymSplitSettings({ value, disabled, onChange }: {
  value: GymSplit;
  disabled: boolean;
  onChange: (value: GymSplit) => void;
}) {
  return <fieldset className="gym-split-settings" disabled={disabled}>
    <legend>Gym muscle-group split</legend>
    <p className="muted">Plan Chest, Back and Legs sessions; leg targets may move for recovery. Choose the smaller groups and Abs for each.</p>
    {gymPrimaryGroups.map((primary) => <fieldset key={primary}>
      <legend>{muscleGroupLabel(primary)} session</legend>
      <div className="muscle-group-options">{gymAccessoryGroups.map((group) => <label key={group}>
        <input type="checkbox" aria-label={`${muscleGroupLabel(primary)} with ${muscleGroupLabel(group)}`}
          checked={value[primary].includes(group)}
          onChange={(event) => onChange({
            ...value,
            [primary]: event.target.checked
              ? [...value[primary], group]
              : value[primary].filter((item) => item !== group),
          })} />
        {muscleGroupLabel(group)}
      </label>)}</div>
    </fieldset>)}
  </fieldset>;
}
