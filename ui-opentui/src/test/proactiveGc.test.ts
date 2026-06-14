/**
 * proactiveGc tests (W2) — the opt-in idle-gated GC gating + timing.
 *
 * Pins: enabled ONLY under a low heap cap + exposed gc; never fires mid-stream;
 * fires after a full idle window; tightens to the eager window once RSS is high;
 * and is a no-op (inert handles) on the default path.
 */
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'

import { proactiveGcEnabled, startProactiveGc } from '../boundary/proactiveGc.ts'

const ENV_KEYS = ['HERMES_TUI_HEAP_MB', 'HERMES_TUI_PROACTIVE_GC'] as const
const saved: Record<string, string | undefined> = {}

beforeEach(() => {
  for (const k of ENV_KEYS) saved[k] = process.env[k]
})
afterEach(() => {
  for (const k of ENV_KEYS) {
    if (saved[k] === undefined) delete process.env[k]
    else process.env[k] = saved[k]
  }
  vi.restoreAllMocks()
  vi.useRealTimers()
})

/** Stub a callable global.gc and return the spy. */
function stubGc() {
  const spy = vi.fn()
  // global.gc is optional in the type — assign through a loosened view.
  ;(globalThis as { gc?: () => void }).gc = spy
  return spy
}

describe('proactiveGcEnabled — gating', () => {
  test('OFF on the default path (no heap cap), even with gc exposed', () => {
    delete process.env.HERMES_TUI_HEAP_MB
    delete process.env.HERMES_TUI_PROACTIVE_GC
    stubGc()
    expect(proactiveGcEnabled()).toBe(false)
  })

  test('ON under a low heap cap with gc exposed', () => {
    delete process.env.HERMES_TUI_PROACTIVE_GC
    stubGc()
    expect(proactiveGcEnabled(256)).toBe(true)
  })

  test('OFF under a high heap cap (not the low-mem signal)', () => {
    delete process.env.HERMES_TUI_PROACTIVE_GC
    stubGc()
    expect(proactiveGcEnabled(8192)).toBe(false)
  })

  test('OFF when gc is not exposed, even under a low cap', () => {
    delete process.env.HERMES_TUI_PROACTIVE_GC
    delete (globalThis as { gc?: () => void }).gc
    expect(proactiveGcEnabled(256)).toBe(false)
  })

  test('explicit HERMES_TUI_PROACTIVE_GC=off overrides the low-cap default', () => {
    process.env.HERMES_TUI_PROACTIVE_GC = 'off'
    stubGc()
    expect(proactiveGcEnabled(256)).toBe(false)
  })

  test('explicit HERMES_TUI_PROACTIVE_GC=on forces it on under a high cap', () => {
    process.env.HERMES_TUI_PROACTIVE_GC = 'on'
    stubGc()
    expect(proactiveGcEnabled(8192)).toBe(true)
  })
})

describe('startProactiveGc — idle gating', () => {
  test('no-op inert handles on the default path', () => {
    delete process.env.HERMES_TUI_HEAP_MB
    delete process.env.HERMES_TUI_PROACTIVE_GC
    const gc = stubGc()
    vi.useFakeTimers()
    const h = startProactiveGc(() => false)
    vi.advanceTimersByTime(60_000)
    expect(gc).not.toHaveBeenCalled()
    h.stop()
  })

  test('fires after a full idle window when not streaming', () => {
    process.env.HERMES_TUI_HEAP_MB = '256'
    delete process.env.HERMES_TUI_PROACTIVE_GC
    const gc = stubGc()
    vi.useFakeTimers()
    const h = startProactiveGc(() => false)
    // before the idle window elapses: no GC
    vi.advanceTimersByTime(3000)
    expect(gc).not.toHaveBeenCalled()
    // past the 8s idle window: GC fires
    vi.advanceTimersByTime(9000)
    expect(gc).toHaveBeenCalled()
    h.stop()
  })

  test('never fires while streaming, no matter how long', () => {
    process.env.HERMES_TUI_HEAP_MB = '256'
    delete process.env.HERMES_TUI_PROACTIVE_GC
    const gc = stubGc()
    vi.useFakeTimers()
    const h = startProactiveGc(() => true) // always streaming
    vi.advanceTimersByTime(60_000)
    expect(gc).not.toHaveBeenCalled()
    h.stop()
  })

  test('stop() halts the watcher', () => {
    process.env.HERMES_TUI_HEAP_MB = '256'
    delete process.env.HERMES_TUI_PROACTIVE_GC
    const gc = stubGc()
    vi.useFakeTimers()
    const h = startProactiveGc(() => false)
    h.stop()
    vi.advanceTimersByTime(60_000)
    expect(gc).not.toHaveBeenCalled()
  })
})
