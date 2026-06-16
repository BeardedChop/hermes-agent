/**
 * Extra Tree-sitter grammar registration — the syntax-highlighting language
 * expansion (docs/plans/opentui-syntax-highlighting-languages.md).
 *
 * @opentui/core@0.4.x bundles only a handful of grammars (ts/js/markdown/
 * markdown_inline/zig); everything else renders plain text. The cure is the
 * public `addDefaultParsers()` API fed with REMOTE grammar URLs — OpenTUI's
 * TreeSitterClient fetches each `.wasm`/`.scm` lazily on first use of a
 * filetype and caches it under the client's `dataPath`. We do NOT vendor any
 * binaries (cf. opencode, which checks in zero `.wasm`/`.scm` and lets OpenTUI
 * fetch+cache). The grammar set + its URLs live in `parsers.manifest.json`.
 *
 * Cache location: `HERMES_TUI_PARSER_CACHE` (set by the Python launcher to
 * `~/.hermes/cache/opentui-parsers/`, profile-aware via get_hermes_home). When
 * unset (dev/demo/CI), we leave OpenTUI's default data path
 * (`$XDG_DATA_HOME/opentui` → `~/.local/share/opentui`) untouched.
 *
 * `setDataPath()` on the GLOBAL client must run BEFORE the client initializes
 * (it only mutates `options.dataPath` until init, then the worker boots with
 * it). `addDefaultParsers()` must run BEFORE the first `<code>`/`<markdown>`
 * mount (they grab the global client lazily and trigger init). The entry
 * imports + calls `registerRemoteParsers()` at module load, ahead of renderer
 * acquisition, so both orderings hold.
 *
 * Offline behavior: registration itself does NO network (it only declares the
 * URL configs). The fetch happens on first highlight of a given language; if it
 * fails (air-gapped / GitHub unreachable), OpenTUI degrades that filetype to
 * plain text — never a throw. A registration error likewise degrades the whole
 * extra set to plain text.
 */
import { getTreeSitterClient } from '@opentui/core'
import { addDefaultParsers } from '@opentui/core'

import manifest from './parsers.manifest.json'
import { getLog } from './log.ts'

interface ManifestParser {
  readonly filetype: string
  readonly aliases: readonly string[]
  readonly wasm: string
  readonly highlights: string
}

/** The registered parser configs (exported shape for tests/diagnostics). */
export interface RegisteredParser {
  filetype: string
  aliases?: string[]
  wasm: string
  queries: { highlights: string[] }
}

/** The cache dir for fetched grammar assets, or undefined to use OpenTUI's
 *  default ($XDG_DATA_HOME/opentui). The launcher sets this per-profile. */
export function parserCacheDir(): string | undefined {
  const dir = (process.env.HERMES_TUI_PARSER_CACHE ?? '').trim()
  return dir.length ? dir : undefined
}

/** Build the remote parser configs from the manifest. Pure — no network, no
 *  filesystem; just declares the URL configs OpenTUI fetches lazily. */
export function remoteParsers(): RegisteredParser[] {
  const configs: RegisteredParser[] = []
  for (const parser of (manifest as { parsers: ManifestParser[] }).parsers) {
    if (!parser.wasm || !parser.highlights) continue
    configs.push({
      filetype: parser.filetype,
      ...(parser.aliases.length ? { aliases: [...parser.aliases] } : {}),
      wasm: parser.wasm,
      queries: { highlights: [parser.highlights] }
    })
  }
  return configs
}

/** Point the global tree-sitter client's cache at our profile dir, then
 *  register the remote grammars with core's global default-parser list.
 *  Returns what was registered (empty on any failure — plain-text fallback). */
export function registerRemoteParsers(): RegisteredParser[] {
  try {
    const cache = parserCacheDir()
    if (cache) {
      // Must precede the client's lazy initialize() (first <code>/<markdown>
      // mount). Pre-init this only mutates options.dataPath; the returned
      // promise resolves immediately (no worker yet) so we don't await it.
      void getTreeSitterClient().setDataPath(cache)
    }
    const parsers = remoteParsers()
    if (!parsers.length) {
      getLog().warn('parsers', 'no remote tree-sitter grammars declared — extras render plain', {})
      return []
    }
    addDefaultParsers(parsers)
    return parsers
  } catch (cause) {
    getLog().warn('parsers', 'tree-sitter registration failed — extras render plain', {
      cause: String(cause)
    })
    return []
  }
}
