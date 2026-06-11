# Platform Support Tiers — Implementation Plan

## Goal

Formalize Hermes Agent's platform support into three tiers, document them in the repo and docs, and deprecate removed platforms (pip/PyPI, Homebrew formula) with a clear migration path.

---

## Platform Support Tiers

### Explicitly supported — guaranteed to work, first-party installers only

| Platform | Installer |
|----------|-----------|
| Linux x86_64 / arm64 | `curl \| bash` installer, Docker image |
| Latest Debian, Ubuntu, Fedora, Windows WSL | `curl \| bash` installer |
| Official Docker image | `docker pull` |
| macOS arm64 | Desktop app installer, `curl \| bash` installer |
| Windows x86_64 / arm64 | Desktop app installer, PowerShell installer |

### Best-effort — PRs accepted for fixes, but Nous won't prioritize them, nor will we accept packaging-specific code in the repo

- Termux / Android
- AUR packaging
- Homebrew packaging
- Nix packaging (flake + NixOS module stay in-tree and maintained; packaging bugs outside core nix support are best-effort)

### Explicitly unsupported — no PRs for support will be accepted

- macOS x86_64
- Packaging via pip / PyPI
- FreeBSD

---

## Where the tier information lives

### In the repo (for agents and contributors)

| File | What to add |
|------|-------------|
| `AGENTS.md` | New `## Platform Support` section with the tier table and a link to the docs reference page. This is the canonical in-repo source — agents and contributors read it first. |
| `CONTRIBUTING.md` | Update the "Contribution Priorities" section (currently lines 8–17) to reference the tiers. Replace the generic "Cross-platform compatibility" bullet with explicit tier-aware language: PRs for best-effort platforms are welcome but won't block releases; PRs for unsupported platforms will be closed. |

### In the docs (for users)

| File | What to add |
|------|-------------|
| `website/docs/reference/platform-support.md` (new) | The canonical user-facing reference. Full tier breakdown with nuance, migration instructions for each deprecated path, and a support policy summary. Other pages link here. |
| `website/docs/getting-started/installation.md` | Add a prominent tier summary (table or callout) near the top, before the install commands. Remove the pip install row from the install layout table. Add a "Migrating from pip" subsection. |
| `website/docs/getting-started/updating.md` | Replace the "pip installs" update section with a deprecation notice linking to the platform-support page. |
| `website/docs/getting-started/termux.md` | Add a best-effort support banner at the top. |
| `website/docs/getting-started/nix-setup.md` | Add a note clarifying that the nix flake + NixOS module are maintained in-tree but nix-specific packaging bugs are best-effort. |

### What does NOT change

- `flake.nix`, `nix/`, Dockerfile — these are deployment methods, not just packaging. They stay.
- `scripts/install.sh` termux detection — already works, no reason to break it.
- `constraints-termux.txt` and `[termux]`/`[termux-all]` extras in pyproject.toml — still needed for best-effort users.

---

## Deprecating removed platforms

### 1. pip / PyPI

**Step 1: Publish one final version to PyPI**

- Update the package `description` in `pyproject.toml` to include a deprecation prefix:
  ```
  ⚠️ DEPRECATED: pip/PyPI installs are discontinued. See https://hermes-agent.nousresearch.com/ for supported install methods.
  ```
- Bump the version (next semver, e.g. `0.17.0`)
- Cut the release through the existing pipeline (`scripts/release.py` → tag push → `upload_to_pypi.yml`)
- After that release ships, **disable `upload_to_pypi.yml`**: add `if: false` to the job definitions and a comment explaining why

**Step 2: Add runtime deprecation notices**

Every touchpoint where Hermes detects a pip install must surface a clear deprecation warning. The message should be consistent across all surfaces:

> ⚠️ pip/PyPI installs are discontinued and no longer receive updates. Switch to a supported install method: https://hermes-agent.nousresearch.com/

In `hermes_cli/`:

