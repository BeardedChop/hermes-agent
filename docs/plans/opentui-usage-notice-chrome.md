# OpenTUI — usage/credits notice in the composer chrome

**Status:** spec (not started) · **Engine:** `ui-opentui/` · **Author:** glitch · 2026-06-14

## Goal

Render the gateway's **usage / credits notices** as a persistent, level-tinted
**chrome banner pinned at the top of the input zone** (directly above the status
bar), with the same lifecycle the Ink engine already has — sticky vs TTL,
mid-turn hold + turn-end reveal, and "flash-and-yield" for the usage bands.

Today the OpenTUI engine **receives** these notices but mis-renders them as
scrolling inline transcript cards with no lifecycle. This spec fixes that without
touching the gateway or the agent (the data already flows correctly).

## What already exists (verified)

### The wire (source of truth — do NOT change)
The gateway emits one event for every notice, snake_case payload:

```
notification.show   payload { text, level, kind, ttl_ms, key, id }   # tui_gateway/server.py:2878
notification.clear  payload { key }                                  # tui_gateway/server.py:2890
```

These come from `AgentNotice` (`agent/credits_tracker.py:177`). The credits
policy (`evaluate_credits_notices`, `agent/credits_tracker.py:245`) emits exactly
four notices — the full catalog this feature renders:

| `key`                 | `text` (already glyphed by policy)              | `level`   | `kind`   | `ttl_ms` | lifecycle      |
|-----------------------|-------------------------------------------------|-----------|----------|----------|----------------|
| `credits.usage`       | `⚠/• Credits N% used · $X cap` (bands 50/75/90) | info/warn | `sticky` | —        | flash-and-yield |
| `credits.grant_spent` | `• Grant spent · $X top-up left`                | info      | `sticky` | —        | flash-and-yield |
| `credits.depleted`    | `✕ Credit access paused · run /usage for balance` | error   | `sticky` | —        | sticky          |
| `credits.restored`    | `✓ Credit access restored`                      | success   | `ttl`    | `8000`   | TTL self-expire |

**Load-bearing facts:**
- `text` is **already glyphed** (⚠ • ✕ ✓) by the Python policy — the renderer
  **must not** prepend another glyph. It only tints by `level`.
- `level` includes **`success`** (green) — a level the current OpenTUI parser
  silently drops to `info`.
- `kind` is the **lifecycle marker** (`sticky` | `ttl`), NOT a display label.
  `id` == `key` (stable per kind, not unique per emission).
- Notices are **reconciled**: the policy emits `to_clear` (a `notification.clear`)
  then `to_show`. A band change clears `credits.usage` then re-shows it.

### The Ink reference behavior (what we're matching)
`ui-tui/src/app/turnController.ts` + `appChrome.tsx`:
- `showNotice` (`:181`): if **busy**, hold in `pendingNotice` (latest-wins);
  if idle, apply now.
- `applyNotice` (`:213`): set the visible notice; for `kind: 'ttl'` with
  `ttl_ms > 0`, arm a self-expiry timer (clearing any prior timer first).
- `clearNotice(key)` (`:198`): drop the visible **and** pending notice only when
  the key matches (a stale clear must not wipe a newer notice).
- `flushPendingNotice` (`:245`): at **turn end** (only the real end sites) apply
  the held notice — its TTL clock starts here, when it first becomes visible.
- **Flash-and-yield** (`startMessage`, `:917`): at **turn start**, if the visible
  notice's key is `credits.usage` or `credits.grant_spent`, clear it — "show
  once, then get out of the way." `credits.depleted` and others stay sticky. The
  Python `active` latch keeps the key so it won't re-fire next turn.
- Session reset clears all notice state so session A's notice can't bleed into B.
- Color by level: `error→error`, `warn→warn`, `success→statusGood`,
  `info→accent` (`noticeColor`, `appChrome.tsx:192`).

### The OpenTUI side (what we change)
- `notification.show` → `parseNotification` → `pushNotification` → **inline card**
  in the transcript (`store.ts:832`, `notificationCard.tsx`). All kinds, no
  lifecycle. The Option B process-completion card (`kind: 'process.complete'`)
  and `background.complete` (`kind: 'background task complete'`) also use this
  path — **they must keep working unchanged.**
- `parseNotification` coerces `level` to `info|warn|error` only
  (`backgroundActivity.ts:48`) — drops `success`.
