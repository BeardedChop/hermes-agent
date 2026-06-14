/**
 * proactiveGc — opt-in, idle-gated `global.gc()` for the low-mem path (W2).
 *
 * GATED on the low-mem opt-in: only runs when the user set a LOW
 * `HERMES_TUI_HEAP_MB` (the same knob W1 threads into `--max-old-space-size`).
 * Default / unconstrained sessions do NOTHING — no proactive GC, no divergence
 * from Ink on the default path (Ink never calls gc proactively; it only exposes
 * it for heapdumps, so W2 is OpenTUI-only by design — spec D5).
 *
 * TRIGGER MODEL — idle-gated, never mid-stream:
 *   - A low-frequency timer ticks every IDLE_MS. On each tick it calls
 *     `global.gc()` ONLY when (a) a turn is NOT streaming (`isStreaming()` false
 *     — so we never pause mid-render/mid-reply) and (b) at least one full idle
 *     window has passed since the last activity (stream end / explicit touch).
 *   - If RSS crosses RSS_EAGER_KB (>400MB) the cadence tightens (EAGER_MS) but
 *     it STILL waits for idle — eagerness shortens the window, never bypasses it.
 *   - `--expose-gc` (W1) makes `global.gc` real; without it this is a silent
 *     no-op (we detect and disable). The timer is unref'd — it never keeps the
 *     process alive — and every failure path disables silently (a GC helper must
 *     never break the TUI).
 *
 * Reuses `process.memoryUsage().rss` (same read as memlog) for the >400MB check.
 */
import { envFlag } from '../logic/env.ts'

/** Below this heap cap (MB) we treat the session as low-mem opt-in. 8192 is the
 *  default; anyone who set a cap materially under it wants tight memory. */
const LOW_MEM_HEAP_MB = 4096
/** Idle window (ms): time since last activity before a GC is allowed. */
const IDLE_MS = 8000
/** Tightened idle window once RSS is high. */
const EAGER_MS = 3000
/** RSS (KB) above which GC becomes eager (still idle-gated). 400MB. */
const RSS_EAGER_KB = 400 * 1024

/** The configured heap cap in MB from the W1 knob, or null when unset/garbage.
 *  The Python launcher reads the same env; the child inherits it, so the Node
 *  side can read it directly to know whether low-mem mode is active. */
function configuredHeapMb(): number | null {
  const v = (process.env.HERMES_TUI_HEAP_MB ?? '').trim()
  if (!/^\d+$/.test(v)) return null
  const n = Number.parseInt(v, 10)
  return n > 0 ? n : null
}

/** Whether proactive GC should run: a low heap cap is set AND gc is exposed.
 *  `HERMES_TUI_PROACTIVE_GC` can force it on/off, but defaults to the low-mem
 *  signal so the knob composes (spec D9: independent knobs). */
export function proactiveGcEnabled(heapMb: number | null = configuredHeapMb()): boolean {
  const lowMem = heapMb !== null && heapMb <= LOW_MEM_HEAP_MB
  return envFlag(process.env.HERMES_TUI_PROACTIVE_GC, lowMem) && typeof global.gc === 'function'
}

/**
 * Start the idle-gated proactive GC watcher. `isStreaming` reports whether a
 * turn is mid-flight (read from the store's `info.running`). Returns a stop
 * function and a `touch()` to mark fresh activity (e.g. on keypress / stream
 * start) so the idle clock resets. No-op (returns inert handles) when disabled.
 */
export function startProactiveGc(isStreaming: () => boolean): { stop: () => void; touch: () => void } {
  if (!proactiveGcEnabled()) return { stop: () => {}, touch: () => {} }
  const gc = global.gc
  if (typeof gc !== 'function') return { stop: () => {}, touch: () => {} }

  let lastActivity = Date.now()
  const touch = () => {
    lastActivity = Date.now()
  }

  // Tick at the eager cadence; the idle-window check (below) does the real
  // gating, so a high-RSS session reacts within EAGER_MS while a calm one still
  // waits the full IDLE_MS. One cheap rss read + compare per tick.
  const timer = setInterval(() => {
    try {
      if (isStreaming()) {
        // mid-stream: defer entirely and keep the clock fresh so a GC can't fire
        // the instant the stream ends — it waits a full idle window after.
        lastActivity = Date.now()
        return
      }
      const rssKb = Math.floor(process.memoryUsage().rss / 1024)
      const window = rssKb > RSS_EAGER_KB ? EAGER_MS : IDLE_MS
      if (Date.now() - lastActivity < window) return
      gc()
      // After a collection, reset the clock so we don't GC every tick — the next
      // one waits another full idle window.
      lastActivity = Date.now()
    } catch {
      clearInterval(timer) // a failing GC helper must not retry forever
    }
  }, EAGER_MS)
  timer.unref?.()

  return { stop: () => clearInterval(timer), touch }
}
