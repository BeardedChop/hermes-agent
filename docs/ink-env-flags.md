# Ink TUI — diagnostic environment flags

Non-secret behavioral knobs for the Ink engine (`ui-tui/`). These are
**environment overrides**, not `.env` secrets — set them in your shell for a
session, or `export` them in your shell rc to make them sticky. They mirror the
OpenTUI engine's flags (`docs/opentui-env-flags.md`) so a single switch covers
both engines.

| Flag | Default | What it does |
|---|---|---|
| `HERMES_TUI_DIAGNOSTICS` | off | Master diagnostics switch. Turning it on enables the developer/profiling surface across the TUI — including the memory self-sampler below. One `export HERMES_TUI_DIAGNOSTICS=1` in your shell rc covers **every** session you start, on **either** engine. |
| `HERMES_TUI_MEMLOG` | = `HERMES_TUI_DIAGNOSTICS` | In-process 1Hz memory self-sampling (`ui-tui/src/lib/memlog.ts`) → `~/.hermes/logs/memwatch/<boot>-<pid>.jsonl`. Defaults to the master switch; set `=1` / `=0` to force it on/off independently. |

## What the memory trace captures

Each Ink session, when sampling is enabled, appends one JSON line per second to
its own file under `~/.hermes/logs/memwatch/`, keyed by boot time + pid:

```json
{"t":1781514892,"rss_kb":92148,"heap_used_kb":7234,"external_kb":2378}
```

- `t` — unix seconds.
- `rss_kb` — resident set size (the number that matters for the native-RSS-gap
  story: rss climbing while heap stays flat is the #15141-class signal).
- `heap_used_kb` — V8 heap in use.
- `external_kb` — off-heap (buffers, native allocations).

**Ink emits no `mounted` / `peak_mounted` field.** Those are OpenTUI's
windowing dev counters; Ink has no windowing, so it logs the rss/heap/external
core only. `memwatch-report.mjs` treats `mounted` as optional, so Ink lines
aggregate cleanly alongside OpenTUI's.

## Why this exists — cross-engine memory comparison

The filename scheme, directory, and line schema are **byte-compatible with
OpenTUI's collector** (`ui-opentui/src/boundary/memlog.ts`). Both engines write
to the same `~/.hermes/logs/memwatch/` directory, so one aggregator reads both:

```sh
# enable on either/both engines (master switch covers both)
export HERMES_TUI_DIAGNOSTICS=1
HERMES_TUI_ENGINE=ink     hermes --tui   # Ink session → its own .jsonl
HERMES_TUI_ENGINE=opentui hermes --tui   # OpenTUI session → its own .jsonl

# fleet table across BOTH engines' sessions:
cd ~/github/tui-bench && node memwatch-report.mjs
```

This is what makes a true side-by-side **real-world** memory arc possible —
cold floor → load → plateau/leak — instead of comparing OpenTUI dogfood traces
against an Ink harness with no equivalent data.

## Cost & safety

- ~50 bytes/s when on; one `process.memoryUsage()` + one short append per
  second. The interval is **unref'd** — it never keeps the process alive.
- 14-day retention: older traces are pruned (best-effort) at start.
- **Every failure path disables the logger silently.** Diagnostics must never
  break the TUI — this is the one place the "errors propagate" rule is
  intentionally inverted, matching the OpenTUI collector.
- Off by default: regular users write nothing.

## Getting a meaningful trace

A short scroll-through won't show growth. For a comparison against OpenTUI's
4–5h sessions, drive a tool-heavy 2–3h Ink session as the floor (see
`docs/plans/opentui-ink-asymmetry-note.md` for why the harness ≠ dogfood data).
