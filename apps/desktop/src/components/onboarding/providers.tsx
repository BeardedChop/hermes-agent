import { useState } from 'react'

import { RowButton } from '@/components/ui/row-button'
import { useI18n } from '@/i18n'
import { Check, ChevronRight, Cpu, Loader2, Terminal } from '@/lib/icons'
import { cn } from '@/lib/utils'
import type { LocalServerInfo, OAuthProvider } from '@/types/hermes'

const PROVIDER_DISPLAY: Record<string, { order: number; title: string }> = {
  nous: { order: 0, title: 'Nous Portal' },
  'openai-codex': { order: 1, title: 'OpenAI OAuth (ChatGPT)' },
  'minimax-oauth': { order: 2, title: 'MiniMax' },
  'qwen-oauth': { order: 3, title: 'Qwen Code' },
  'xai-oauth': { order: 4, title: 'xAI Grok' },
  // Both Anthropic entries sit at the bottom: the API-key path first, then
  // the subscription OAuth path (only works with extra usage credits).
  anthropic: { order: 5, title: 'Anthropic API Key' },
  'claude-code': { order: 6, title: 'Anthropic OAuth: Required Extra Usage Credits to Use Subscription' }
}

const assetPath = (path: string) => `${import.meta.env.BASE_URL}${path.replace(/^\/+/, '')}`

export const providerTitle = (p: OAuthProvider) => PROVIDER_DISPLAY[p.id]?.title ?? p.name
const orderOf = (p: OAuthProvider) => PROVIDER_DISPLAY[p.id]?.order ?? 99

export const sortProviders = (providers: OAuthProvider[]) =>
  [...providers].sort((a, b) => orderOf(a) - orderOf(b) || a.name.localeCompare(b.name))

export function FeaturedProviderRow({
  onSelect,
  provider
}: {
  onSelect: (provider: OAuthProvider) => void
  provider: OAuthProvider
}) {
  const { t } = useI18n()
  const loggedIn = provider.status?.logged_in

  return (
    <button
      className="group relative flex w-full items-center justify-between gap-4 rounded-[8px] bg-primary/[0.06] px-3 py-2.5 text-left transition-colors hover:bg-primary/10"
      onClick={() => onSelect(provider)}
      type="button"
    >
      <span aria-hidden className="arc-border arc-reverse arc-nous" />
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <img alt="" className="size-5 shrink-0 rounded" src={assetPath('apple-touch-icon.png')} />
          <span className="text-[length:var(--conversation-text-font-size)] font-semibold">
            {providerTitle(provider)}
          </span>
          {loggedIn ? (
            <ConnectedTag />
          ) : (
            <span className="inline-flex items-center gap-1.5 bg-primary px-2 py-0.5 text-[0.64rem] font-semibold uppercase tracking-[0.16em] text-primary-foreground">
              <span aria-hidden="true" className="dither inline-block size-2 shrink-0" />
              {t.onboarding.recommended}
            </span>
          )}
        </div>
        <p className="mt-1 text-xs leading-5 text-muted-foreground">{t.onboarding.featuredPitch}</p>
      </div>
      <ChevronRight className="size-4 shrink-0 text-primary transition group-hover:translate-x-0.5" />
    </button>
  )
}

function ConnectedTag() {
  const { t } = useI18n()

  return (
    <span className="inline-flex items-center gap-1 bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
      <Check className="size-3" />
      {t.onboarding.connected}
    </span>
  )
}

const PROVIDER_ROW_CLASS =
  'group flex w-full items-center justify-between gap-3 rounded-[6px] px-3 py-2.5 text-left transition-colors hover:bg-(--ui-control-hover-background)'

export function KeyProviderRow({ onClick }: { onClick: () => void }) {
  const { t } = useI18n()

  return (
    <RowButton className={PROVIDER_ROW_CLASS} onClick={onClick}>
      <div className="min-w-0">
        <span className="text-[length:var(--conversation-text-font-size)] font-semibold">OpenRouter</span>
        <p className="mt-1 text-xs leading-5 text-muted-foreground">{t.onboarding.openRouterPitch}</p>
      </div>
      <ChevronRight className="size-4 text-muted-foreground transition group-hover:text-foreground" />
    </RowButton>
  )
}

