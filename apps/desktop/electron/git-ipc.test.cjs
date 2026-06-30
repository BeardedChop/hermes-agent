'use strict'

const assert = require('node:assert/strict')
const test = require('node:test')

const { GIT_IPC_CHANNELS, registerGitIpc } = require('./git-ipc.cjs')

function fakeIpcMain() {
  const handlers = new Map()

  return {
    handlers,
    handle(channel, handler) {
      handlers.set(channel, handler)
    }
  }
}

test('registerGitIpc wires every advertised git channel exactly once', () => {
  const ipcMain = fakeIpcMain()

  registerGitIpc({
    ipcMain,
    resolveGitBinary: () => 'git',
    resolveGhBinary: () => 'gh'
  })

  assert.deepEqual([...ipcMain.handlers.keys()].sort(), [...GIT_IPC_CHANNELS].sort())

  for (const channel of GIT_IPC_CHANNELS) {
    assert.equal(typeof ipcMain.handlers.get(channel), 'function', `${channel} should register a handler`)
  }
})

test('registerGitIpc delegates worktreeList to the git-worktree-ops module', async () => {
  const ipcMain = fakeIpcMain()
  const calls = []

  // Stub the git binary resolver so we can confirm the handler threads it into
  // the ops layer without shelling out to a real git.
  registerGitIpc({
    ipcMain,
    resolveGitBinary: () => {
      calls.push('git')

      return 'git'
    },
    resolveGhBinary: () => 'gh'
  })

  const worktreeList = ipcMain.handlers.get('hermes:git:worktreeList')
  // The resolver is consulted synchronously to build the ops call; whatever the
  // ops layer then does with a non-repo path is irrelevant to the wiring.
  try {
    await worktreeList({}, '/definitely/not/a/repo')
  } catch {
    // ops layer may reject on a bad path — not what this test asserts.
  }

  assert.deepEqual(calls, ['git'])
})
