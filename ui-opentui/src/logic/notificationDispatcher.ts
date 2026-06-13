/**
 * Notification channel decision — pure routing for an ActivityNotification.
 * Every notification gets the inline transcript card; only "important" ones
 * additionally fire a desktop/terminal OSC notification (to pull the user back
 * to the terminal). The OSC payload shape is termChrome's `TermNotification`;
 * the boundary owns the actual escape-sequence write (termChrome.notifySequences).
 */
import type { ActivityNotification } from './backgroundActivity.ts'
import type { TermNotification } from './termChrome.ts'

export interface NotificationChannels {
  /** Always true — every notification gets the inline transcript card. */
  card: boolean
  /** Present only for "terminal/important" notifications (see notificationChannels). */
  osc?: TermNotification
}

/** Kind substrings that mark a "the work finished, look here" notification —
 *  matched case-insensitively anywhere in the kind. */
const COMPLETION_KIND_HINTS = ['complete', 'done', 'finish']

function isImportant(n: ActivityNotification): boolean {
  if (n.level === 'error' || n.level === 'warn') return true
  const kind = n.kind.toLowerCase()
  return COMPLETION_KIND_HINTS.some(hint => kind.includes(hint))
}

/**
 * Decide the output channels for `n`: ALWAYS the card; ADD an OSC desktop
 * notification when the notification is important enough to interrupt —
 * level 'error'/'warn', or a kind containing 'complete'/'done'/'finish'
 * (case-insensitive). The OSC always titles 'Hermes' with the notification
 * text as the body.
 */
export function notificationChannels(n: ActivityNotification): NotificationChannels {
  if (!isImportant(n)) return { card: true }
  return { card: true, osc: { body: n.text, title: 'Hermes' } }
}