| Location | Change |
|----------|--------|
| `config.py` — `detect_install_method()` returns `"pip"` | Keep returning `"pip"` (detection still works, needed so existing installs see the deprecation message) |
| `config.py` — `cmd_update` pip path | Replace the `uv pip install --upgrade hermes-agent` command with the deprecation message above. Do not attempt the upgrade — just print the message and exit. |
| `banner.py` — existing `detect_install_method() == "pip"` check | Add a deprecation line to the startup banner for pip installs |
| `main.py` — `hermes doctor` | Print the deprecation warning when `detect_install_method() == "pip"`, with an additional line: "Migrate with: curl -fsSL https://hermes-agent.nousresearch.com/install.sh \| bash" |

**Step 3: Update the docs**

- `website/docs/getting-started/installation.md`: remove the pip install row from the install layout table; add a deprecation callout box; add a brief "Migrating from pip" section
- `website/docs/getting-started/updating.md`: replace the "pip installs" section with a deprecation notice + link

**Step 4: Clean up pyproject.toml and enforce build failure (after the final release)**

- Add a comment at the top of `[project]` noting that PyPI publishing is discontinued
- Remove `[project.scripts]` entries — they're only needed for pip's `console_scripts` entry points; git/docker/nix all use their own launchers
- Keep `[build-system]`, `[project.optional-dependencies]`, and `[tool.setuptools]` sections — they're used by nix build and local dev setup (like termux), not just pip
- Remove `hermes_agent.egg-info/` from tracking
- **Enforce wheel build failure**: replace any remaining `setup.py` with a minimal stub that explicitly raises a `RuntimeError("pip/wheel builds are discontinued. Please use curl install, docker, or nix. See https://hermes-agent.nousresearch.com/")`. This prevents accidental silent fallback builds.
- **Standardize on uv**: update all remaining local dev/build documentation, scripts, and comments to explicitly use `uv pip` instead of plain `pip`.

**Step 5: Rip out `ensurepip` and standardize entirely on `uv`**

