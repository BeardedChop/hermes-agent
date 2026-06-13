/**
 * Notification channel-decision tests. Card is always on; OSC fires only for
 * important notifications (error/warn level, or a completion-ish kind).
 */
import { describe, expect, test } from 'vitest'

import type { ActivityNotification } from '../logic/backgroundActivity.ts'
import { notificationChannels } from '../logic/notificationDispatcher.ts'

function notif(over: Partial<ActivityNotification>): ActivityNotification {
  return { id: 'n', kind: '', level: 'info', text: 'something happened', ...over }
}

describe('notificationChannels', () => {
  test('card is always true', () => {
    expect(notificationChannels(notif({})).card).toBe(true)
    expect(notificationChannels(notif({ level: 'error' })).card).toBe(true)
  })

  test('plain info → no osc', () => {
    expect(notificationChannels(notif({ level: 'info', kind: 'progress' })).osc).toBeUndefined()
  })

  test('error and warn levels fire osc', () => {
    expect(notificationChannels(notif({ level: 'error' })).osc).toBeDefined()
    expect(notificationChannels(notif({ level: 'warn' })).osc).toBeDefined()
  })

  test('completion-ish kinds fire osc, case-insensitive (complete/done/finish)', () => {
    expect(notificationChannels(notif({ kind: 'task.complete' })).osc).toBeDefined()
    expect(notificationChannels(notif({ kind: 'JOB_DONE' })).osc).toBeDefined()
    expect(notificationChannels(notif({ kind: 'Finished' })).osc).toBeDefined()
    // substring match anywhere in the kind
    expect(notificationChannels(notif({ kind: 'agent.run.completed' })).osc).toBeDefined()
    // a non-completion info kind stays card-only
    expect(notificationChannels(notif({ kind: 'started' })).osc).toBeUndefined()
  })

  test('osc body == text, title == "Hermes"', () => {
    const ch = notificationChannels(notif({ level: 'error', text: 'build broke' }))
    expect(ch.osc).toEqual({ body: 'build broke', title: 'Hermes' })
  })
})
