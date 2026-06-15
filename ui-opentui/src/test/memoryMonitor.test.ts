import { describe, expect, test } from 'vitest'

import {
  createWarnState,
  evaluateWarn,
  warnLine,
  WARN_FLOOR_BYTES,
  WARN_GROWTH_STEP_BYTES
} from '../logic/memoryMonitor.ts'

const MB = 1024 ** 2

describe('evaluateWarn — #34095 silent-death early-warning', () => {
  test('the first (un-seeded) sample only seeds; never fires even if huge', () => {
    const s = createWarnState()
    const r = evaluateWarn(s, WARN_FLOOR_BYTES + 10 * WARN_GROWTH_STEP_BYTES)
    expect(r.fire).toBe(false)
    expect(r.growthBytes).toBe(0)
    expect(s.lastHeap).toBe(WARN_FLOOR_BYTES + 10 * WARN_GROWTH_STEP_BYTES)
  })

  test('fires once when above the floor AND climbing ≥ the growth step', () => {
    const s = createWarnState()
    evaluateWarn(s, WARN_FLOOR_BYTES) // seed at the floor
    const r = evaluateWarn(s, WARN_FLOOR_BYTES + WARN_GROWTH_STEP_BYTES)
    expect(r.fire).toBe(true)
    expect(r.growthBytes).toBe(WARN_GROWTH_STEP_BYTES)
  })

  test('does not re-fire while it stays high (one-shot until re-armed)', () => {
    const s = createWarnState()
    evaluateWarn(s, WARN_FLOOR_BYTES)
    expect(evaluateWarn(s, WARN_FLOOR_BYTES + WARN_GROWTH_STEP_BYTES).fire).toBe(true)
    // keep climbing — already warned, stays silent
    expect(evaluateWarn(s, WARN_FLOOR_BYTES + 3 * WARN_GROWTH_STEP_BYTES).fire).toBe(false)
    expect(evaluateWarn(s, WARN_FLOOR_BYTES + 6 * WARN_GROWTH_STEP_BYTES).fire).toBe(false)
  })

  test('does NOT fire on slow growth (below the step) even above the floor', () => {
    const s = createWarnState()
    evaluateWarn(s, WARN_FLOOR_BYTES)
    const r = evaluateWarn(s, WARN_FLOOR_BYTES + 10 * MB) // +10MB << 150MB step
    expect(r.fire).toBe(false)
  })

  test('does NOT fire below the floor even on a steep jump (small-heap churn is normal)', () => {
    const s = createWarnState()
    evaluateWarn(s, 100 * MB)
    const r = evaluateWarn(s, 100 * MB + 2 * WARN_GROWTH_STEP_BYTES) // still < 600MB floor
    expect(r.fire).toBe(false)
  })

  test('re-arms after heap falls back below the floor, then can fire again', () => {
    const s = createWarnState()
    evaluateWarn(s, WARN_FLOOR_BYTES)
    expect(evaluateWarn(s, WARN_FLOOR_BYTES + WARN_GROWTH_STEP_BYTES).fire).toBe(true)
    // drop back below the floor → re-arm (warned cleared)
    expect(evaluateWarn(s, 200 * MB).fire).toBe(false)
    expect(s.warned).toBe(false)
    // climb steeply from below-floor straight past the floor → fires again
    // (the jump itself is ≥ step AND lands ≥ floor — exactly the blowup signal)
    expect(evaluateWarn(s, WARN_FLOOR_BYTES + 10 * MB).fire).toBe(true)
  })

  test('honors custom floor/step overrides', () => {
    const s = createWarnState()
    evaluateWarn(s, 50 * MB, 40 * MB, 5 * MB) // floor 40MB, step 5MB
    expect(evaluateWarn(s, 60 * MB, 40 * MB, 5 * MB).fire).toBe(true)
  })
})

describe('warnLine', () => {
  test('reports heap, growth, rss in MB and points at the diagnostics flag', () => {
    const line = warnLine(700 * MB, 900 * MB, 160 * MB)
    expect(line).toContain('700MB')
    expect(line).toContain('+160MB')
    expect(line).toContain('900MB')
    expect(line).toContain('HERMES_TUI_DIAGNOSTICS=1')
  })
})
