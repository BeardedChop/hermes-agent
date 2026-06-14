/**
 * NoticeBanner — the persistent chrome banner for `state.notice` (the visible
 * credits/usage notice with a lifecycle, set by the store from gateway policy).
 * Distinct from `NotificationCard`: the card is an inline transcript row (one per
 * `notification.show`); THIS is a single sticky chrome line that sits directly
 * above the status bar, mirroring the bar's left padding.
 *
 * The `text` is ALREADY glyphed by the gateway policy (e.g. `⚠ Credits 90% used`,
 * `✕ Credit access paused`, `✓ Credit access restored`), so the banner renders it
 * VERBATIM — it only tints by level, never prepends another glyph. Truncates to
 * the terminal width so it can never wrap and push the composer.
 */
import { Show } from 'solid-js'

import type { ActivityNotification } from '../logic/backgroundActivity.ts'
import { truncRight } from '../logic/truncate.ts'
import { useDimensions } from './dimensions.tsx'
import { useTheme } from './theme.tsx'

export function NoticeBanner(props: { notice: ActivityNotification | null }) {
  const theme = useTheme()
  const dims = useDimensions()
  const n = () => props.notice
  const levelColor = () => {
    const c = theme().color
    const level = n()?.level
    return level === 'error' ? c.error : level === 'warn' ? c.warn : level === 'success' ? c.statusGood : c.accent
  }
  // Budget the text into the row so it never wraps: total − paddingLeft(1) − a
  // right margin(1). Matches how statusBar/backgroundPanel budget chrome rows.
  const text = () => truncRight(n()?.text ?? '', Math.max(8, dims().width - 2))
  return (
    <Show when={props.notice}>
      <box style={{ flexShrink: 0, paddingLeft: 1 }}>
        <text selectable={false}>
          <span style={{ fg: levelColor() }}>{text()}</span>
        </text>
      </box>
    </Show>
  )
}
