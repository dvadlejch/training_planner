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

- The user chooses a horizon, initially **1–4 weeks**, and presses **Generate suggestions / Replan**.
- The system considers the remaining part of the current week and, if requested, later weeks.
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

The user opens a mostly empty calendar, optionally sets training preferences, marks busy sections, chooses a one-week horizon and presses **Generate suggestions**. The engine generates cautious proposals using defaults and available calendar space. VO2 max, heart rate, past workouts and readiness are **not** prerequisites.

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
- Manual 1–4-week suggestion generation, preview, per-item approval and understandable reasoning.
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

- A local **React/TypeScript** interface centered on an editable full-month calendar with Monday-to-Sunday rows, previous/next month navigation and a Today button. All dates remain displayed while loading and editing; narrow screens show the same dates as a day-by-day agenda. Workout cards expand to show details and actions. The 1-4-week suggestion horizon is independent of the month view; navigate between months to review suggestions without losing selections. Each day has **Add training**; saved entries have **Edit** and **Delete**. Add/edit forms open in the adjacent tools panel (below the calendar on mobile) for the selected day with Save and Cancel controls. Edit the date to move an activity, or change its type, status, duration, HR zone, RPE and notes. Failed saves preserve the draft for correction or retry. Successful additions and non-date edits clear the suggestion preview; date changes instead ask whether to recalculate it.
- The **calm outdoor interface** uses warm neutral surfaces, forest-green controls, activity colour accents and separate labelled status badges. Suggestions and the expandable heart-rate reference live in the tools panel; **Plan training** opens and focuses the suggestion controls. Proposal selection and acceptance remain next to the calendar. No remote fonts or assets are required.
- **Mouse drag-and-drop** moves saved workouts and unsaved suggestions. Moving a confirmed or completed workout requires confirmation, including date changes through Edit; planned/skipped workouts and suggestions move without approval. After each successful move, a separate **Recalculate / Keep current suggestions** dialog asks whether to regenerate the preview. Cancelling a move or a failed save leaves both the workout and preview intact. Keeping suggestions preserves their positions and selections; acceptance still rechecks the current calendar. Recalculation resets selection and keeps manually moved draft dates while generating other suggestions around their workload. A recalculation failure leaves the completed move and preview intact for retry. Drafts remain unsaved until **Accept selected**.
- Each unsaved suggestion has a **Remove** button visible even while collapsed. Removal requires no confirmation, removes it from the acceptance selection and leaves saved workouts untouched. After removal, the **Recalculate / Keep current suggestions** dialog offers to update the remaining preview. Recalculation keeps dismissed dates free and discards any removed draft move; a fresh **Generate suggestions** resets removals. An explicit draft move may still use a dismissed date. Proposal generation and acceptance carry these temporary date exclusions in optional `dismissed: ["2026-10-06"]`.
- Drag the move handle, or click it to edit the date with the keyboard. Saved workouts may move to occupied or shaded adjacent-month dates. Suggestions require a free, available date inside their planning horizon, today or later. Moves preserve workout details and the displayed month. Dragging is disabled during loading, saving, editing and the rescheduling dialog. Touch dragging, dragging through month navigation and timed placement are not implemented.
- Proposal requests support optional `moves: [{ "original_day": "2026-10-06", "session": { "day": "2026-10-08", "activity": "gym", "status": "planned" } }]`. These are explicit user-positioned drafts: generation reserves their destinations and does not refill their original dates. They may override preferred weekdays and recovery spacing, as manual training entries can; newly generated workouts account for their workload. Send the same `moves` with acceptance. The server rechecks dates, availability, duplicate origins/destinations, planned status and intervening bookings, and accepts selected drafts atomically. A fresh **Generate suggestions** starts a new plan without retaining manual draft moves.
- A **Status** dropdown on every saved activity changes planned/confirmed/completed/skipped directly in the calendar. **Confirm** on a planned activity marks it committed but still upcoming. Status changes preserve other workout details and clear the suggestion preview only on success. Confirmed entries remain editable and count as booked training during suggestion generation. `PATCH /api/sessions/{session_id}/status` accepts only `{ "status": "confirmed" }` (or another supported status).
- A **Delete** button on each saved calendar activity. Deleting any saved activity (including accepted suggestions, completed and skipped workouts) requires confirmation. Deletion is permanent, refreshes the calendar and clears the suggestion preview; cancelling or a failed deletion keeps the activity. The API exposes `DELETE /api/sessions/{session_id}` (204 on success, 404 if missing).
- A **FastAPI** backend with validated session and planning endpoints, including `PUT /api/sessions/{session_id}` for replacing a saved activity while preserving its identifier (404 if missing).
- SQLite storage using the current sessions schema, with **planned, confirmed, completed or skipped** status. Planned duration and main-set HR zones are separate from recorded results; all metrics are optional and blank values remain null.
- Activity-specific recorded results: running has distance (km), actual duration (min), average HR (bpm), calculated average pace (min/km), and active calories (kcal); cycling has distance, actual duration, average HR, elevation gain (m), and active calories; hiking has distance, actual duration, calculated average pace, elevation gain, and active calories. Gym has actual duration, active calories and multiline notes for weights and repetitions. Recorded RPE is optional for all activities. Average pace uses actual total duration divided by distance; it is not a separate editable value or moving pace. Zero or missing distance/time leaves pace unspecified.
- Event cards show upcoming targets or a compact summary of completed results. Expanded details group training targets, recorded results, and notes. Completed sessions with a recorded duration use it for duration-based recovery checks; otherwise those checks fall back to planned duration. Distance, average HR, pace, elevation and calories are stored/displayed but do not yet influence recommendations.
- Add/edit fields follow the selected status: **planned/confirmed** show targets and planning notes; **completed** shows activity-specific results, RPE and workout notes, with existing targets in a collapsed, read-only **Original plan** section; **skipped** shows only date, activity and status. Switching status preserves both saved values and unsaved drafts. Completing a workout does not require metrics. New activities saved directly as completed or skipped do not receive default planned targets; explicitly edited targets are retained. Changing activity while recording results does not overwrite the original targets.
- An **ephemeral, whole-day** unavailability selector when generating suggestions (not persisted).
- Explicit **Generate suggestions** and **Accept selected** actions with per-item selection. Generating a preview does not save proposed sessions; acceptance rechecks the calendar and commits the entire batch in one transaction.
- Deterministic **1-4-week, day-level rules** for gym, easy runs, weekend hikes and flexible long-run dates.
- Unit tests for the planner/storage and integration tests for API validation, proposal preservation and transactional acceptance.

