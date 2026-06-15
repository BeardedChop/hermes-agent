/**
 * Memory-monitor LOGIC (pure, no node:v8/process/file imports — testable).
 *
 * Ports the high-value SMART part of Ink's memory monitor
 * (`ui-tui/src/lib/memoryMonitor.ts`): the #34095 silent-death EARLY-WARNING.
 * It deliberately does NOT port Ink's auto heap-snapshot capture — the OpenTUI
 * engine's always-on `memlog` NDJSON trace (boundary/memlog.ts) is the
 * diagnosis path, and the rss-vs-heap divergence it records is the better
 * diagnostic for the native-RSS leak class (#15141) that a V8 heap snapshot
 * captures poorly anyway. So we skip the #41948 disk-fill bug class entirely.
 *
 * The early-warning regime is BELOW the OOM ceiling: Node can OOM from a render-
 * tree / store blowup at a few hundred MB, well under any "critical" exit
 * watermark, so a plain level machine never sees it and the death looks silent
 * (#34095 showed up only as a bare gateway `stdin EOF`). We fire ONCE when heap
 * both crosses a modest absolute floor AND is climbing steeply (≥150MB between
 * ticks) — the render-tree-blowup signature — and re-arm only after heap falls
 * back below the floor. The boundary turns the fire into a visible transcript
 * system line so the user gets a heads-up before the process dies.
 */

const MB = 1024 ** 2

/** Heap floor below which we never warn (a small heap climbing is normal). */
export const WARN_FLOOR_BYTES = 600 * MB
/** Per-tick growth that, combined with crossing the floor, signals a blowup. */
export const WARN_GROWTH_STEP_BYTES = 150 * MB

/** Mutable arm/disarm state for the early-warning detector. */
export interface WarnState {
  /** Previous heapUsed sample; `-1` until the first sample is seen. */
  lastHeap: number
  /** Whether we've already fired since the last re-arm (one-shot until reset). */
  warned: boolean
}

/** A fresh, un-seeded warn state (lastHeap < 0 ⇒ first sample can't "grow"). */
export function createWarnState(): WarnState {
  return { lastHeap: -1, warned: false }
}

export interface WarnEvaluation {
  /** True exactly on the tick the warning should fire (one-shot). */
  readonly fire: boolean
  /** The growth since the previous sample (bytes; 0 on the first sample). */
  readonly growthBytes: number
}

/**
 * Advance the early-warning state machine by one sample. MUTATES `state`
 * (lastHeap + warned) and returns whether to fire this tick.
 *
 * Fires once when, while below any OOM ceiling: heap ≥ floor AND grew
 * ≥ step since the previous sample AND we haven't already fired. Re-arms
 * (warned ← false) once heap drops back below the floor. The first
 * (un-seeded) sample only seeds lastHeap and never fires.
 */
export function evaluateWarn(
  state: WarnState,
  heapUsed: number,
  floorBytes: number = WARN_FLOOR_BYTES,
  stepBytes: number = WARN_GROWTH_STEP_BYTES
): WarnEvaluation {
  const seeded = state.lastHeap >= 0
  const growthBytes = seeded ? heapUsed - state.lastHeap : 0
  let fire = false

  if (seeded) {
    if (!state.warned && heapUsed >= floorBytes && growthBytes >= stepBytes) {
      state.warned = true
      fire = true
    } else if (heapUsed < floorBytes) {
      state.warned = false
    }
  }

  state.lastHeap = heapUsed
  return { fire, growthBytes }
}

/** Render the user-facing early-warning line (KB system line, no disk cost). */
export function warnLine(heapUsed: number, rss: number, growthBytes: number): string {
  const mb = (n: number) => Math.round(n / MB)
  return (
    `⚠ memory climbing fast — heap ${mb(heapUsed)}MB (+${mb(growthBytes)}MB), rss ${mb(rss)}MB. ` +
    `If the TUI dies, this is why; relaunch with HERMES_TUI_DIAGNOSTICS=1 for a trace.`
  )
}
