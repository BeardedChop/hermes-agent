/**
 * Remote tree-sitter grammar registration (syntax-highlighting language
 * expansion). Grammars are NOT vendored — they're declared as remote URLs in
 * parsers.manifest.json and fetched+cached by OpenTUI on first use. Layers:
 *   1. config: every manifest grammar builds a well-formed config — a release
 *      `.wasm` URL + a highlights `.scm` URL (both https).
 *   2. resolution: core's filetype maps route our curated extensions/fence
 *      labels to the registered filetype ids.
 * Actual fetch + visual color is live-smoke territory (network + async settle —
 * see codeBlock.tsx); these tests pin the wiring that makes it possible without
 * hitting the network.
 */
import { extToFiletype, infoStringToFiletype, pathToFiletype } from '@opentui/core'
import { describe, expect, test } from 'vitest'

import { parserCacheDir, registerRemoteParsers, remoteParsers } from '../boundary/parsers.ts'

const EXPECTED = ['python', 'rust', 'go', 'bash', 'json', 'c', 'html', 'css', 'yaml', 'toml']

describe('remote grammar configs', () => {
  test('all 10 curated grammars build configs from the manifest', () => {
    const configs = remoteParsers()
    expect(configs.map(c => c.filetype).sort()).toEqual([...EXPECTED].sort())
  })

  test('each config carries an https .wasm URL and a non-empty .scm URL', () => {
    for (const config of remoteParsers()) {
      expect(config.wasm, config.filetype).toMatch(/^https:\/\/.+\.wasm$/)
      const scm = config.queries.highlights[0]!
      expect(scm.startsWith('https://'), config.filetype).toBe(true)
      expect(scm.endsWith('.scm'), config.filetype).toBe(true)
    }
  })

  test('registerRemoteParsers registers and reports the full set', () => {
    const registered = registerRemoteParsers()
    expect(registered.map(r => r.filetype).sort()).toEqual([...EXPECTED].sort())
  })

  test('parserCacheDir reflects HERMES_TUI_PARSER_CACHE (undefined when unset)', () => {
    const prev = process.env.HERMES_TUI_PARSER_CACHE
    try {
      delete process.env.HERMES_TUI_PARSER_CACHE
      expect(parserCacheDir()).toBeUndefined()
      process.env.HERMES_TUI_PARSER_CACHE = '/tmp/hermes-parser-cache'
      expect(parserCacheDir()).toBe('/tmp/hermes-parser-cache')
      process.env.HERMES_TUI_PARSER_CACHE = '   '
      expect(parserCacheDir()).toBeUndefined()
    } finally {
      if (prev === undefined) delete process.env.HERMES_TUI_PARSER_CACHE
      else process.env.HERMES_TUI_PARSER_CACHE = prev
    }
  })
})

describe('filetype routing into the registered ids', () => {
  test('tool-body path extensions resolve to curated filetypes', () => {
    expect(pathToFiletype('a/b/script.py')).toBe('python')
    expect(pathToFiletype('src/main.rs')).toBe('rust')
    expect(pathToFiletype('cmd/main.go')).toBe('go')
    expect(pathToFiletype('run.sh')).toBe('bash')
    expect(pathToFiletype('conf.yaml')).toBe('yaml')
    expect(pathToFiletype('conf.yml')).toBe('yaml')
    expect(pathToFiletype('Cargo.toml')).toBe('toml')
    expect(pathToFiletype('lib.c')).toBe('c')
    expect(pathToFiletype('lib.h')).toBe('c')
    expect(pathToFiletype('index.html')).toBe('html')
    expect(pathToFiletype('style.css')).toBe('css')
    expect(pathToFiletype('package.json')).toBe('json')
  })

  test('markdown fence labels resolve to curated filetypes (3b — injections)', () => {
    expect(infoStringToFiletype('python')).toBe('python')
    expect(infoStringToFiletype('py')).toBe('python')
    expect(infoStringToFiletype('rust')).toBe('rust')
    expect(infoStringToFiletype('sh')).toBe('bash')
    expect(infoStringToFiletype('yaml title=x.yml')).toBe('yaml')
    expect(extToFiletype('zsh')).toBe('bash')
  })
})