export function ProviderRow({
  onSelect,
  provider
}: {
  onSelect: (provider: OAuthProvider) => void
  provider: OAuthProvider
}) {
  const { t } = useI18n()
  const loggedIn = provider.status?.logged_in
  const Trail = provider.flow === 'external' ? Terminal : ChevronRight

  return (
    <RowButton className={PROVIDER_ROW_CLASS} onClick={() => onSelect(provider)}>
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-[length:var(--conversation-text-font-size)] font-semibold">
            {providerTitle(provider)}
          </span>
          {loggedIn ? <ConnectedTag /> : null}
        </div>
        <p className="mt-1 text-xs leading-5 text-muted-foreground">{t.onboarding.flowSubtitles[provider.flow]}</p>
      </div>
      <Trail className="size-4 text-muted-foreground transition group-hover:text-foreground" />
    </RowButton>
  )
}

/**
 * A local model server found by /api/local-servers/detect (currently the
 * Ollama row; LM Studio detection reuses the shape later). Collapsed: a
 * provider row showing "detected · N models installed". Expanded: the
 * installed-model list, each row a one-click connect — no URL typing, no
 * blind first-model assignment.
 */
export function DetectedLocalServerRow({
  onConnect,
  server
}: {
  onConnect: (baseUrl: string, model: string) => Promise<{ ok: boolean; message?: string }>
  server: LocalServerInfo
}) {
  const { t } = useI18n()
  const copy = t.onboarding.detectedLocal
  const [expanded, setExpanded] = useState(false)
  const [busyModel, setBusyModel] = useState<null | string>(null)
  const [error, setError] = useState('')

  const connect = async (model: string) => {
    if (busyModel) {
      return
    }

    setBusyModel(model)
    setError('')
    const result = await onConnect(server.base_url, model)

    if (!result.ok) {
      setError(result.message || copy.connectFailed)
      setBusyModel(null)
    }
    // On success the overlay unmounts via completeDesktopOnboarding().
  }

  return (
    <div className="rounded-[6px] transition-colors">
      <RowButton className={PROVIDER_ROW_CLASS} onClick={() => setExpanded(open => !open)}>
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <Cpu className="size-4 shrink-0 text-primary" />
            <span className="text-[length:var(--conversation-text-font-size)] font-semibold">Ollama</span>
            <span className="inline-flex items-center gap-1 bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
              <Check className="size-3" />
              {copy.detected}
            </span>
          </div>
          <p className="mt-1 text-xs leading-5 text-muted-foreground">{copy.modelsInstalled(server.models.length)}</p>
        </div>
        <ChevronRight
          className={cn('size-4 text-muted-foreground transition group-hover:text-foreground', expanded && 'rotate-90')}
        />
      </RowButton>
      {expanded ? (
        <div className="grid gap-0.5 px-3 pb-2">
          {server.models.map(model => (
            <RowButton
              className="group flex w-full items-center justify-between gap-3 rounded-[6px] px-3 py-1.5 text-left font-mono text-xs transition-colors hover:bg-(--ui-control-hover-background)"
              disabled={busyModel !== null}
              key={model}
              onClick={() => void connect(model)}
            >
              <span className="truncate">{model}</span>
              {busyModel === model ? (
                <Loader2 className="size-3.5 shrink-0 animate-spin text-muted-foreground" />
              ) : (
                <span className="shrink-0 text-[0.64rem] uppercase tracking-wide text-muted-foreground opacity-0 transition group-hover:opacity-100">
                  {copy.use}
                </span>
              )}
            </RowButton>
          ))}
          {error ? <p className="px-3 pt-1 text-xs leading-5 text-destructive">{error}</p> : null}
        </div>
      ) : null}
    </div>
  )
}
