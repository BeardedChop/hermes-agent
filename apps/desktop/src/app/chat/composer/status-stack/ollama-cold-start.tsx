import { useStore } from '@nanostores/react'
import { useEffect, useState } from 'react'

import { GlyphSpinner } from '@/components/ui/glyph-spinner'
import { getOllamaModels } from '@/hermes'
import { useI18n } from '@/i18n'
import { $awaitingResponse, $currentModel, $currentProvider } from '@/store/session'

// Wait this long after a turn starts before concluding the silence is a cold
// model load (a warm model answers well inside it), then confirm against the
// server before showing anything.
const COLD_START_GRACE_MS = 4_000
const POLL_INTERVAL_MS = 2_000

/**
 * Cold-start detection for local Ollama models: returns the model name while
 * a turn has been awaiting its first token past the grace period and the
 * target model is not yet in the server's loaded list — i.e. Ollama is
 * reading weights into memory. Returns '' for non-Ollama providers and for
 * warm models (the loaded check keeps ordinary slow generations quiet).
 *
 * A hook rather than a self-hiding component so the status stack can count
 * it toward its own visibility (the stack collapses when every section is
 * empty).
 */
export function useOllamaColdStart(): string {
  const awaiting = useStore($awaitingResponse)
  const provider = useStore($currentProvider)
  const model = useStore($currentModel)
  const [loadingModel, setLoadingModel] = useState('')

  const active = awaiting && provider === 'ollama' && Boolean(model)

  useEffect(() => {
    if (!active) {
      setLoadingModel('')

      return
    }

    let cancelled = false
    let timer: ReturnType<typeof setTimeout>

    const check = async () => {
      try {
        const data = await getOllamaModels()

        if (cancelled) {
          return
        }

        const loaded = data.running.some(r => r.name === model || r.name.split(':', 1)[0] === model.split(':', 1)[0])

        // Loaded (or server unreachable — nothing useful to say): clear and
        // let the normal streaming UI take over.
        if (loaded || !data.reachable) {
          setLoadingModel('')

          return
        }

        setLoadingModel(model)
        timer = setTimeout(() => void check(), POLL_INTERVAL_MS)
      } catch {
        if (!cancelled) {
          setLoadingModel('')
        }
      }
    }

    timer = setTimeout(() => void check(), COLD_START_GRACE_MS)

    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [active, model])

  return active ? loadingModel : ''
}

export function OllamaColdStartRow({ model }: { model: string }) {
  const { t } = useI18n()

  return (
    <div className="flex items-center gap-2 px-3 py-1.5 text-xs text-muted-foreground" data-slot="ollama-cold-start">
      <GlyphSpinner className="opacity-70" spinner="braille" />
      <span>{t.statusStack.ollamaLoading(model)}</span>
    </div>
  )
}
