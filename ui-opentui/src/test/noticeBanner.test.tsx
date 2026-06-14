/**
 * NoticeBanner frame tests — the persistent chrome banner for `state.notice`.
 *   1. renders the (already-glyphed) text VERBATIM, with no extra leading marker;
 *   2. each level (warn/success/error) renders its text + picks the right tint;
 *   3. a null notice renders an empty frame;
 *   4. long text truncates to the terminal width (never wraps).
 */
import { RGBA } from '@opentui/core'
import { describe, expect, test } from 'vitest'

import { createSessionStore } from '../logic/store.ts'
import { NoticeBanner } from '../view/noticeBanner.tsx'
import { ThemeProvider } from '../view/theme.tsx'
import { captureFrame, renderProbe } from './lib/render.ts'

const theme = () => createSessionStore().state.theme

describe('NoticeBanner frame', () => {
  test('renders the glyphed text verbatim, with no doubled marker', async () => {
    const frame = await captureFrame(
      () => (
        <ThemeProvider theme={theme}>
          <NoticeBanner notice={{ id: 'n1', text: '⚠ Credits 90% used · $20 cap', level: 'warn', kind: 'usage' }} />
        </ThemeProvider>
      ),
      { width: 60, height: 4 }
    )
    expect(frame).toContain('Credits 90% used')
    expect(frame).toContain('⚠') // the gateway glyph survives verbatim…
    expect(frame).not.toContain('◆') // …and the card marker is NOT added
  })

  test('a warn notice and a success notice each render their text', async () => {
    const warn = await captureFrame(
      () => (
        <ThemeProvider theme={theme}>
          <NoticeBanner notice={{ id: 'w', text: '⚠ Credits 90% used', level: 'warn', kind: 'usage' }} />
        </ThemeProvider>
      ),
      { width: 60, height: 4 }
    )
    expect(warn).toContain('Credits 90% used')

    const success = await captureFrame(
      () => (
        <ThemeProvider theme={theme}>
          <NoticeBanner notice={{ id: 's', text: '✓ Credit access restored', level: 'success', kind: 'usage' }} />
        </ThemeProvider>
      ),
      { width: 60, height: 4 }
    )
    expect(success).toContain('Credit access restored')
  })

  test('tints by level: warn → theme warn, success → statusGood, error → error', async () => {
    const colors = theme().color
    const cases: Array<{ level: 'warn' | 'success' | 'error'; text: string; expected: string }> = [
      { level: 'warn', text: '⚠ warn line', expected: colors.warn },
      { level: 'success', text: '✓ ok line', expected: colors.statusGood },
      { level: 'error', text: '✕ err line', expected: colors.error }
    ]
    for (const c of cases) {
      const probe = await renderProbe(
        () => (
          <ThemeProvider theme={theme}>
            <NoticeBanner notice={{ id: c.level, text: c.text, level: c.level, kind: 'usage' }} />
          </ThemeProvider>
        ),
        { width: 60, height: 4 }
      )
      try {
        let span: { fg: RGBA } | undefined
        for (const line of probe.spans().lines) {
          for (const s of line.spans) {
            if (s.text.includes('line')) span = s
          }
        }
        expect(span).toBeDefined()
        expect(span!.fg.toInts().slice(0, 3)).toEqual(RGBA.fromHex(c.expected).toInts().slice(0, 3))
      } finally {
        probe.destroy()
      }
    }
  })

  test('a null notice renders an empty frame (no banner text)', async () => {
    const frame = await captureFrame(
      () => (
        <ThemeProvider theme={theme}>
          <NoticeBanner notice={null} />
        </ThemeProvider>
      ),
      { width: 60, height: 4 }
    )
    expect(frame).not.toContain('Credits')
    expect(frame.trim()).toBe('')
  })

  test('long text truncates to the terminal width (never wraps)', async () => {
    const width = 20
    const long = '⚠ Credits 90% used · $20 cap · run /usage for your current balance details'
    const frame = await captureFrame(
      () => (
        <ThemeProvider theme={theme}>
          <NoticeBanner notice={{ id: 'l', text: long, level: 'warn', kind: 'usage' }} />
        </ThemeProvider>
      ),
      { width, height: 4 }
    )
    // No rendered line exceeds the terminal width → it clipped instead of wrapping.
    for (const line of frame.split('\n')) {
      expect(line.length).toBeLessThanOrEqual(width)
    }
    expect(frame).toContain('…') // truncRight ellipsis present
  })
})
