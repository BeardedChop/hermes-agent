# Platform Support

Hermes Agent is designed to run reliably across a variety of environments. To ensure maintainability and a high-quality user experience, we formalize our platform support into three distinct tiers. 

## Support Tiers

### 1. Explicitly Supported (Guaranteed)
These platforms are fully supported, tested, and guaranteed to work. We provide first-party installers and prioritize fixes for these environments.

| Platform | Supported Installers |
|----------|----------------------|
| Linux (x86_64 / arm64) | `curl \| bash` installer, Docker image |
| Latest Debian, Ubuntu, Fedora | `curl \| bash` installer |
| Official Docker image | `docker pull` |
| macOS (arm64 / Apple Silicon) | Desktop app installer, `curl \| bash` installer |
| Windows (x86_64 / arm64) | Desktop app installer, PowerShell installer |

### 2. Best-Effort Support
We welcome community PRs for fixes on these platforms, and they generally work, but Nous will not prioritize them. We also do not accept packaging-specific code changes into the core repository for these platforms.

- **Termux / Android**: Community-supported. Best-effort fixes are welcome, but will not block Hermes releases.
- **AUR Packaging**: Community-maintained. 
- **Homebrew Packaging**: Deprecated. See [Migrating from Homebrew](#migrating-from-homebrew) below.
- **Nix Packaging**: The `flake.nix` and NixOS module are maintained in-tree as a primary deployment method. However, niche Nix-specific packaging bugs (e.g., a new dependency failing to build under Nix) are treated as best-effort.

### 3. Explicitly Unsupported
We do not accept PRs attempting to add or restore support for these platforms. 

- **macOS (x86_64 / Intel)**: No longer supported.
- **Packaging via pip / PyPI**: Deprecated and discontinued. See [Migrating from pip/PyPI](#migrating-from-pippypi) below.
- **FreeBSD**: Not supported.

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

*Note: Attempting to build a wheel or install via pip will now result in a clear error message directing you to these supported methods.*

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

- **Bug Reports**: We prioritize bug reports and feature requests originating from *Explicitly Supported* platforms. 
- **Pull Requests**: PRs targeting *Best-Effort* platforms are welcome but are reviewed on a community basis and will not block core releases. PRs targeting *Explicitly Unsupported* platforms will be closed.
- **Security Updates**: Security patches and critical fixes are guaranteed for *Explicitly Supported* installation methods only.

For questions or to discuss best-effort platform support, please reach out in our community channels!
