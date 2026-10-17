import { useEffect, useRef, type ReactElement } from "react";

interface RescheduleDialogProps {
  busy: boolean;
  error: string;
  onRecalculate: () => void;
  onKeep: () => void;
}

/** Ask before replacing a preview; native modal behavior handles focus and Escape. */
export default function RescheduleDialog({
  busy, error, onRecalculate, onKeep,
}: RescheduleDialogProps): ReactElement {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const element = dialog.current;
    if (!element) return;
    // DOM test environments may not implement the native dialog API.
    if (element.showModal) element.showModal();
    else element.setAttribute("open", "");
  }, []);
  return (
    <dialog ref={dialog} className="reschedule-dialog" aria-labelledby="reschedule-heading"
      onCancel={(event) => { event.preventDefault(); if (!busy) onKeep(); }}>
      <h2 id="reschedule-heading">Recalculate suggestions?</h2>
      <p>Your training plan changed. Recalculate the remaining suggestions?</p>
      <p>Removed suggestions stay excluded. Manually moved suggestions keep their dates, and saved workouts stay in place.</p>
      {error && <p role="alert" className="message error">{error}</p>}
      <div className="reschedule-actions">
        <button type="button" disabled={busy} onClick={onRecalculate} autoFocus>
          {busy ? "Recalculating..." : "Recalculate"}
        </button>
        <button type="button" className="secondary" disabled={busy} onClick={onKeep}>
          Keep current suggestions
        </button>
      </div>
    </dialog>
  );
}
