/**
 * Background-activity logic — pure parsers + derive helpers for the "ambient
 * activity" feature (notifications, long-running processes, background runs).
 * No state container here: the store owns the arrays; these functions parse
 * loose wire payloads (everything off the gateway is `unknown`) and compute
 * derived values over immutable arrays. Mirrors the defensive loose-read style
 * of `logic/slash.ts` (`readStr`) and the snake_case→camel mapping the wire
 * needs.
 *
 * Wire shapes (see boundary/schema/GatewayEvent.ts ~134):
 *   notification.show  payload {text, level, kind, ttl_ms, key, id}  (loose Record)
 *   notification.clear payload {key}
 *   agents.list result {processes:[{session_id, command, status, uptime_seconds}]}
 */

export interface ActivityNotification {
  id: string
  key?: string
  text: string
  level: 'info' | 'warn' | 'error'
  kind: string
  ttlMs?: number
}

export interface BackgroundProcess {
  sessionId: string
  command: string
  status: string
  uptimeSeconds: number
}

export interface BackgroundRun {
  id: string
  label: string
  status: 'running' | 'complete' | 'failed' | 'cancelled'
  startedAt?: number
  summary?: string
}

/** Loose-read a string field off an `unknown` object (slash.ts `readStr` style). */
function readStr(value: unknown, key: string): string | undefined {
  if (!value || typeof value !== 'object') return undefined
  const v = (value as { [k: string]: unknown })[key]
  return typeof v === 'string' ? v : undefined
}

/** Loose-read a finite number off an `unknown` object. */
function readNum(value: unknown, key: string): number | undefined {
  if (!value || typeof value !== 'object') return undefined
  const v = (value as { [k: string]: unknown })[key]
  return typeof v === 'number' && Number.isFinite(v) ? v : undefined
}

/** Coerce any wire `level` to the closed union; anything that isn't a known
 *  level (absent, garbage, wrong-typed) falls back to 'info'. */
function coerceLevel(value: unknown): ActivityNotification['level'] {
  return value === 'warn' || value === 'error' ? value : 'info'
}

/**
 * Parse a `notification.show` payload (unknown) → ActivityNotification, or null
 * when there's no usable text (text is the load-bearing field — without it the
 * card has nothing to show). Maps snake_case `ttl_ms` → `ttlMs`, coerces a
 * garbage/missing `level` to 'info', and defaults `kind` to ''.
 *
 * id resolution (dedupe key): prefer the wire `id`, then fall back to `key`. If
 * BOTH are missing we synthesize `id = `n:${text}`` rather than minting a random
 * id — a random id would make every re-emit of the same text a NEW card, so a
 * text-derived stable id keeps dedupe (upsertNotification) working for
 * gateways that don't send ids. The original `key` (if any) is preserved
 * separately so notification.clear by key still targets the right rows.
 */
export function parseNotification(payload: unknown): ActivityNotification | null {
  const text = readStr(payload, 'text')
  if (!text) return null
  const key = readStr(payload, 'key')
  const id = readStr(payload, 'id') ?? key ?? `n:${text}`
  const out: ActivityNotification = {
    id,
    kind: readStr(payload, 'kind') ?? '',
    level: coerceLevel((payload as { level?: unknown } | null | undefined)?.level),
    text
  }
  if (key !== undefined) out.key = key
  const ttlMs = readNum(payload, 'ttl_ms')
  if (ttlMs !== undefined) out.ttlMs = ttlMs
  return out
}

/** Dedupe-by-id upsert: replace an existing item with the same id, else append.
 *  Returns a NEW array (never mutates the input). */
export function upsertNotification(
  list: readonly ActivityNotification[],
  n: ActivityNotification
): ActivityNotification[] {
  const idx = list.findIndex(item => item.id === n.id)
  if (idx === -1) return [...list, n]
  const next = list.slice()
  next[idx] = n
  return next
}

/** Drop every notification whose `key` matches (notification.clear). Returns a
 *  NEW array. Notifications without a key are never cleared this way. */
export function clearNotificationsByKey(list: readonly ActivityNotification[], key: string): ActivityNotification[] {
  return list.filter(n => n.key !== key)
}

/** Parse an `agents.list` result ({processes:[...]}) → BackgroundProcess[],
 *  skipping malformed rows (a row missing session_id/command is dropped, not
 *  defaulted). snake_case `session_id`/`uptime_seconds` → camelCase; a missing
 *  uptime defaults to 0, a missing status to ''. */
export function parseProcessList(result: unknown): BackgroundProcess[] {
  if (!result || typeof result !== 'object') return []
  const processes = (result as { processes?: unknown }).processes
  if (!Array.isArray(processes)) return []
  const out: BackgroundProcess[] = []
  for (const row of processes) {
    const sessionId = readStr(row, 'session_id')
    const command = readStr(row, 'command')
    if (!sessionId || !command) continue
    out.push({
      command,
      sessionId,
      status: readStr(row, 'status') ?? '',
      uptimeSeconds: readNum(row, 'uptime_seconds') ?? 0
    })
  }
  return out
}

/** Terminal (no-longer-running) process statuses. A process whose status is
 *  NOT one of these is treated as running — leniently, because the gateway's
 *  status vocabulary is open-ended and we'd rather over-count the ambient badge
 *  than silently hide a still-live process under an unfamiliar status string.
 *  Matched case-insensitively after trimming. */
const DONE_STATUSES = new Set(['exited', 'failed', 'complete', 'done', 'killed'])

function procIsRunning(status: string): boolean {
  return !DONE_STATUSES.has(status.trim().toLowerCase())
}

/** Count of "currently running" things for the ambient badge: runs whose
 *  status is 'running', plus processes whose status is running-ish (anything
 *  that isn't a terminal status — see DONE_STATUSES). */
export function runningCount(runs: readonly BackgroundRun[], procs: readonly BackgroundProcess[]): number {
  const runningRuns = runs.filter(r => r.status === 'running').length
  const runningProcs = procs.filter(p => procIsRunning(p.status)).length
  return runningRuns + runningProcs
}
