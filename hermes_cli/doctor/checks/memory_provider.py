"""Memory provider checks."""

from __future__ import annotations

from hermes_cli.doctor._registry import register


@register("Memory Provider", "memory-provider", priority=10)
def check_memory_provider(report):
    from hermes_cli.doctor import HERMES_HOME

    provider = ""
    import yaml as _yaml
    cfg_path = HERMES_HOME / "config.yaml"
    if cfg_path.exists():
        with open(cfg_path, encoding="utf-8") as f:
            raw = _yaml.safe_load(f) or {}
        provider = (raw.get("memory") or {}).get("provider", "")

    if not provider:
        report.ok("Built-in memory active", "(no external provider configured — this is fine)")
    elif provider == "honcho":
        _check_honcho(report)
    elif provider == "mem0":
        _check_mem0(report)
    else:
        _check_generic(report, provider)


def _check_honcho(report):
    from plugins.memory.honcho.client import HonchoClientConfig, resolve_config_path
    hcfg = HonchoClientConfig.from_global_config()
    cfg_path = resolve_config_path()

    if not cfg_path.exists():
        if hcfg.api_key or hcfg.base_url:
            report.ok("Honcho configured via environment variables",
                      f"config file {cfg_path} not found, using HONCHO_API_KEY env var")
        else:
            report.warn("Honcho config not found", "run: hermes memory setup")
    elif not hcfg.enabled:
        report.info(f"Honcho disabled (set enabled: true in {cfg_path} to activate)")
    elif not (hcfg.api_key or hcfg.base_url):
        report.fail("Honcho API key or base URL not set", "run: hermes memory setup",
                    fix="No Honcho API key — run 'hermes memory setup'")
    else:
        from plugins.memory.honcho.client import get_honcho_client, reset_honcho_client
        reset_honcho_client()
        get_honcho_client(hcfg)
        report.ok("Honcho connected",
                  f"workspace={hcfg.workspace_id} mode={hcfg.recall_mode} freq={hcfg.write_frequency}")


def _check_mem0(report):
    from plugins.memory.mem0 import _load_config as _lc
    cfg = _lc()
    if cfg.get("api_key"):
        report.ok("Mem0 API key configured")
        report.info(f"user_id={cfg.get('user_id', '?')}  agent_id={cfg.get('agent_id', '?')}")
    else:
        report.fail("Mem0 API key not set", "(set MEM0_API_KEY in .env or run hermes memory setup)",
                    fix="Mem0 is set as memory provider but API key is missing")


def _check_generic(report, provider_name):
    from plugins.memory import load_memory_provider
    p = load_memory_provider(provider_name)
    if p and p.is_available():
        report.ok(f"{provider_name} provider active")
    elif p:
        report.warn(f"{provider_name} configured but not available", "run: hermes memory status")
    else:
        report.warn(f"{provider_name} plugin not found", "run: hermes memory setup")
