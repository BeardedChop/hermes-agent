/**
 * TodoTool — renderer for the `todo` task-list tool.
 *
 * Panel-primary / inline-minimal: the live task list is shown by the pinned
 * TodoPanel above the composer (view/todoPanel.tsx), so the in-transcript tool
 * call collapses to a one-line SUMMARY ("10 tasks · 1 done, 1 in progress,
 * 8 open") instead of dumping the raw JSON. Expanding it shows a clean
 * checklist (the historical plan at that point), NEVER the JSON blob.
 *
 * Wire shape (tools/todo_tool.py result.to_dict / acp_adapter/tools.py):
 *   { todos: [{ id, content, status }], summary: { completed, in_progress,
 *     pending, cancelled } }
 *   status ∈ pending | in_progress | completed | cancelled
 * List ORDER is priority (tools/todo_tool.py) — never re-sort; the in_progress
 * item is emphasized by glyph + colour, not by reordering.
 */
import { createMemo, For, Show } from 'solid-js'

import type { ToolPartState } from '../../logic/store.ts'
import { truncate } from '../../logic/toolOutput.ts'
import { useTheme } from '../theme.tsx'
import { defaultSubtitle, structuredResult } from './defaultTool.tsx'
import type { ToolBodyProps, ToolRenderer } from './registry.tsx'

export type TodoStatus = 'pending' | 'in_progress' | 'completed' | 'cancelled'

export interface TodoItem {
  content: string
  status: TodoStatus
}

/** Per-state glyph (single-width, in the existing geometric palette). */
export function todoGlyph(status: TodoStatus): string {
  switch (status) {
    case 'completed':
      return '✓'
    case 'in_progress':
      return '▣'
    case 'cancelled':
      return '✗'
    default:
      return '☐'
  }
}

/** Parse the todos array out of a part's structured result/args. */
export function todosOf(part: ToolPartState): TodoItem[] {
  const r = structuredResult(part)
  const raw = r?.['todos'] ?? part.args?.['todos']
  if (!Array.isArray(raw)) return []
  const out: TodoItem[] = []
  for (const t of raw) {
    if (!t || typeof t !== 'object') continue
    const o = t as Record<string, unknown>
    const content = typeof o['content'] === 'string' ? o['content'] : ''
    const status = normalizeStatus(o['status'])
    if (content) out.push({ content, status })
  }
  return out
}

function normalizeStatus(s: unknown): TodoStatus {
  if (s === 'completed' || s === 'in_progress' || s === 'cancelled') return s
  return 'pending'
}

export interface TodoCounts {
  total: number
  completed: number
  in_progress: number
  pending: number
  cancelled: number
}

/** Counts by state — prefers the gateway summary, else derives from the list. */
export function todoCounts(part: ToolPartState): TodoCounts {
  const todos = todosOf(part)
  const s = structuredResult(part)?.['summary']
  if (s && typeof s === 'object' && !Array.isArray(s)) {
    const o = s as Record<string, unknown>
    const num = (k: string): number => {
      const v = o[k]
      return typeof v === 'number' ? v : 0
    }
    const completed = num('completed')
    const in_progress = num('in_progress')
    const pending = num('pending')
    const cancelled = num('cancelled')
    const total = completed + in_progress + pending + cancelled || todos.length
    return { total, completed, in_progress, pending, cancelled }
  }
  const counts: TodoCounts = { total: todos.length, completed: 0, in_progress: 0, pending: 0, cancelled: 0 }
  for (const t of todos) counts[t.status]++
  return counts
}

/** One-line summary subtitle: "10 tasks · 1 done, 1 in progress, 8 open"
 *  (zero-count buckets dropped). */
export function todoSummary(part: ToolPartState): string {
  const c = todoCounts(part)
  if (c.total === 0) return ''
  const bits: string[] = []
  if (c.completed) bits.push(`${c.completed} done`)
  if (c.in_progress) bits.push(`${c.in_progress} in progress`)
  if (c.pending) bits.push(`${c.pending} open`)
  if (c.cancelled) bits.push(`${c.cancelled} cancelled`)
  const tail = bits.length ? ` · ${bits.join(', ')}` : ''
  return `${c.total} task${c.total === 1 ? '' : 's'}${tail}`
}

/** Expanded body: the full checklist (historical plan), in list order. */
export function TodoToolBody(props: ToolBodyProps) {
  const theme = useTheme()
  const todos = createMemo(() => todosOf(props.part))
  const colorFor = (status: TodoStatus): string => {
    const c = theme().color
    switch (status) {
      case 'completed':
        return c.ok
      case 'in_progress':
        return c.accent
      case 'cancelled':
        return c.muted
      default:
        return c.text
    }
  }
  return (
    <Show when={todos().length > 0} fallback={null}>
      <box style={{ flexDirection: 'column', flexGrow: 1, minWidth: 0 }}>
        <For each={todos()}>
          {item => (
            <text selectionBg={theme().color.selectionBg}>
              <span style={{ fg: colorFor(item.status) }}>{todoGlyph(item.status)} </span>
              <span
                style={{
                  fg:
                    item.status === 'completed' || item.status === 'cancelled'
                      ? theme().color.muted
                      : theme().color.text
                }}
              >
                {truncate(item.content, Math.max(1, props.width - 2))}
              </span>
            </text>
          )}
        </For>
      </box>
    </Show>
  )
}

export const todoRenderer: ToolRenderer = {
  Body: TodoToolBody,
  // Expandable when there's a real list to show.
  expandable: part => todosOf(part).length > 0,
  // Honest "(N lines)" = one row per todo.
  lines: part => todosOf(part).map(t => `${todoGlyph(t.status)} ${t.content}`),
  // Collapsed = the summary line (the live list lives in the pinned panel).
  subtitle: part => todoSummary(part) || defaultSubtitle(part)
}