- Store carries `lastNotification` (OSC seam), `bgTasks`; **no** `notice` slot.
- Theme has `accent`, `warn`, `error`, `ok`/`statusGood`, `muted`
  (`logic/theme.ts`) — `success` maps to `statusGood`.
- Input zone layout (`view/App.tsx:140-211`): a top-bordered column —
  `<StatusBar>` → composer `<Switch>` → `<AgentsTray>`. The new banner mounts at
  `App.tsx:144`, **directly above `<StatusBar>`** (the topmost line of the chrome).
- Turn lifecycle hooks: `case 'message.start'` (`store.ts:779`, sets
  `info.running = true`) and `case 'message.complete'` (`store.ts:811`, sets
  `info.running = false`). `clearTranscript` (`store.ts:631`) is the reset site.
- `Date.now()` is used freely in the store (`:877`) — `setTimeout` for TTL is fine.

## The one design decision: routing

`kind` is the discriminator. **`notification.show` with `kind === 'sticky'` or
`kind === 'ttl'` → the new chrome-notice path; every other kind → the existing
inline-card path, untouched.** This mirrors Ink's `Notice.kind: 'sticky' | 'ttl'`
exactly, and the credits policy sets `kind` to one of those for all four notices,
while the process/background cards use label-strings (`process.complete`,
`background task complete`) that are neither — so they stay inline cards. No
gateway change, no key-prefix sniffing.

