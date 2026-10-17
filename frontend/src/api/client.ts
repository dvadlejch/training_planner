import type { PlanningRequest, Session, SessionInput } from "./types";

/** Send JSON through the same-origin API proxy and expose readable failures.
 *
 * Parameters
 * ----------
 * path : string
 *     Endpoint relative to /api.
 * body : unknown, optional
 *     JSON payload; omission selects GET rather than POST.
 * signal : AbortSignal, optional
 *     Cancellation signal for a superseded calendar query.
 * method : string, optional
 *     Explicit HTTP method; otherwise inferred from the body.
 *
 * Returns
 * -------
 * Promise<T>
 *     Decoded JSON response.
 *
 * Raises
 * ------
 * Error
 *     If the server rejects the request, networking fails, or JSON is invalid.
 */
async function request<T>(path: string, body?: unknown, signal?: AbortSignal, method?: string): Promise<T> {
  const response = await fetch(`/api${path}`, {
    method: method ?? (body === undefined ? "GET" : "POST"),
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal,
  });
  if (!response.ok) {
    const error: { detail?: unknown } = await response.json().catch(() => ({}));
    throw new Error(typeof error.detail === "string"
      ? error.detail : `Request failed (${response.status}). Check the supplied values.`);
  }
  // Successful deletion has no JSON body.
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

/** Read saved workouts in an inclusive date range.
 *
 * Parameters
 * ----------
 * start : string
 *     First date in YYYY-MM-DD format.
 * end : string
 *     Last date in YYYY-MM-DD format.
 * signal : AbortSignal, optional
 *     Cancellation signal for the request.
 *
 * Returns
 * -------
 * Promise<Session[]>
 *     Saved workouts ordered by date and identifier.
 *
 * Raises
 * ------
 * Error
 *     If the request fails, is cancelled, or the response is invalid JSON.
 */
export function listSessions(start: string, end: string, signal?: AbortSignal): Promise<Session[]> {
  const query = new URLSearchParams({ start, end });
  return request(`/sessions?${query}`, undefined, signal);
}

/** Persist a manually entered workout.
 *
 * Parameters
 * ----------
 * session : SessionInput
 *     Workout details; unknown metrics are null.
 *
 * Returns
 * -------
 * Promise<Session>
 *     Committed workout with its database identifier.
 *
 * Raises
 * ------
 * Error
 *     If validation, networking, persistence, or JSON decoding fails.
 */
export function saveSession(session: SessionInput): Promise<Session> {
  return request("/sessions", session);
}

/** Replace a saved workout while retaining its database identifier. */
export function updateSession(id: number, session: SessionInput): Promise<Session> {
  return request(`/sessions/${id}`, session, undefined, "PUT");
}

/** Change only status so quick actions cannot overwrite other workout details. */
export function updateSessionStatus(id: number, status: SessionInput["status"]): Promise<Session> {
  return request(`/sessions/${id}/status`, { status }, undefined, "PATCH");
}

/** Permanently delete a saved workout; reject on server or network failure. */
export function deleteSession(id: number): Promise<void> {
  return request(`/sessions/${id}`, undefined, undefined, "DELETE");
}

/** Generate a preview without storing the proposed workouts.
 *
 * Parameters
 * ----------
 * input : PlanningRequest
 *     Monday week start and temporary unavailable dates.
 *
 * Returns
 * -------
 * Promise<Session[]>
 *     Unsaved suggestions with null identifiers.
 *
 * Raises
 * ------
 * Error
 *     If planning input, networking, or JSON decoding fails.
 */
export function generateProposals(input: PlanningRequest): Promise<Session[]> {
  return request("/proposals", input);
}

/** Atomically accept selected suggestions after server-side revalidation.
 *
 * Parameters
 * ----------
 * input : PlanningRequest
 *     Original planning inputs used for the preview.
 * proposals : Session[]
 *     Unmodified preview items selected for acceptance.
 *
 * Returns
 * -------
 * Promise<Session[]>
 *     Committed workouts with database identifiers.
 *
 * Raises
 * ------
 * Error
 *     If proposals conflict or validation, networking, or JSON decoding fails.
 */
export function acceptProposals(input: PlanningRequest, proposals: Session[]): Promise<Session[]> {
  // IDs identify persisted sessions, so omit the null preview IDs from input.
  return request("/proposals/accept", {
    ...input, proposals: proposals.map(({ id: _id, ...session }) => session),
  });
}
