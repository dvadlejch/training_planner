# Adaptive Training Planner

> **Status: early local web prototype.** This README is primarily a **product specification** describing the intended application. Features described as *planned* are **not yet implemented**. See [Current implementation](#current-implementation) for what actually works today.

## 1. Project overview

Adaptive Training Planner is a local-first personal training calendar and recommendation application. It helps a user plan, log, and adapt strength and endurance training around an unpredictable work schedule, travel, other commitments, personal preferences, and recovery.

The initial use case combines three weekly gym sessions, progressive running endurance and VO2 max development, and weekend hiking/cycling for long-distance and uphill fitness. The design should remain configurable, rather than hard-code this particular schedule for every user.

**Product promise:** The app recommends training that fits the user's life. It never requires the user to exercise on a particular day, enter biometric data, or accept a suggested workout.

## 2. Core product principles

1. **Flexibility before rigid compliance.** Any day or portion of a day can be blocked, with no limits on how much time the user makes unavailable. A valid plan may contain fewer sessions than the user's targets, or even no workouts.
2. **Suggestions, not commands.** Planning is initiated manually. A generated proposal is a draft until explicitly accepted. Declining suggestions is always allowed.
3. **User control and preservation.** Previously accepted sessions are preserved during replanning by default; completed sessions are never silently modified. The user can intentionally edit, remove, reschedule, or unlock their own entries.
4. **All fitness and readiness inputs are optional.** The app can generate conservative default suggestions without training history, fitness metrics, or recovery scores. Missing data means *unknown*, not zero, poor fitness, or low energy.
5. **Progressive personalization.** Availability and preferences are used when provided; training history, performance metrics, and readiness refine recommendations when available.
6. **Explainability.** Each proposal explains its purpose, the relevant constraints, and any compromises (for example, skipping intervals before a difficult mountain trip).
7. **No punishment for rest.** Deliberate rest, travel, and skipped sessions should not be displayed as personal failures or automatically compensated for with excessive training later.
8. **Safe, conservative adaptation.** Avoid abrupt changes in training volume/intensity and unnecessary clustering of demanding sessions. The app is a planning aid, not medical advice.
9. **Local-first and extensible.** A Python backend and React/TypeScript interface with local storage initially; integrations and more advanced algorithms can be added without replacing core domain logic.

## 3. Supported activities and goals

**Initial activity categories:** gym, easy running, quality/interval running, longer endurance running, hiking, cycling, recovery/rest, and non-training commitments (such as work, travel, appointments, and holidays). Activity types should be extensible.

**Configurable goals:**
- Maintain or develop general strength and muscle, initially at the session level rather than exercise/set level.
- Improve running consistency, aerobic endurance, and VO2 max.
- Build hiking and cycling endurance, especially sustained climbing and cumulative elevation gain.
- Balance these goals with recovery and changing availability.

The user can update the **relative priorities** of goals at any time. A baseline preference might be *approximately three gym sessions and two runs each week, plus weekend outdoors*, but these are **soft targets**, not minimums or hard constraints. The planner may explain when availability prevents satisfying targets.

Gym scheduling should support a **rotating order of familiar workout types**, not a fixed mandatory weekday split: chest + shoulders/biceps, back + triceps/shoulders, and legs + biceps/triceps. Before a demanding hiking/cycling weekend, the planner should generally recommend scheduling strenuous legs earlier in the week or reducing leg load. Detailed gym exercise prescriptions are **out of scope for the initial MVP**.

## 4. Calendar, time blocks, and availability

### 4.1 Primary calendar model

The main GUI is an **interactive weekly calendar**; a monthly overview is a secondary, optional view. The calendar displays both training sessions and non-training commitments.

Each day has three planning sections:

| Section | Purpose |
| --- | --- |
| **Morning** | Before-work exercise, morning commitments, etc. |
| **Afternoon** | Work, travel, appointments, outings, etc. |
| **Evening** | After-work gym, exercise, social commitments, etc. |

These are **logical time blocks**, not strict clock-time limits. The user may optionally specify exact start/end times. The app should eventually allow configurable section boundaries, but this is not required for the first implementation.

A calendar item has a start section and an end section (inclusive), so it may occupy **one, two, or three sections on a day**. For instance, a long hike can occupy morning + afternoon, or all three sections; a gym visit can occupy evening. Support for truly **multi-day events** (such as a trekking weekend) is desirable as a follow-on capability. Exact times, if provided, refine placement without making timed scheduling mandatory.

### 4.2 Availability

- Mark any entire day or any combination of morning/afternoon/evening as unavailable; this is allowed for any number of days.
- Record non-training commitments and, where appropriate, mark the occupied blocks as unavailable for training suggestions.
- Leave a block empty without promising to train in it. **Free does not mean required to fill.**
- Support explicit preferences such as *prefer gym Tuesday/Wednesday/Friday evenings around 18:30* or *Monday/Thursday may be unavailable*, without converting them to requirements.
- Never place a proposed workout in an unavailable block or in conflict with another accepted booking; an overlapping option would need explicit user action to resolve.
- Let users view, add, edit, move, resize across sections, and remove calendar items interactively (for example by drag-and-drop), with accessible form-based editing as an alternative.
- Permit a deliberate zero-workout day, rest week, or holiday period.

### 4.3 Session state and ownership

The **target** data model distinguishes: proposed/unaccepted, accepted/planned, completed, skipped/cancelled, and non-training commitments. An accepted item is protected from automatic replanning, whether or not it is explicitly marked as locked. Explicitly locked items are never recommended for movement unless the user unlocks them. Completed history remains intact unless the user deliberately corrects it.

These richer states and lock semantics are *planned*; the current prototype has planned/confirmed/completed/skipped workout statuses. Confirmed means committed but still upcoming; completing a workout is a separate status change. Explicit locks and automatic rescheduling remain future features.

## 5. Training and activity logging

A primary workflow is **one-click or quick completion** of an existing workout; the user may optionally expand it to enter more information or edit a past entry.

**All per-activity fields are optional wherever technically possible:**
- Date, activity and completion status (basic record identity).
- Duration, distance, pace/speed, elevation gain, route or notes.
- Heart-rate information, including average/max HR or time in zones if available.
- Perceived exertion (RPE) and subjective fatigue.
- Relevant fitness estimates, including watch-estimated VO2 max, as separate time-stamped observations.

The UI should avoid requiring detailed metrics just to record that an activity happened. For some activities, only a date and category will be known. Store unknown values as missing/null; never infer that unentered workouts did not occur.

Gym logging currently supports duration, effort, status, optional active calories,
and multiline workout notes for exercises, weights and repetitions. Structured
exercise/set records, gym session subtypes and performance trends remain planned.

## 6. Optional fitness and recovery information

### 6.1 Fitness metrics

Optional user-entered inputs may include current watch-estimated VO2 max, resting heart rate, recent running performance, endurance duration, climbing/elevation statistics, and historical activity summaries. Record observation dates and, where useful, a source (manual entry vs future imported measurement). Trends are more informative than a single noisy watch estimate.

### 6.2 Readiness

Optional check-ins may include energy, sleep quality, fatigue, muscle soreness, and notes. **No daily check-in is required.** If none exists, the planner falls back to the known schedule and conservative workload rules rather than interpreting absent readiness scores as low readiness.

### 6.3 Levels of available information

The same planner should operate gracefully with:
1. **Minimal information:** general goals/defaults and currently free/unblocked calendar blocks; generate a cautious starting suggestion.
2. **Preferences/availability:** honor stated priorities, target frequencies, preferred windows, commitments, and blocked sections.
3. **History:** additionally consider completed volume, recent intensity, training frequency and hiking/cycling load.
4. **Performance and readiness:** further tailor recommendations using the optional observed statistics and personal feedback.

The planner must be clear about what information actually influenced a suggestion, and should avoid false precision when data is sparse.

## 7. Recommendation and planning engine

### 7.1 Planning behavior

- Suggestions always cover the next **28 days**, starting today; the user presses **Generate suggestions / Replan**.
- The system includes today and the following 27 days. The horizon is fixed rather than user-configurable.
- Recommendations are shown as a **preview** with proposed calendar positions, workout types, approximate duration/intensity, and an explanation.
- The user may accept/reject each suggestion or explicitly accept a batch. **Nothing is committed before approval.**
- Existing accepted sessions stay where they are by default. If the app thinks a change would help, it may offer it as a clearly separate opt-in suggestion, but must not move the session on its own.
- Proposals are generated only for usable free time blocks. When insufficient time is available, propose fewer activities, lower volume or no activities, without treating the week as invalid.
- Later weeks are provisional recommendations, not firm commitments.

### 7.2 Desired training logic

Initial recommendations should be **deterministic, rules-based, and explainable**, with configurable priorities and soft targets. Example rules and objectives:

- Aim for consistent easy running before adding demanding VO2 max sessions. A starting plan may suggest two weekly runs, growing toward an optional third based on consistency and recovery.
- Use mostly easy endurance training; introduce quality running cautiously and generally avoid multiple hard endurance efforts close together.
- Count hard hikes, steep climbs and challenging rides toward weekly endurance and fatigue considerations, rather than evaluating running in isolation.
- Rotate gym muscle-group sessions around weekend plans; avoid a heavy leg session immediately before a demanding hike when practical.
- Permit a short easy morning run and an evening upper-body gym session on the same day where feasible.
- Avoid placing hard intervals too close to heavy leg sessions, long outings or signs of poor recovery.
- Prefer feasible, consistent training to maximizing session count.
- Use reported VO2 max, heart rate, elevation, RPE, and readiness **only when available and relevant**; never require them.
- Gradually progress durations, volume and intensity; avoid aggressive make-up workouts following missed sessions.

Rules should be adjustable and testable, and not encode medical/physiological certainty from limited measurements. In a later phase, an optimization or AI-assisted recommendation layer may augment—but not silently override—the transparent safety and user-approval constraints.

### 7.3 Explainability and trade-offs

Each proposed session should be able to answer:
- Why this activity, and why on this day/block?
- Which goal or soft target does it serve?
- Which calendar restrictions, completed activities or fatigue considerations affected it?
- Which data was missing, and what defaults were used?
- What changed compared with the previous proposal, if this was a replan?

Example: *“Wednesday morning: 30-minute easy run. Monday and Thursday are blocked; Wednesday evening is upper-body gym, so an easy morning run is a feasible second session. Saturday's long climb is the week's demanding endurance session, so no VO2 max intervals are proposed.”*

## 8. Replanning and preservation rules

Replanning is **manual only**. Editing an event or adding a completed workout must **not** silently rewrite the calendar. A discreet *plan may be outdated* indicator may invite the user to request new suggestions.

Replanning invariants:
1. Never alter completed records without direct user editing.
2. Never change accepted/planned sessions without explicit permission.
3. Never replace or schedule through blocked sections or fixed commitments.
4. Never require a minimum number of workouts or an available day.
5. Do not automatically compensate for missed sessions by overloading later days.
6. Allow a user to decline every proposal and continue using the calendar normally.

For optional replacement recommendations, clearly show the proposed change and require separate confirmation. Manual user edits always take precedence over recommendations.

## 9. Illustrative user workflows

### First use with no metrics

The user opens a mostly empty calendar, optionally sets training preferences, marks busy sections, reviews the training targets and presses **Generate suggestions**. The engine generates cautious proposals using defaults and available calendar space. VO2 max, heart rate, past workouts and readiness are **not** prerequisites.

### Busy travel week

Monday and Thursday are blocked, while Tuesday, Wednesday and Friday evenings have room for gym. The user asks for a new plan. The app might suggest a short easy Wednesday morning run, three gym sessions if feasible, and a weekend endurance session; it can instead recommend fewer workouts if the remaining blocks are unavailable. Accepted workouts remain untouched.

### Long mountain day

The user adds a Saturday hike spanning **morning + afternoon**, or the full day. The engine treats it as a long outdoor endurance commitment, recommends lighter leg loading before it, and does not automatically pile a hard running session on top of the weekend. The user can still reject or change every proposed session.

### Partial workout data

The user marks a run complete with only its duration, later adding distance and average HR. The app can already use the completed session and duration; it only uses the extra metrics after they become available.

### Change of priorities

The user raises running/VO2 max priority for a month and reduces gym priority. On the next manually requested plan, the app recommends a different balance while preserving previously accepted calendar items.

### Full week unavailable

The user blocks every calendar section. The planner returns **no workout suggestions**, explains that no time is available, and does not treat this as an error.

## 10. Initial MVP, later phases, and current implementation

**Important:** *MVP* denotes the **target first fully useful version**, not the features already present in this repository.

### Target MVP

- Interactive weekly calendar organized by morning/afternoon/evening, with spanning items.
- Manual training and non-training commitments, plus fully flexible block/day availability.
- Accepted/proposed/completed session states and preservation of accepted sessions.
- Quick completion and optional workout metrics (including running/cycling/hiking basics).
- Editable goals, priorities, flexible targets and preferred training windows.
- Manual 28-day suggestion generation, preview, per-item approval and understandable reasoning.
- Conservative scheduling rules using optional training history and optional basic recovery feedback.
- Local storage and basic automated tests for scheduling invariants.

### Later enhancements

- Customizable daypart boundaries and multi-day events.
- More detailed running progression, performance charts and fitness trends.
- Import/synchronization with sports watches and activity apps (subject to available APIs), and import/export of files.
- Detailed gym exercises, weights and progression.
- Richer recovery modeling, advanced optimization and optional AI-assisted recommendations.
- Additional user experience improvements such as mobile-friendly layouts and advanced calendar manipulation.

### Current implementation

The starter currently provides:

- A local **React/TypeScript** interface centered on an editable full-month calendar with Monday-to-Sunday rows, previous/next month navigation and a Today button. All dates remain displayed while loading and editing; narrow screens show the same dates as a day-by-day agenda. Workout cards expand to show details and actions. The fixed 28-day suggestion horizon is independent of the month view; navigate between months without losing unsaved suggestions. Each day has **Add training**; saved entries have **Edit** and **Delete**. Add/edit forms open in the adjacent tools panel (below the calendar on mobile) for the selected day with Save and Cancel controls. Edit the date to move an activity, or change its type, status, duration, HR zone, RPE and notes. Failed saves preserve the draft for correction or retry. Successful additions and non-date edits clear the suggestion preview; date changes instead ask whether to recalculate it.
- The **calm outdoor interface** uses warm neutral surfaces, forest-green controls, activity colour accents and separate labelled status badges. Suggestion generation and the expandable heart-rate reference live in the tools panel; **Plan training** opens and focuses the suggestion controls. Suggestions are confirmed directly on their calendar cards. No remote fonts or assets are required.
- **Mouse drag-and-drop** moves saved workouts and unsaved suggestions. Moving a confirmed or completed workout requires confirmation, including date changes through Edit; planned/skipped workouts and suggestions move without approval. After each successful move, a separate **Recalculate / Keep current suggestions** dialog asks whether to regenerate the preview. Cancelling a move or a failed save leaves both the workout and preview intact. Keeping suggestions preserves their positions; confirmation still rechecks the current calendar. Recalculation keeps manually moved draft dates while generating other suggestions around their workload. A recalculation failure leaves the completed move and preview intact for retry. Drafts remain unsaved until their **Confirm** button is pressed.
- Each unsaved suggestion has **Confirm** and **Remove** buttons visible even while collapsed. Removal requires no confirmation and leaves saved workouts untouched. After removal, the **Recalculate / Keep current suggestions** dialog offers to update the remaining preview. Recalculation excludes the removed workout type on its date, preserves other same-day activities and discards any removed draft move; a fresh **Generate suggestions** resets removals. An explicit draft move may still use a dismissed date. Proposal generation and acceptance carry per-workout exclusions in optional `excluded: [{ "day": "2026-10-06", "activity": "gym" }]`. The legacy `dismissed` date list remains available to API clients for whole-day exclusions.
- Drag the move handle, or click it to edit the date with the keyboard. Saved workouts may move to occupied or shaded adjacent-month dates. Suggestions may move to a date containing a different workout type, provided the date is available, on an allowed weekday for that activity,
inside the 28-day horizon and today or later. A second draft or active saved workout of the same type on that date is rejected. Moves preserve workout details and the displayed month. Dragging is disabled during loading, saving, editing and the rescheduling dialog. Touch dragging, dragging through month navigation and timed placement are not implemented.
- Proposal requests support optional `moves: [{ "original_day": "2026-10-06", "session": { "day": "2026-10-08", "activity": "gym", "status": "planned" } }]`. These are explicit user-positioned drafts: generation reserves their workout type at the destination and excludes that type at the original date. Other activities may use either date. They may override preferred weekdays and recovery spacing, as manual training entries can; newly generated workouts account for their workload. Send the same `moves` with acceptance. The server rechecks dates, availability, duplicate (date, activity) origins/destinations, planned status and intervening bookings, and accepts selected drafts atomically. A fresh **Generate suggestions** starts a new plan without retaining manual draft moves.
- A **Status** dropdown on every saved activity changes planned/confirmed/completed/skipped directly in the calendar. **Confirm** on a planned activity marks it committed but still upcoming. Status changes preserve other workout details and clear the suggestion preview only on success. Confirmed entries remain editable and count as booked training during suggestion generation. `PATCH /api/sessions/{session_id}/status` accepts only `{ "status": "confirmed" }` (or another supported status).
- A **Delete** button on each saved calendar activity. Deleting any saved activity (including accepted suggestions, completed and skipped workouts) requires confirmation. Deletion is permanent, refreshes the calendar and clears the suggestion preview; cancelling or a failed deletion keeps the activity. The API exposes `DELETE /api/sessions/{session_id}` (204 on success, 404 if missing).
- A **FastAPI** backend with validated session and planning endpoints, including `PUT /api/sessions/{session_id}` for replacing a saved activity while preserving its identifier (404 if missing).
- Suggestions always start **today** and cover a fixed **28 days**. The horizon selector has been removed. There is no start-date input. Generating a new plan shows the current month; month navigation remains independent of the planning window. Weekdays are placement preferences, with gym and easy-running alternatives when those dates are unavailable. The API retains the `week_start` field name for compatibility, but it now accepts any weekday as the inclusive start; confirmation and recalculation reuse the preview's original window and targets. The optional API `weeks` field defaults to 4 and rejects every other value.
- An **Unavailable** checkbox on each calendar day excludes it from suggestions. Marks persist across month navigation and training-target changes until the page is reloaded. Changing availability clears unsaved suggestions while preserving saved workouts; the separate unavailable-day list has been removed.
- Explicit **Generate suggestions** and calendar-only review: expand suggestion cards for details and use each card's **Confirm** button to save that suggestion as confirmed upcoming training. Other suggestions remain unsaved and available for review; failed confirmation preserves the draft for retry. There are no selection checkboxes or batch selection controls. **Dismiss all** clears the remaining unsaved suggestions without affecting saved workouts. Confirmation sends `confirm: true` to `POST /api/proposals/accept`, which revalidates the original draft and saves the confirmed status in the same transaction. API clients omitting `confirm` retain the existing planned-status acceptance behavior.
- SQLite storage using the current sessions schema, with **planned, confirmed, completed or skipped** status. Planned duration and main-set HR zones are separate from recorded results; all metrics are optional and blank values remain null.
- Activity-specific recorded results: running has distance (km), actual duration (min), average HR (bpm), calculated average pace (min/km), and active calories (kcal); cycling has distance, actual duration, average HR, elevation gain (m), and active calories; hiking has distance, actual duration, calculated average pace, elevation gain, and active calories. Gym has actual duration, active calories and multiline notes for weights and repetitions. Recorded RPE is optional for all activities. Average pace uses actual total duration divided by distance; it is not a separate editable value or moving pace. Zero or missing distance/time leaves pace unspecified.
- Actual duration in completed training forms accepts minutes (including decimals), `mm:ss`, or `hh:mm:ss` (for example, `42:30` or `1:05:30`). Colon-separated seconds and minutes after hours must be `00`-`59`; total duration is limited to 24 hours. Values are saved as fractional minutes and used to calculate pace.
- Event cards show upcoming targets or a compact summary of completed results. Expanded details group training targets, recorded results, and notes. Completed sessions with a recorded duration use it for duration-based recovery checks; otherwise those checks fall back to planned duration. Distance, average HR, pace, elevation and calories are stored/displayed but do not yet influence recommendations.
- Add/edit fields follow the selected status: **planned/confirmed** show targets and planning notes; **completed** shows activity-specific results, RPE and workout notes, with existing targets in a collapsed, read-only **Original plan** section; **skipped** shows only date, activity and status. Switching status preserves both saved values and unsaved drafts. Completing a workout does not require metrics. New activities saved directly as completed or skipped do not receive default planned targets; explicitly edited targets are retained. Changing activity while recording results does not overwrite the original targets.
- Deterministic **28-day, day-level rules** with gym/running targets, optional interval runs, weekend hikes and flexible long-run dates.
- Unit tests for the planner/storage and integration tests for API validation, proposal preservation and transactional acceptance.

**Not yet implemented:** the daypart calendar, exact times, spanning/multi-day items, persisted availability or non-training commitments, distinct proposal/accepted locks, detailed metrics, optional readiness inputs, goal-priority settings, intelligent recovery/load adaptation, personalized VO2 max progression, integrations, or performance dashboards. The current rule engine uses preferred weekdays with flexible long-run dates, excludes elapsed dates and does **not** account for time-block availability or automatically select the best rotation of gym muscle groups.


### Training targets, allowed weekdays and multiple daily events

The Suggestions panel offers **gym sessions per week (0-7)**, **runs per week
(0-7)**, and **interval runs (0-2, included in total runs)**. Defaults are three gym
sessions, two runs and no intervals. Lowering total runs automatically lowers the
interval selection if needed. **Gym weekdays** and **Running weekdays** select which
days can receive each activity. All seven days, including Saturday and Sunday,
are enabled by default. These are hard placement restrictions, while counts remain
soft targets. No selected weekdays means no suggestions for that activity; the
target count is retained so days can be enabled again later. All run categories
use the running weekdays, including interval and fallback long-run suggestions.

Targets, weekday choices and unavailable days are temporary page state and reset
on reload. Changing any setting clears the unsaved preview. Confirmations and
recalculations reuse the preview's original counts and weekday selections.

For this first version, "per week" means each of four consecutive seven-day periods
starting on the preview's start date, rather than partial Monday-Sunday weeks.
Targets are soft: allowed weekdays, unavailable dates, existing bookings and
recovery can leave them unmet. A blocked date takes precedence over a selected
weekday. Saved workouts on unselected weekdays are preserved and still count.
Planned, confirmed and completed workouts count; skipped workouts do not count or
occupy suggestion capacity. All running categories, including races, count toward
total runs; only interval runs satisfy the interval target. Other proposed runs
are easy or long easy runs. A single-run target uses an easy run.
Zero gym/running targets disable those suggestions, while the existing independent
Saturday hike suggestions remain.

The calendar, storage and manual add/edit workflow support multiple workouts per
date without exact times. Automatic generation permits at most two events per day,
pairing an easy/recovery run with ordinary gym training where recovery allows.
Gym placement tries empty days before pairing with a run, even when that means
using a less-preferred weekday. Consecutive gym days, including three in a row,
are allowed; there is no mandatory gym rest-day gap.
It does not automatically pair two runs, demanding activities, or training with
an explicit rest booking. Manual entries may still exceed these automatic limits.
No database migration is needed: multiple saved entries per date were already supported.

Proposal identity uses **(date, activity)**, so removing, moving or confirming a gym
draft does not affect a same-day running draft. Saved entries retain their database
identifiers. Acceptance still rejects duplicate workout proposals and revalidates
the whole selection atomically.

API generation and acceptance both accept the same optional input:
```json
{
  "week_start": "2026-10-18",
  "targets": { "gym": 3, "runs": 3, "intervals": 1 },
  "weekdays": { "gym": [0, 1, 2, 3, 4, 5, 6], "running": [0, 3, 5] },
  "blocked": [],
  "excluded": []
}
```

The optional API weekday settings use Monday = 0 through Sunday = 6.
Omitting either activity defaults it to all seven days; an empty list allows none.
Both generation and acceptance validate strict integer values from 0 to 6.
Explicit unsaved draft moves must also respect the activity's selected weekdays;
manual saved-workout entry remains under the user's control.
Saturday hike suggestions remain independent and may occupy a selected gym day;
their count and recurring weekdays are not configurable yet.

Named running modes, personalized progression, cross-period gym carryover,
gym workout rotation, persisted preferences and exact-time/daypart conflicts
remain planned.

## 11. Technical architecture

The project uses Python 3.11+, **FastAPI** for HTTP endpoints, **React 19 + TypeScript + Vite** for the browser interface, **SQLite** for local storage, and **pytest** for backend tests. Streamlit has been removed.

```text
src/training_planner/
  domain/models.py        # Framework-independent workout types and statuses
  planner/rules.py        # Pure target/recovery rules over a fixed 28-day horizon
  application/services.py # Session CRUD, previews and transactional acceptance
  storage/db.py           # SQLite connection and session repository
  api/app.py              # FastAPI app factory and /api endpoints
  api/schemas.py          # Validated HTTP request/response contracts
frontend/
  src/api/                # Typed HTTP client and transport types
  src/components/         # Reusable UI components
  src/App.tsx             # Monthly calendar and proposal workflows
  vite.config.ts          # Local API proxy for development and build preview
  package.json            # Frontend dependencies and commands
  package-lock.json       # Reproducible frontend dependency resolution
tests/
  unit/                   # Planner and storage checks
  integration/            # API and application workflow checks
data/                     # Existing local database (excluded from version control)
pyproject.toml            # Python dependencies, src packaging and tooling
README.md                 # Product specification and setup
```

The interface calls application services through the API. Services coordinate the domain, planner and repository; the domain and planner do not import FastAPI, React or SQLite. HTTP validation lives at the API boundary. Database connections are short-lived, and services own write transactions.

The prototype creates the current schema at `data/training.db`. Older database schemas and retired activity categories are not supported; discard development data when changing the schema. `TRAINING_PLANNER_DB` can override the location; use an absolute path when launching outside the project root.

Likely future domain concepts include `CalendarItem`, `TimeBlock`, `Availability`, `GoalPriority`, `TrainingPreference`, `WorkoutMetrics`, `ReadinessEntry`, and `PlanningProposal`, with stable identifiers, optional metrics and explicit ownership/status distinctions. Those types are **proposals**, not current modules or database tables.

For a future planner, distinguish **hard constraints** (unavailable blocks, accepted commitments, explicit locks) from **soft preferences** (preferred times, frequency targets, gym split order, ideal progression). Tests should cover fully blocked weeks, spanning events, absent metrics, accepted-session preservation, and rejection of all proposals.

## 12. Installation and development

Prerequisites: Python 3.11+ (uv uses the Python 3.13 development pin) and Node.js 22.22.2+ (22.x), 24.15.0+ (24.x), or 26+ with npm. For the Makefile workflow, also install GNU Make and uv and ensure all tools are on PATH. Run from the project root:

```bash
make install  # Install both backend and frontend dependencies
make run      # Start API on port 8000 and frontend on port 5173
```

Use `make dev` instead of `make install` to include Python test, lint, and typing tools and install the commit hooks. You can also run `make run-api` and `make run-frontend` in separate terminals. No virtual environment activation is needed for these targets. The Makefile supports Windows and Unix and automatically includes the optional `.tools/node` installation on PATH. On Windows, that installation can contain `node.exe` directly; on Unix it uses `.tools/node/bin`.

To install and run manually without Make or uv:

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
python -m pip install -e '.[dev]'
python -m uvicorn training_planner.api.app:app --reload --host 127.0.0.1 --port 8000
```

In a second terminal, start from the **project root** and run:

```bash
# Make this checkout's local Node/npm installation available in this terminal.
export PATH="$PWD/.tools/node/bin:$PATH"
cd frontend
npm ci
npm run dev
```

The optional local Node distribution in `.tools/node` is excluded from version control. On a fresh checkout, install Node.js 22.22.2+ (22.x), 24.15.0+ (24.x), or 26+ with npm first; the PATH line above is unnecessary if your normal Node installation is already available. The `export` examples use a Unix shell; on Windows with Node/npm on PATH, run `cd frontend`, `npm ci`, and `npm run dev`. Activating the Python virtual environment does not add Node/npm to PATH. PATH changes apply only to the terminal where the export command runs, so repeat it in each new frontend terminal.

If you are already inside `frontend/` and see `npm: command not found`, run:

```bash
export PATH="$PWD/../.tools/node/bin:$PATH"
node --version
npm --version
npm ci
npm run dev
```

Open **http://127.0.0.1:5173**. Vite forwards `/api` requests to the local backend on port 8000, so no cross-origin configuration is required. The API documentation is available at **http://127.0.0.1:8000/docs**. Both processes run locally; the interface uses no remote fonts or services at runtime.

Backend checks, from the project root with the virtual environment activated:

```bash
python -m pytest -q
ruff check src tests
ruff format --check src tests
mypy src tests
```

Every commit must pass Ruff lint, Ruff formatting (89-character line limit), and
mypy across `src` and `tests`. Install hooks once per checkout with
`uv sync --extra dev` and `uv run --extra dev pre-commit install` (also done by
`make backend-dev` / `make dev`). The hooks check the staged snapshot at commit time
and block commits on failures. They require uv on PATH, including in GUI Git clients.
Run `make check` for all three checks, or `uv run --extra dev pre-commit run --all-files`.
After a manual pip installation, run `pre-commit install`; uv is still required by
the hook commands. Do not bypass failing hooks.

Frontend checks and build, from `frontend/`:

```bash
npm test
npm run typecheck
npm run build
npm run preview
```

The preview runs on port 4173 and also requires the backend on port 8000. It is a local build preview, not a production deployment configuration. After updating frontend dependencies with `npm install`, commit the updated `package-lock.json`.

The SQLite database is created locally at `data/training.db` on the first session/planning operation. Importing the API or checking `/api/health` does not create a database. The application is currently a single-user local prototype. Backup/sync, migrations, data import and multi-user support are not yet provided.

## Windows application and installer builds

Icon designs and editable sources are in [assets/icons](assets/icons/README.md).
The default Summit Calendar icon is embedded in the app and installer executables,
used by app shortcuts and the browser tab, and displayed inside the installation wizard.
Rebuild the installer below to include these assets.

Windows packaging is separate from the two-server development workflow above.
The packaged application serves the built React interface and API together on
`http://127.0.0.1:8765`, and opens your default browser after startup. A console
window remains open: press **Ctrl+C** there to stop the app. Closing the browser
does not stop the server. A second launch reports an occupied port; use the existing
window or stop it before relaunching. Advanced users can pass `--no-browser` or
`--port 8766` to the executable.

Build on Windows with uv, the Node/npm versions listed above, and optionally GNU
Make. Installer builds additionally require **Inno Setup 6**. Install it from
[the official download page](https://jrsoftware.org/isdl.php); the script searches
its usual installation directories, `.tools/inno`, and PATH. For a custom installation,
set the `ISCC` environment variable to the full path of `ISCC.exe`.

```powershell
make package-windows    # Runnable folder: dist/TrainingPlanner/
make installer-windows  # Setup executable: dist/TrainingPlanner-Setup-0.1.0.exe
make release-windows    # Backend checks/tests and frontend tests/checks, then installer
```

Without Make, run the same workflow directly from PowerShell:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/build-windows.ps1 -Target installer
# Use -Target package or -Target release for the other workflows.
```

Builds use `uv sync --locked`, the pinned PyInstaller build extra, and `npm ci`.
Packaging uses a separate `.venv-build` environment containing runtime and build
dependencies, keeping development tools out of the distributed application.
Every package build smoke-tests a temporary copy of the actual executable: frontend
assets, API health and writes, executable-relative storage, and repeated initialization.
The installer version comes from `pyproject.toml`. Missing tools or failing commands
stop the build. Generated files live in ignored `build/` and `dist/` directories;
builds do not install the app or launch a browser. Packaging refuses to overwrite
`dist/TrainingPlanner` if it contains a `data/` directory: move an application folder
you have used before rebuilding. Always distribute the entire packaged folder or
the setup executable, not just the inner `TrainingPlanner.exe`.

`make clean` removes generated `build/` and `dist/` output, `frontend/dist`,
frontend build caches, and Python/test/lint caches. It preserves source files,
Git metadata, virtual environments, installed dependencies and `.tools`.
Data directories and SQLite files/sidecars are protected: output subfolders
containing them are kept intact, including used application bundles and installer
smoke-test results. Sibling installer executables and build intermediates are still
removed. Linked output is preserved rather than traversed. The command reports
what it removes or preserves; generated installers must be rebuilt afterward.

The installer asks for a destination, defaulting to
`%LOCALAPPDATA%\Programs\TrainingPlanner`. Choose a local directory your account
can write to during ordinary use; `Program Files` is unsuitable for this storage
layout. Installation runs without requesting administrator privileges. Start menu
and desktop shortcuts are separate **unchecked** options on every installation.
Launching the app after installation is also optional and unchecked.

```text
TrainingPlanner/
  TrainingPlanner.exe
  _internal/            # Python runtime, dependencies and built interface
  data/
    training.db         # Created by application initialization, never shipped
  unins000.exe          # Added by the installer
```

Setup invokes `TrainingPlanner.exe --init-db` and reports initialization failures.
The app also initializes missing tables on launch. Its database always lives at
`data/training.db` relative to the executable, independent of shortcuts, working
directory, or a development `TRAINING_PLANNER_DB` override. No existing checkout
database is copied, migrated or backed up. Reinstalling preserves existing records;
uninstalling removes installed application files while leaving application-created
data in place. Close the app before installing an update. A portable packaged folder
can be moved while the app is closed. Keep installed copies at their selected location
so Windows' registered uninstaller and any chosen shortcuts continue to work.

Database migrations, automatic backups and automatic updates remain unimplemented.
Older incompatible prototype schemas are still unsupported; use a fresh database
for this test-data stage. Before retaining real history across schema changes,
implement migrations and a backup policy. Release builds run automated source checks;
test the resulting installer on a clean Windows machine before distribution.

An optional installer smoke test verifies installation to a path with spaces, absent
default shortcuts, initialization, reinstallation with saved data, and uninstall data
preservation. It briefly registers a per-user installation, uninstalls it afterward,
and leaves logs/test data under `build/`. It refuses to affect an existing installation
or existing Training Planner shortcuts. It is separate from build commands, which
never install the application:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tests/windows_installer_smoke.ps1
```

## 13. Open implementation questions

These can be settled during development without blocking the product vision:

1. Exact default time boundaries for morning, afternoon and evening, and whether overlapping items within a block are supported when exact times do not conflict.
2. The interaction design and React components for the logical daypart grid, spanning items and accessible drag/drop alternatives.
3. How to represent workouts spanning days, and how time-zone changes during travel should be handled.
4. The specific default target frequencies and progression caps for different experience levels.
5. How to weight endurance load, gym fatigue, subjective readiness and incomplete measurements in explainable rules.
6. The data migration and export strategy as the initial SQLite schema evolves.

Changes to this README should preserve the distinction between **intended requirements**, **MVP scope**, and **already implemented behavior**.


## Heart-rate and duration based running

Running is planned by total minutes and a main-set heart-rate zone, rather than distance.
The session form offers recovery (Z1-2, 20 min), easy (Z2, 30 min), long easy
(Z2, 45 min), tempo/threshold (Z3-4, 40 min), VO2 max intervals (Z4-5 work bouts,
45 min), hard endurance (Z3-4, 60 min), and race/maximum-effort test (no fixed zone
or duration). These are editable examples, not personalized prescriptions.

Zone reference: a five-zone maximum-HR model, Z1 50-60%, Z2 60-70%, Z3 70-80%,
Z4 80-90%, Z5 90-100%. Zone numbers differ between HRmax, heart-rate reserve and
threshold-based systems; these percentages are not measured physiological thresholds.
The heart-rate section includes an optional calculator: enter a whole-number maximum HR
(50-300 bpm) to see all five bpm ranges instantly. This input is held only in the page
and is cleared on reload. Lower boundaries are rounded up, upper boundaries exclude the
next zone, and Z5 includes maximum HR, so integer ranges do not overlap. For example,
180 bpm gives Z2 108-125 bpm. These are percentage-based estimates; use individually
calibrated zones when available and conversational effort as the easy-running cross-check.
HR data remains optional. Run calculator checks with `npm --prefix frontend test`.

Interval example: 10 min easy warm-up, 4 x 4 min hard with 3 x 3 min easy between
repetitions, then 10 min easy cool-down = 45 min total. The Z4-5 target applies
only to work bouts, building toward approximately 85-95% HRmax. Heart rate lags
changes in effort; do not sprint to force the target at the start of a repetition.

The scheduler prefers Tuesday/Wednesday/Friday gym dates and searches alternative dates
within each seven-day target period. Easy and long-run proposals use Z2. Interval proposals
use Z4-5 main-set targets only when explicitly requested through the interval count.
Saved neighboring-week sessions and newly proposed outings influence recovery checks.
Suggestions cover the next 28 days. Mark **Unavailable** directly on calendar days to exclude them. Browse months to mark dates across the horizon; availability marks survive month navigation and target changes. Changing availability clears unsaved suggestions without changing saved workouts. These choices remain local to the current page and reset on reload.
Hard run categories, Z4-5 targets, RPE >=7, and long endurance outings (>=90 min)
count as demanding, including easy and recovery runs. Skipped sessions do not count.
Two calendar days is the default buffer for demanding work; races and demanding outings >=120 min use three.
These are conservative configurable-in-code heuristics, not measured recovery times.
Recovery checks protect endurance in either insertion order, including a saved short long-run
entry next to a proposed hike. Ordinary gym entries have unknown load; explicit demanding
gym metrics still count. Monday easy suggestions use a fixed 20-minute starting duration so accepting other
suggestions does not rewrite their contents. Non-demanding Monday easy runs of at most 20 minutes are a recovery exception,
whether saved or proposed, so accepting them does not change compatible suggestions. Hikes stay on Saturdays. Long runs prefer Sunday, then search up
to six later days within the selected horizon, ahead of gym/easy-run slots when the total running target is at least two.
Saved and proposed long runs stay at least seven days apart to avoid piling up deferred runs.
If no eligible date exists, the suggestion is omitted. Only today and later dates are proposed.
Blocked days cannot receive training but still count toward recovery in calendar days.
Acceptance rechecks the whole horizon and neighboring saved work in one transaction.
Accepted sessions are preserved. Generic gym entries
cannot identify heavy leg training yet, so that conflict still needs manual review.

Sources consulted:
- [Polar endurance zones](https://www.polar.com/us-en/guide/endurance-training)
- [Polar higher-intensity zones](https://www.polar.com/us-en/guide/anaerobic-training)
- [NTNU CERG interval guidance](https://www.ntnu.edu/cerg/advice)
- [Polar on heart-rate response lag](https://www.polar.com/blog/power-vs-running-is-heart-rate-training-old-news/)

The category mappings, example durations and calendar buffers are app design choices
informed by this guidance; they are not universal training prescriptions.
