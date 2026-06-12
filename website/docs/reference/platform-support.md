# Platform Support

Hermes Agent is designed to run reliably across a variety of environments. To ensure maintainability and a high-quality user experience, we formalize our platform support into three distinct tiers.

## Support Tiers

### 1. Explicitly Supported (Guaranteed)

These platforms are fully supported, tested, and guaranteed to work. We provide first-party installers and prioritize fixes for these environments.

| Platform                                              | Supported Installers                         |
| ----------------------------------------------------- | -------------------------------------------- |
| Linux (Debian, Ubuntu, Fedora, WSL2) (x86_64 / arm64) | `curl \| bash` installer                     |
| Official Docker image                                 | `docker pull`                                |
| macOS (Apple Silicon)                                 | Hermes Desktop App, `curl \| bash` installer |
| Windows (x86_64 / arm64)                              | Hermes Desktop App, PowerShell installer     |

### 2. Best-Effort Support

We welcome community PRs for fixes on these platforms, and they generally work, but Nous will not prioritize them.
We also generally do not accept packaging-specific code changes into the core repository for these platforms.

- **Termux / Android**: Community-supported.
- **AUR Packaging**: Community-supported.
- **Nix Packaging**: The `flake.nix` and NixOS module are maintained in-tree as a primary deployment method. However, niche Nix-specific packaging bugs (e.g., a new dependency failing to build under Nix) are treated as best-effort.

### 3. Explicitly Unsupported

We do not accept PRs attempting to add or restore support for these platforms.

- **macOS (x86_64 / Intel)**: No longer supported.
- **Packaging via Homebrew**: Deprecated. See [Migrating from Homebrew](#migrating-from-homebrew) below.
- **Packaging via pip / PyPI**: Deprecated and discontinued. See [Migrating from pip/PyPI](#migrating-from-pippypi) below.
- **FreeBSD**: Not supported.
- **Haiku**: Okay, maybe if you submit a working PR.

---

## Migration Guides

### Migrating from pip / PyPI

:::warning Deprecation Notice
**pip and PyPI installations are officially discontinued and no longer receive updates.**
:::

If you installed Hermes via `pip install hermes-agent`, please migrate to a supported installation method immediately. The recommended approach for most users is the universal installer script:

```bash
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
```

Alternatively, you can use:

- **Docker**: `docker pull nousresearch/hermes-agent` (or your configured registry)
- **Nix**: Use the official flake or NixOS module provided in the repository.

### Migrating from Homebrew

:::warning Deprecation Notice
**Homebrew installations are officially discontinued and no longer receive updates.**
:::

The Homebrew formula has been deprecated upstream. If you installed Hermes via `brew install hermes-agent`, please migrate to the universal installer script:

```bash
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
```

After installing via the supported method, you can safely remove the deprecated Homebrew formula:

```bash
brew uninstall hermes-agent
```

---

## Support Policy Summary

- **Bug Reports**: We prioritize bug reports and feature requests originating from _Explicitly Supported_ platforms.
- **Pull Requests**: PRs targeting _Best-Effort_ platforms are welcome but are reviewed on a community basis and will not block core releases. PRs targeting _Explicitly Unsupported_ platforms will be closed.
- **Security Updates**: Security patches and critical fixes are guaranteed for _Explicitly Supported_ installation methods only.

For questions or to discuss best-effort platform support, please reach out in our community channels!
