/**
 * memoryMonitor — the early-warning BOUNDARY (touches node:process; the pure
 * threshold/growth logic lives in logic/memoryMonitor.ts).
 *
 * Ports the high-value #34095 silent-death early-warning from Ink
 * (`ui-tui/src/lib/memoryMonitor.ts`) to the OpenTUI engine, and ONLY that:
 *   - NO auto heap-snapshot capture (the #41948 disk-fill bug class is not
 *     re-imported — the always-on memlog NDJSON trace is the diagnosis path,
 *     and its rss-vs-heap divergence is the better diagnostic for the native
 *     RSS-leak class a V8 snapshot captures poorly).
 *   - NO Ink cache eviction (Solid disposes out-of-window rows; windowing +
 *     proactiveGc already cover memory pressure).
 *
 * It polls `process.memoryUsage()` on a 10s unref'd interval and, when the
 * pure detector fires, surfaces a single transcript system line so the user
 * SEES "memory climbing fast" before Node OOMs under the exit threshold. This
 * is ON by default (unlike memlog/heapdump): it's a user-facing safety
 * heads-up, not a diagnostic dump, and costs one memoryUsage() read per 10s
 * with zero disk. Every failure path disables silently (a diagnostic must
 * never break the TUI — the one place the "errors propagate" rule is
 * intentionally inverted, matching memlog/proactiveGc).
 */
import { createWarnState, evaluateWarn, warnLine } from '../logic/memoryMonitor.ts'

/** Sample cadence — matches Ink's monitor (10s, unref'd). */
const SAMPLE_MS = 10_000

/**
 * Start the early-warning watcher. `emitWarn` receives the ready-to-show system
 * line on the (one-shot) tick growth looks abnormal. Returns a stop function.
 * The interval is unref'd so it never keeps the process alive.
 */
export function startMemoryMonitor(emitWarn: (line: string) => void): () => void {
  const state = createWarnState()
  const timer = setInterval(() => {
    try {
      const { heapUsed, rss } = process.memoryUsage()
      const { fire, growthBytes } = evaluateWarn(state, heapUsed)
      if (fire) emitWarn(warnLine(heapUsed, rss, growthBytes))
    } catch {
      clearInterval(timer) // a failing diagnostic must not retry forever
    }
  }, SAMPLE_MS)
  timer.unref?.()
  return () => clearInterval(timer)
}
