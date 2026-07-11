/**
 * Bridge parity contract (RFC docs/plans/2026-07-10-001 §2.1).
 *
 * The renderer runs against two bridge implementations: the Electron preload
 * (electron/preload.ts) and the web bridge (this directory). This test pins
 * the RELATION between them — not a snapshot of either:
 *
 *   every key the preload exposes  ⊆  web-implemented ∪ WEB_OMITTED_SURFACE
 *
 * with WEB_STUBBED_SURFACE / WEB_OMITTED_SURFACE required to stay accurate
 * (no stale entries, omissions really absent). Adding a method to preload.ts
 * without deciding its web story fails here — the failure message tells the
 * author exactly what decision is owed.
 *
 * The preload is imported with 'electron' mocked, so the object under test is
 * the REAL exposed bridge, not a copy of its key list.
 */
import { describe, expect, it, vi } from 'vitest'

import { createWebBridge, WEB_OMITTED_SURFACE, WEB_STUBBED_SURFACE } from './index'

const captured = vi.hoisted(() => ({ apis: {} as Record<string, Record<string, unknown>> }))

vi.mock('electron', () => ({
  contextBridge: {
    exposeInMainWorld: (name: string, api: Record<string, unknown>) => {
      captured.apis[name] = api
    }
  },
  ipcRenderer: {
    invoke: async () => undefined,
    on: () => {},
    removeListener: () => {},
    send: () => {}
  },
  webUtils: {
    getPathForFile: () => ''
  }
}))

// Side-effect import: runs exposeInMainWorld with the mocked contextBridge.
await import('../../electron/preload')

function preloadBridge(): Record<string, unknown> {
  const api = captured.apis.hermesDesktop

  if (!api) {
    throw new Error('preload.ts did not expose hermesDesktop — did the module shape change?')
  }

  return api
}

describe('web bridge parity with the Electron preload', () => {
  const preload = preloadBridge()
  const web = createWebBridge() as unknown as Record<string, unknown>

  it('both bridges declare their host marker', () => {
    expect(preload.host).toBe('electron')
    expect(web.host).toBe('web')
  })

  it('every preload key is web-implemented or a registered omission', () => {
    const undecided = Object.keys(preload).filter(key => !(key in web) && !(key in WEB_OMITTED_SURFACE))

    // A non-empty list means preload.ts gained surface whose web story nobody
    // decided. Implement it in createWebBridge(), stub it there (and register
    // the reason in WEB_STUBBED_SURFACE), or register a deliberate absence in
    // WEB_OMITTED_SURFACE.
    expect(undecided).toEqual([])
  })

  it('registered omissions are really absent from the web bridge', () => {
    const wronglyPresent = Object.keys(WEB_OMITTED_SURFACE).filter(key => key in web)

    expect(wronglyPresent).toEqual([])
  })

  it('registries carry no stale entries for surface the preload no longer has', () => {
    const staleOmissions = Object.keys(WEB_OMITTED_SURFACE).filter(key => !(key in preload))
    const staleStubs = Object.keys(WEB_STUBBED_SURFACE).filter(key => !(key in preload))

    expect(staleOmissions).toEqual([])
    expect(staleStubs).toEqual([])
  })

  it('registered stubs exist on the web bridge', () => {
    const missingStubs = Object.keys(WEB_STUBBED_SURFACE).filter(key => !(key in web))

    expect(missingStubs).toEqual([])
  })

  it('namespace objects present on both bridges expose the same methods', () => {
    const namespaces = Object.keys(preload).filter(
      key => typeof preload[key] === 'object' && preload[key] !== null && key in web
    )

    for (const namespace of namespaces) {
      const preloadKeys = Object.keys(preload[namespace] as object).sort()
      const webKeys = Object.keys(web[namespace] as object).sort()

      // Same relation one level down: a method added to a preload namespace
      // must appear on the web namespace too (implemented or inert).
      expect({ [namespace]: webKeys }).toEqual({ [namespace]: preloadKeys })
    }
  })
})