**Not yet implemented:** the daypart calendar, exact times, spanning/multi-day items, persisted availability or non-training commitments, distinct proposal/accepted locks, detailed metrics, optional readiness inputs, goal-priority settings, intelligent recovery/load adaptation, personalized VO2 max progression, integrations, or performance dashboards. The current rule engine uses preferred weekdays with flexible long-run dates, excludes elapsed dates and does **not** account for time-block availability or automatically select the best rotation of gym muscle groups.

## 11. Technical architecture

The project uses Python 3.11+, **FastAPI** for HTTP endpoints, **React 19 + TypeScript + Vite** for the browser interface, **SQLite** for local storage, and **pytest** for backend tests. Streamlit has been removed.

```text
src/training_planner/
  domain/models.py        # Framework-independent workout types and statuses
  planner/rules.py        # Pure, deterministic rules over a 1-4-week horizon
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

The starter scheduler still uses fixed gym weekdays and does not automatically prescribe
hard running without training history. It now assigns Z2 to running proposals and considers
saved neighboring-week sessions and newly proposed outings when checking recovery.
Choose a 1-4-week horizon; proposals and unavailable-day controls cover the whole horizon.
Hard run categories, Z4-5 targets, RPE >=7, and long endurance outings (>=90 min)
count as demanding, including easy and recovery runs. Skipped sessions do not count.
Two calendar days is the default buffer for demanding work; races and demanding outings >=120 min use three.
These are conservative configurable-in-code heuristics, not measured recovery times.
Recovery checks protect endurance in either insertion order, including a saved short long-run
entry next to a proposed hike. Ordinary gym entries have unknown load; explicit demanding
gym metrics still count. Monday easy runs shorten to 20 minutes around nearby demanding
work. Non-demanding Monday easy runs of at most 20 minutes are a recovery exception,
whether saved or proposed, so accepting them does not change compatible suggestions. Hikes stay on Saturdays. Long runs prefer Sunday, then search up
to six later days within the selected horizon, ahead of default gym/easy-run slots.
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
