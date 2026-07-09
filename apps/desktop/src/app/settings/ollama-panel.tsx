import { useCallback, useEffect, useRef, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { RowButton } from '@/components/ui/row-button'
import {
  deleteOllamaModel,
  getOllamaModels,
  loadOllamaModel,
  pollOllamaPull,
  startOllamaPull
} from '@/hermes'
import { useI18n } from '@/i18n'
import { Check, ChevronDown, Cpu, Download, Loader2, Trash2 } from '@/lib/icons'
import { cn } from '@/lib/utils'
import { notify, notifyError } from '@/store/notifications'
import type { OllamaModelsResponse, OllamaPullStatus } from '@/types/hermes'

import { CONTROL_TEXT } from './constants'
import { SettingsCategoryHeading } from './env-credentials'
import { Pill } from './primitives'

const PULL_POLL_INTERVAL_MS = 750

function formatBytes(bytes?: number): string {
  if (!bytes || bytes <= 0) {
    return ''
  }

  const gib = bytes / 1024 ** 3

  return gib >= 1 ? `${gib.toFixed(1)} GB` : `${Math.round(bytes / 1024 ** 2)} MB`
}

function formatContext(tokens?: number): string {
  if (!tokens || tokens <= 0) {
    return ''
  }

  return tokens >= 1024 ? `${Math.round(tokens / 1024)}k` : String(tokens)
}

/**
 * Local Ollama server card for the Providers page. Same row language as the
 * OAuth provider cards, but the connection kind is reachability rather than
 * a credential: the status tag shows "Running · N models" or a start-the-
 * server hint. Expanding a running server reveals model management —
 * installed models (size, delete, warm-up), loaded models (VRAM, context),
 * curated pull recommendations, and free-form pull.
 */
export function OllamaProviderCard() {
  const { t } = useI18n()
  const copy = t.settings.ollama
  const [data, setData] = useState<null | OllamaModelsResponse>(null)
  const [expanded, setExpanded] = useState(false)
  const [pull, setPull] = useState<null | OllamaPullStatus>(null)
  const [pullModel, setPullModel] = useState('')
  const [busyModel, setBusyModel] = useState<null | string>(null)
  const pollTimer = useRef<null | ReturnType<typeof setTimeout>>(null)

  const refresh = useCallback(async () => {
    try {
      setData(await getOllamaModels())
    } catch {
      setData(null)
    }
  }, [])

  useEffect(() => {
    void refresh()

    return () => {
      if (pollTimer.current) {
        clearTimeout(pollTimer.current)
      }
    }
  }, [refresh])

  // While the server is down (or detection failed), poll so the card flips
  // to "Running" by itself when the user starts Ollama — the status endpoint
  // answers in ~20ms, so this is cheap. Stops as soon as it's reachable.
  const reachableNow = Boolean(data?.reachable)

  useEffect(() => {
    if (reachableNow) {
      return
    }

    const timer = setInterval(() => void refresh(), 5_000)

    return () => clearInterval(timer)
  }, [reachableNow, refresh])

  const pollUntilDone = useCallback(
    (jobId: string) => {
      const tick = async () => {
        let status: OllamaPullStatus

        try {
          status = await pollOllamaPull(jobId)
        } catch (err) {
          setPull(null)
          notifyError(err, copy.pullFailed)

          return
        }

        setPull(status)

        if (status.status === 'pulling') {
          pollTimer.current = setTimeout(() => void tick(), PULL_POLL_INTERVAL_MS)

          return
        }

        if (status.status === 'done') {
          notify({ kind: 'success', title: copy.pullDone(status.model), message: '' })
          setPull(null)
          setPullModel('')
          void refresh()
        } else {
          notifyError(new Error(status.error_message || status.detail || 'pull failed'), copy.pullFailed)
          setPull(null)
        }
      }

      void tick()
    },
    [copy, refresh]
  )

  const beginPull = useCallback(
    async (model: string) => {
      const name = model.trim()

      if (!name || pull) {
        return
      }

      try {
        const { job_id } = await startOllamaPull(name)

        setPull({ job_id, model: name, status: 'pulling', detail: 'starting' })
        pollUntilDone(job_id)
      } catch (err) {
        notifyError(err, copy.pullFailed)
      }
    },
    [copy.pullFailed, pollUntilDone, pull]
  )

  const removeModel = useCallback(
    async (model: string) => {
      setBusyModel(model)

      try {
        const result = await deleteOllamaModel(model)

        if (!result.ok) {
          notifyError(new Error(result.message), copy.deleteFailed)
        } else {
          void refresh()
        }
      } catch (err) {
        notifyError(err, copy.deleteFailed)
      } finally {
        setBusyModel(null)
      }
    },
    [copy.deleteFailed, refresh]
  )

  const warmModel = useCallback(
    async (model: string) => {
      setBusyModel(model)

      try {
        const result = await loadOllamaModel(model)

        if (!result.ok) {
          notifyError(new Error(result.message), copy.loadFailed)
        } else {
          void refresh()
        }
      } catch (err) {
        notifyError(err, copy.loadFailed)
      } finally {
        setBusyModel(null)
      }
    },
    [copy.loadFailed, refresh]
  )

  const reachable = Boolean(data?.reachable)
  const installedCount = data?.installed.length ?? 0
  const running = new Map((data?.running ?? []).map(r => [r.name, r]))

  const pullPercent =
    pull?.total_bytes && pull.completed_bytes !== undefined
      ? Math.min(100, Math.round((pull.completed_bytes / pull.total_bytes) * 100))
      : null

  // Detection still pending: render nothing rather than flashing the
  // not-running hint at every page open on machines without Ollama.
  if (data === null) {
    return null
  }

  return (
    <section className="mb-5 grid gap-2" data-slot="ollama-provider-card">
      <SettingsCategoryHeading icon={Cpu} title={copy.categoryTitle} />
      <div className="rounded-[6px] transition-colors">
        <RowButton
          className="group flex w-full items-center justify-between gap-3 rounded-[6px] px-3 py-2.5 text-left transition-colors hover:bg-(--ui-control-hover-background)"
          disabled={!reachable}
          onClick={() => setExpanded(open => !open)}
        >
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-[length:var(--conversation-text-font-size)] font-semibold">Ollama</span>
              {reachable ? (
                <span className="inline-flex items-center gap-1 bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
                  <Check className="size-3" />
                  {copy.running(installedCount)}
                </span>
              ) : null}
            </div>
            <p className="mt-1 text-xs leading-5 text-muted-foreground">
              {reachable ? copy.desc : copy.notRunning}
            </p>
          </div>
          {reachable && (
            <ChevronDown
              className={cn('size-4 shrink-0 text-muted-foreground transition group-hover:text-foreground', expanded && 'rotate-180')}
            />
          )}
        </RowButton>

        {reachable && expanded && data && (
          <div className="px-3 pb-2 pt-1">
            {data.kv_cache_advisory && (
        <p className="mb-2 rounded-sm bg-amber-500/10 px-2.5 py-1.5 text-xs leading-5 text-amber-700 dark:text-amber-400">
          {copy.kvCacheAdvisory(
            data.kv_cache_advisory.model,
            formatContext(data.kv_cache_advisory.loaded_context),
            formatContext(data.kv_cache_advisory.trained_context)
          )}
        </p>
      )}

      <div className="grid gap-1">
        {data.installed.map(model => {
          const live = running.get(model.name)
          const busy = busyModel === model.name

          const meta = [model.parameter_size, model.quantization, formatBytes(model.size_bytes)]
            .filter(Boolean)
            .join(' · ')

          return (
            <div
              className="flex items-center justify-between gap-3 rounded-[6px] px-3 py-2 transition-colors hover:bg-(--ui-control-hover-background)"
              key={model.name}
            >
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="truncate font-mono text-xs">{model.name}</span>
                  {live && (
                    <Pill tone="primary">
                      {copy.loaded}
                      {live.context_length ? ` · ${formatContext(live.context_length)}` : ''}
                      {live.size_vram_bytes ? ` · ${formatBytes(live.size_vram_bytes)} VRAM` : ''}
                    </Pill>
                  )}
                </div>
                {meta && <p className="mt-0.5 text-[0.68rem] text-muted-foreground">{meta}</p>}
              </div>
              <div className="flex shrink-0 items-center gap-1">
                {!live && (
                  <Button disabled={busy} onClick={() => void warmModel(model.name)} size="sm" variant="text">
                    {busy ? <Loader2 className="size-3.5 animate-spin" /> : copy.load}
                  </Button>
                )}
                <Button
                  aria-label={copy.deleteLabel(model.name)}
                  disabled={busy}
                  onClick={() => void removeModel(model.name)}
                  size="icon"
                  variant="ghost"
                >
                  <Trash2 className="size-3.5" />
                </Button>
              </div>
            </div>
          )
        })}
      </div>

      <div className="mt-3">
        <p className="mb-1.5 text-xs font-medium">{copy.getModels}</p>
        {pull ? (
          <div className="rounded-[6px] bg-primary/[0.06] px-3 py-2">
            <div className="flex items-center gap-2 text-xs">
              <Loader2 className="size-3.5 animate-spin text-primary" />
              <span className="font-mono">{pull.model}</span>
              <span className="text-muted-foreground">
                {pullPercent !== null ? `${pullPercent}%` : pull.detail || ''}
              </span>
            </div>
            {pullPercent !== null && (
              <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-primary/15">
                <div className="h-full bg-primary transition-all" style={{ width: `${pullPercent}%` }} />
              </div>
            )}
          </div>
        ) : (
          <>
            <div className="grid gap-1">
              {data.recommended.map(rec => (
                <div
                  className="flex items-center justify-between gap-3 rounded-[6px] px-3 py-1.5 transition-colors hover:bg-(--ui-control-hover-background)"
                  key={rec.model}
                >
                  <div className="min-w-0">
                    <span className="font-mono text-xs">{rec.model}</span>
                    <p className="mt-0.5 truncate text-[0.68rem] text-muted-foreground">{rec.description}</p>
                  </div>
                  <Button
                    className="shrink-0"
                    onClick={() => void beginPull(rec.model)}
                    size="sm"
                    variant="text"
                  >
                    <Download className="size-3.5" />
                    {copy.pull}
                  </Button>
                </div>
              ))}
            </div>
            <div className="mt-2 flex items-center gap-2">
              <Input
                className={cn('max-w-72 font-mono', CONTROL_TEXT)}
                onChange={event => setPullModel(event.target.value)}
                onKeyDown={event => {
                  if (event.key === 'Enter') {
                    void beginPull(pullModel)
                  }
                }}
                placeholder={copy.pullPlaceholder}
                value={pullModel}
              />
              <Button disabled={!pullModel.trim()} onClick={() => void beginPull(pullModel)} size="sm" variant="text">
                {copy.pull}
              </Button>
            </div>
          </>
        )}
      </div>
          </div>
        )}
      </div>
    </section>
  )
}