**Divergence from Ink (intentional):** Ink hides the notice while busy because the
FaceTicker shares its one status slot. OpenTUI's busy face (`StatusLine`) lives in
the transcript area, so the banner has a **dedicated row** and stays visible
through a turn (a depletion warning shouldn't vanish mid-turn). We still **hold
new notices** that arrive mid-turn (`pendingNotice`) and reveal them at turn end —
matching Ink's "don't pop a fresh banner mid-stream" intent.

## Implementation

### Phase 1 — parser + type (`logic/backgroundActivity.ts`)
1. Widen `ActivityNotification.level` to `'info' | 'warn' | 'error' | 'success'`.
2. `coerceLevel`: also accept `'success'` (still fall back to `'info'`).
3. Add `export function isChromeNotice(n: ActivityNotification): boolean` →
   `n.kind === 'sticky' || n.kind === 'ttl'`.
4. `parseNotification` already maps `ttl_ms → ttlMs` and preserves `key`/`id` —
   no shape change beyond the widened level.

**Tests** (`backgroundActivity.test.ts` or `notificationCard.test.tsx`):
`success` survives parse; `kind: 'ttl'` + `ttl_ms` → `ttlMs`; `isChromeNotice`
true for sticky/ttl, false for `process.complete`/`''`.

### Phase 2 — store lifecycle (`logic/store.ts`)
Add state + a private (non-reactive) timer handle in `createSessionStore`:
- `notice: ActivityNotification | null` (visible chrome notice) — new state field,
  init `null`.
- `pendingNotice: ActivityNotification | null` — held mid-turn, init `null`.
- `let noticeTimer: ReturnType<typeof setTimeout> | undefined` (closure var).

Functions (port of `turnController`):
- `showNotice(n)`: `state.info.running ? setState('pendingNotice', n) : applyNotice(n)`
  (latest-wins — assigning replaces any prior pending).
- `applyNotice(n)`: clear `noticeTimer`; `setState('notice', n)`; if
  `n.kind === 'ttl' && n.ttlMs && n.ttlMs > 0`, arm `setTimeout(n.ttlMs)` that
  clears `notice` only if `state.notice?.id === n.id` (defensive guard).
- `clearNotice(key)`: if `state.pendingNotice?.key === key` → null it; if
  `state.notice?.key === key` → clear timer + null `notice`.
- `flushPendingNotice()`: if `state.pendingNotice` → `applyNotice` it, null pending.
- `clearNoticeState()`: null `notice` + `pendingNotice`, clear timer.

Wire into the event reducer:
- `notification.show` (`store.ts:832`): route —
  `const n = parseNotification(...); if (!n) break; if (isChromeNotice(n)) showNotice(n); else pushNotification(n)`.
  (Still record `lastNotification` for the OSC seam in **both** paths — extract
  the `setState('lastNotification', {...n})` so a chrome notice also pings a
  blurred terminal, matching the inline-card behavior.)
- `notification.clear` (`store.ts:837`): call **both** `clearNotificationCards(key)`
  (cards) **and** `clearNotice(key)` (chrome) — a key only ever lives in one, so
  calling both is safe and avoids guessing.
- `message.start` (`store.ts:779`): flash-and-yield — if
  `state.notice?.key === 'credits.usage' || === 'credits.grant_spent'` →
  `clearNotice(state.notice.key)`. (Do this **before** flipping `running` true so
  the read is clean.)
- `message.complete` (`store.ts:811`): call `flushPendingNotice()` (after the
  `running = false` set, so a held notice reveals on the now-idle bar).
- `clearTranscript` (`store.ts:631`) and any session-switch reset:
  `clearNoticeState()`.

Export `notice` via the store's state and `showNotice`/`clearNotice` if a test or
future slash command needs them.

**Tests** (`statusNotice.test.ts`, new):
- idle `showNotice` → `state.notice` set, no card pushed.
- routing: `notification.show` `kind:'sticky'` → `notice` set, **no** transcript
  card; `kind:'process.complete'` → card pushed, `notice` still null.
- mid-turn hold: `message.start` → `showNotice` → `notice` stays null,
  `pendingNotice` set → `message.complete` → `notice` revealed.
- `clearNotice` by key drops visible + pending; non-matching key is a no-op.
- TTL: `kind:'ttl', ttlMs:50` auto-clears (vitest fake timers).
- flash-and-yield: visible `credits.usage` cleared on `message.start`;
  `credits.depleted` persists across a start/complete cycle.
- `clearTranscript` resets `notice` + `pendingNotice`.
- `success` notice keeps its level.

### Phase 3 — view (`view/noticeBanner.tsx` + `App.tsx`)
New `NoticeBanner` (sibling style to `notificationCard.tsx`):
- Props: `notice: ActivityNotification | null`, plus terminal width for truncation.
- `<Show when={notice}>` — renders nothing when null.
- One row, `flexShrink: 0`, `paddingLeft: 1`, `selectable={false}`.
- Text rendered **verbatim** (glyph already present), tinted by level:
  `error→error`, `warn→warn`, `success→statusGood`, `info→accent`.
- Truncate to width with `truncRight` (`logic/truncate.ts`) so a long notice can
  never push the composer or wrap.

Mount in `App.tsx:144`, the first child of the top-bordered input zone, directly
above `<StatusBar store={...} />`:
```tsx
<box border={['top']} ...>
  <NoticeBanner notice={props.store.state.notice} />   {/* new */}
  <StatusBar store={props.store} />
  ...
```

**Tests** (`noticeBanner.test.tsx`, frame): renders the text without adding a
glyph; warn→warn color, success→statusGood color; truncates at narrow width;
renders an empty frame when `notice` is null.

### Phase 4 — parity verification + docs
- `npm run check` green (prettier + eslint + vitest).
- Headless frame dump: a `credits.usage` warn banner above the status bar; a
  `credits.depleted` error banner surviving a turn; a `credits.restored` success
  banner that disappears after its TTL.
- tmux smoke per `docs/opentui-dev-handoff.md` (inject the three notices via the
  test harness / a scripted gateway event; screenshot the chrome).
- Cross-check the four-notice catalog renders identically in tone to Ink's
  `appChromeStatusRule` (color-by-level, no double glyph, truncation).

## Non-goals
- No gateway/agent changes — the wire and the policy are the source of truth.
- No new notice kinds — render exactly the four the policy emits.
- The inline-card path (process/background completions) is **unchanged**.
- No status-bar segment changes — the banner is its own row above the bar.

## Risk / footguns
- **Schema decode-at-boundary**: `notification.show` payload is a loose Record
  read by `parseNotification`, not strict-decoded — a wrong-typed field won't blank
  the bar (unlike `applyInfo`). Keep the loose reads.
- **createStore reference-aliasing**: store `notice` and `pendingNotice` distinct
  objects; when applying pending, it's already its own object — don't alias it to
  `lastNotification`. (See `[[solid-createstore-reference-aliasing]]`.)
- **Timer leak**: `clearNoticeState` must clear `noticeTimer`; ensure session
  reset and store dispose clear it so a TTL callback can't fire into a dead store.
- **Routing regression**: assert in tests that `process.complete` /
  `background task complete` still produce **cards**, not banners — the whole
  feature hinges on the `kind` discriminator.