Since the `curl | bash` installer and all supported environments guarantee a working `uv` binary, remove all legacy `ensurepip` bootstrapping and plain `pip` fallback logic across the codebase. Any remaining local dependency provisioning (e.g., in dev setups, update recovery, or tool environments like Modal) must strictly use `uv pip`. This eliminates race conditions, partial installs, and state confusion from legacy pip bootstrapping.
- Print a hard deprecation message instead of attempting any `pip install` commands in `config.py` / `main.py` update paths.
- `is_uv_tool_install()` detection can stay (it's used internally to differentiate from source/nix/docker builds).

### 2. Homebrew

**Step 1: Deprecate the formula**

- In `packaging/homebrew/hermes-agent.rb`, add Homebrew's official deprecation:
  ```ruby
  deprecate! because: "is discontinued upstream. See https://hermes-agent.nousresearch.com/ for supported install methods."
  ```
- Bump the formula `url`/`version`/`sha256` one final time to match the last release

**Step 2: Add runtime deprecation notices**

Every touchpoint where Hermes detects a Homebrew install must surface a clear deprecation warning. The message should be consistent across all surfaces:

> ⚠️ Homebrew installs are discontinued and no longer receive updates. Switch to a supported install method: https://hermes-agent.nousresearch.com/

In `hermes_cli/`:

| Location | Change |
|----------|--------|
| `config.py` — `get_managed_update_command()` | Return the deprecation message above instead of `"brew upgrade hermes-agent"`. Do not suggest running brew upgrade. |
| `config.py` — `format_managed_message()` | Prepend the deprecation notice before any Homebrew-specific managed-install messages. |
| `banner.py` | Add a deprecation line to the startup banner when `get_managed_system() == "Homebrew"`. |
| `main.py` — `hermes doctor` | Print the deprecation warning when `detect_install_method() == "homebrew"`, with an additional line: "Migrate with: curl -fsSL https://hermes-agent.nousresearch.com/install.sh \| bash" |

**Step 3: Mark the formula as frozen**

- Add a comment at the top of `hermes-agent.rb` saying it's frozen and won't receive further updates
- Update `packaging/homebrew/README.md` to say the formula is deprecated
- Keep the directory in-tree as a reference — don't delete it

### 3. AUR

- No in-tree code. Purely a social/docs change.
- Add a note in `website/docs/reference/platform-support.md` saying AUR packaging is community-maintained and best-effort.
- No code changes needed.

### 4. Nix (stays in-tree, boundary clarified)

- `flake.nix` and `nix/` stay in-tree and maintained — they're a deployment method, not just packaging
- Add a comment in `flake.nix` and `nix/packages.nix` clarifying that nix-specific packaging bugs (e.g. a new dependency that doesn't build under nix) are best-effort: PRs accepted, but won't block releases
- The flake's `systems` list already excludes `x86_64-darwin` (only `x86_64-linux`, `aarch64-linux`, `aarch64-darwin`) — that's correct for the new tiers, no change needed

### 5. Termux

- Add a best-effort support banner to `website/docs/getting-started/termux.md`
- `constraints-termux.txt`, `[termux]`/`[termux-all]` extras, and `scripts/install.sh` termux detection all stay
- Termux-specific bugs won't block releases

### 6. macOS x86_64

- Add a runtime warning: if `platform.machine() == 'x86_64'` and `sys.platform == 'darwin'`, print a one-time deprecation notice in `hermes doctor` saying the platform is unsupported
- Don't actively break anything — just set expectations

---

## Execution order

1. Add `## Platform Support` section to `AGENTS.md`
2. Create `website/docs/reference/platform-support.md`
3. Update `CONTRIBUTING.md` to reference the tiers
4. Update `website/docs/getting-started/installation.md` with tier info and pip deprecation
5. Update `website/docs/getting-started/updating.md` with pip deprecation
6. Add runtime deprecation notices in `hermes_cli/config.py`, `hermes_cli/banner.py`, `hermes_cli/main.py` for **both pip and Homebrew** installs
7. Update `packaging/homebrew/hermes-agent.rb` with `deprecate!`
8. Cut the final PyPI release with deprecation description in pyproject.toml
9. After the release: disable `upload_to_pypi.yml`, replace pip update command with deprecation message, add deprecation comments to pyproject.toml, remove `[project.scripts]`
10. Rip out all `ensurepip` and legacy `pip` fallback logic across `hermes_cli/main.py`, `hermes_cli/tools_config.py`, `tools/lazy_deps.py`, `tools/environments/modal.py`, and install scripts, standardizing exclusively on `uv pip`.
11. Add termux best-effort banner to termux docs
12. Add macOS x86_64 unsupported warning to `hermes doctor`

---

## Files touched (summary)

| File | Action |
|------|--------|
| `AGENTS.md` | Add platform support section |
| `CONTRIBUTING.md` | Update contribution priorities with tier awareness |
| `website/docs/reference/platform-support.md` | Create — canonical user-facing tier reference |
| `website/docs/getting-started/installation.md` | Add tier summary, pip deprecation, migration section |
| `website/docs/getting-started/updating.md` | Replace pip section with deprecation |
| `website/docs/getting-started/termux.md` | Add best-effort banner |
| `website/docs/getting-started/nix-setup.md` | Add best-effort boundary note |
| `hermes_cli/config.py` | Deprecation messages for pip update + Homebrew update command |
| `hermes_cli/banner.py` | Deprecation line for pip installs + Homebrew installs |
| `hermes_cli/main.py` | `hermes doctor` pip + Homebrew deprecation warnings, macOS x86_64 warning |
| `hermes_cli/tools_config.py` | Rip out `ensurepip` fallback, standardize on `uv pip` for local provisioning |
| `tools/lazy_deps.py` | Rip out `ensurepip` fallback, standardize on `uv pip` for local provisioning |
| `tools/environments/modal.py` | Rip out `ensurepip` fallback, standardize on `uv pip` for local provisioning |
| `scripts/install.ps1` | Rip out `ensurepip` fallback, standardize on `uv pip` for local provisioning |
| `packaging/homebrew/hermes-agent.rb` | Add `deprecate!`, freeze comment |
| `packaging/homebrew/README.md` | Mark as deprecated |
| `pyproject.toml` | Deprecation description, later: remove `[project.scripts]`, add comments |
| `.github/workflows/upload_to_pypi.yml` | Disable after final release (`if: false`) |

---

## Full removal (future, after deprecation period)

After a suitable deprecation period (suggested: 2–3 minor releases, or ~6 months), fully remove the deprecated code and packaging infrastructure. This is a separate PR to avoid breaking existing installs prematurely.

### pip / PyPI — full removal

| Item | Action |
|------|--------|
| `hermes_cli/config.py` — `detect_install_method()` | Remove the `"pip"` return path entirely. If no stamp, no managed marker, and no `.git`, treat it as an unknown install rather than defaulting to pip. |
| `hermes_cli/config.py` — `cmd_update` pip path | Remove the pip-specific update branch. |
| `hermes_cli/config.py` — `_MANAGED_SYSTEM_NAMES` | Remove `"brew"` and `"homebrew"` entries. |
| `hermes_cli/config.py` — `get_managed_update_command()` | Remove the `Homebrew` branch. |
| `hermes_cli/config.py` — `format_managed_message()` | Remove the `Homebrew` branch. |
| `hermes_cli/banner.py` | Remove pip and Homebrew deprecation lines from the banner. |
| `hermes_cli/main.py` — `hermes doctor` | Remove pip and Homebrew deprecation warnings. |
| `pyproject.toml` — `[project.optional-dependencies]` | Keep the `termux` and `termux-all` extras (local source builds via uv/nix still use them for best-effort support). Remove the `pty` and `vision` back-compat aliases (they were legacy pip-only install targets). |
| `pyproject.toml` — `[project]` | Remove `description` deprecation prefix. |
| `setup.py` | Replace with a minimal stub that raises a `RuntimeError` explaining pip/wheel builds are discontinued (prevents silent fallback builds). Move any skills/optional-skills data-file logic into the nix build if nix still needs it. |
| `hermes_agent.egg-info/` | Delete entirely. |
| `.github/workflows/upload_to_pypi.yml` | Delete the workflow file. |
| `constraints-termux.txt` | Remove — termux users build from source and can maintain their own constraints. |
| `scripts/install_psutil_android.py` | Remove — termux-specific pip hack. |
| `tests/test_packaging_metadata.py` | Remove pip-specific assertions (wheel/sdist packaging tests). |
| `tests/test_termux_all_extra_compat.py` | Remove. |
| `tests/test_wheel_locales_e2e.py` | Remove — tests pip wheel install behavior. |
| `tests/hermes_cli/test_cmd_update.py` — pip regression tests | Remove the `"pip"` parameterized test cases. |
| `tests/hermes_cli/test_cmd_update_docker.py` — pip test case | Remove the `test_cmd_update_check_on_pip_install_still_uses_pypi` test. |

### Homebrew — full removal

| Item | Action |
|------|--------|
| `packaging/homebrew/` | Delete the entire directory (formula + README). The formula is frozen and will never be updated again — no reason to keep it. |
| `hermes_cli/config.py` — `_MANAGED_SYSTEM_NAMES` | Remove `"brew"` and `"homebrew"` entries (listed above, duplicate for clarity). |
| `pyproject.toml` — `[project.optional-dependencies]` comments | Remove Homebrew-specific comments (e.g. the `voice` extra comment about "source-build packagers like Homebrew"). |
| `pyproject.toml` — `[all]` policy comment | Remove the "packagers (Nix, AUR, Homebrew)" references, update to just "packagers (Nix, AUR)". |

### macOS x86_64 — full removal

| Item | Action |
|------|--------|
| `hermes_cli/main.py` — `hermes doctor` | Remove the x86_64 macOS warning (or escalate to a hard error that refuses to start). |
| `flake.nix` — `systems` | Already correct (no `x86_64-darwin`). No change needed. |

### General cleanup

- **Rip out all `ensurepip` and `pip` fallback logic**: Search the codebase for `ensurepip`, `-m pip`, and `pip install`. Update `hermes_cli/main.py`, `hermes_cli/tools_config.py`, `tools/lazy_deps.py`, `tools/environments/modal.py`, and install scripts to exclusively use `uv pip` for *any* remaining local environment provisioning.
- Search the codebase for any remaining references to `"pip"`, `"homebrew"`, `"brew"`, `PyPI`, `pypi.org`, `upload_to_pypi`, `egg-info`, and `setup.py` — remove or update them.
- Run the full test suite to confirm nothing is broken by the removals.
- Update `AGENTS.md` and `website/docs/reference/platform-support.md` to remove any "deprecated" language and state the removed paths as simply unsupported (no longer "deprecated and still detected" — just gone).
