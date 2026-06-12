"""Configuration file checks."""

from __future__ import annotations

import os
import shutil

from hermes_cli.doctor._registry import register


_PROVIDER_ENV_HINTS = (
    "OPENROUTER_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "ANTHROPIC_TOKEN",
    "OPENAI_BASE_URL", "NOUS_API_KEY", "GLM_API_KEY", "ZAI_API_KEY", "Z_AI_API_KEY",
    "KIMI_API_KEY", "KIMI_CN_API_KEY", "GMI_API_KEY", "MINIMAX_API_KEY",
    "MINIMAX_CN_API_KEY", "KILOCODE_API_KEY", "DEEPSEEK_API_KEY", "DASHSCOPE_API_KEY",
    "HF_TOKEN", "OPENCODE_ZEN_API_KEY", "OPENCODE_GO_API_KEY", "XIAOMI_API_KEY",
    "TOKENHUB_API_KEY",
)


def _has_provider_env_config(content: str) -> bool:
    return any(key in content for key in _PROVIDER_ENV_HINTS)


@register("Configuration Files", "env-file", priority=10)
def check_env_file(report):
    from hermes_cli.doctor import HERMES_HOME, PROJECT_ROOT, _DHH

    env_path = HERMES_HOME / ".env"
    if env_path.exists():
        report.ok(f"{_DHH}/.env file exists")
        content = env_path.read_text(encoding="utf-8")
        if _has_provider_env_config(content):
            report.ok("API key or custom endpoint configured")
        else:
            report.warn(f"No API key found in {_DHH}/.env")
            report.add_issue("run 'hermes setup' to configure API keys")
    elif (PROJECT_ROOT / ".env").exists():
        report.ok(".env file exists (in project directory)")
    else:
        def _fix(r):
            env_path.parent.mkdir(parents=True, exist_ok=True)
            env_path.touch()
            try:
                os.chmod(str(env_path), 0o600)
            except OSError:
                pass
            r.ok(f"Created empty {_DHH}/.env")
            r.info("run 'hermes setup' to configure API keys")

        report.fail(
            f"{_DHH}/.env file missing",
            fix="run 'hermes setup' to create one",
            fix_fn=_fix,
        )


@register("Configuration Files", "config-yaml", priority=20)
def check_config_yaml(report):
    from hermes_cli.doctor import HERMES_HOME, PROJECT_ROOT, _DHH

    config_path = HERMES_HOME / "config.yaml"
    if not config_path.exists():
        fallback = PROJECT_ROOT / "cli-config.yaml"
        if fallback.exists():
            report.ok("cli-config.yaml exists (in project directory)")
            return

        def _fix(r):
            config_path.parent.mkdir(parents=True, exist_ok=True)
            example = PROJECT_ROOT / "cli-config.yaml.example"
            if example.exists():
                shutil.copy2(str(example), str(config_path))
                r.ok(f"Created {_DHH}/config.yaml from cli-config.yaml.example")
            else:
                from hermes_cli.config import DEFAULT_CONFIG, save_config
                save_config(DEFAULT_CONFIG)
                r.ok(f"Created {_DHH}/config.yaml from defaults")

        report.warn(
            "config.yaml not found",
            "(using defaults)",
        )
        report.add_issue(
            f"{_DHH}/config.yaml missing",
            fix_fn=_fix,
        )
        return

    report.ok(f"{_DHH}/config.yaml exists")
    _check_model_provider_config(report, config_path)


def _check_model_provider_config(report, config_path):
    import yaml as _yaml
    from hermes_cli.doctor import _DHH

    cfg = _yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    model_section = cfg.get("model") or {}
    provider_raw = (model_section.get("provider") or "").strip()
    provider = provider_raw.lower()
    default_model = (model_section.get("default") or model_section.get("model") or "").strip()

    known_providers: set[str] = set()
    _resolve_auth_provider = None
    _normalize_catalog_provider = None
    _resolve_provider_full = None

    try:
        from hermes_cli.auth import PROVIDER_REGISTRY, resolve_provider as _rap
        known_providers = set(PROVIDER_REGISTRY.keys()) | {"openrouter", "custom", "auto"}
        _resolve_auth_provider = _rap
    except Exception:
        pass

    try:
        from hermes_cli.providers import normalize_provider as _ncp, resolve_provider_full as _rpf
        _normalize_catalog_provider = _ncp
        _resolve_provider_full = _rpf
    except Exception:
        pass

    custom_providers = []
    try:
        from hermes_cli.config import get_compatible_custom_providers
        custom_providers = get_compatible_custom_providers(cfg) or []
    except Exception:
        pass

    user_providers = cfg.get("providers")
    if isinstance(user_providers, dict):
        known_providers.update(str(n).strip().lower() for n in user_providers if str(n).strip())
    for entry in custom_providers:
        if isinstance(entry, dict):
            n = str(entry.get("name") or "").strip()
            if n:
                known_providers.add("custom:" + n.lower().replace(" ", "-"))

    valid_ids = set(known_providers)
    if _normalize_catalog_provider:
        for kp in known_providers:
            try:
                valid_ids.add(_normalize_catalog_provider(kp))
            except Exception:
                pass

    accepted = {provider} if provider else set()
    runtime_provider = provider
    if provider and _resolve_auth_provider and provider not in {"auto", "custom"}:
        try:
            runtime_provider = _resolve_auth_provider(provider)
            accepted.add(runtime_provider)
        except Exception:
            pass

    catalog_provider = provider
    if provider and _resolve_provider_full and provider not in {"auto", "custom"}:
        pdef = _resolve_provider_full(provider, user_providers, custom_providers)
        catalog_provider = pdef.id if pdef is not None else None
        if catalog_provider:
            accepted.add(catalog_provider)

    if provider and provider != "auto":
        if catalog_provider is None or (known_providers and not (accepted & valid_ids)):
            known_list = ", ".join(sorted(known_providers)) if known_providers else "(unavailable)"
            report.fail(
                f"model.provider '{provider_raw}' is not a recognised provider",
                f"(known: {known_list})",
                fix=f"run 'hermes config set model.provider <valid_provider>' — valid: {known_list}",
            )

    policy_id = str(runtime_provider or catalog_provider or "").strip().lower()
    slug_ok_providers = {"openrouter", "auto", "kilocode", "opencode-zen", "huggingface", "lmstudio", "nous"}
    slug_ok = policy_id in slug_ok_providers or policy_id == "custom" or policy_id.startswith("custom:")
    if default_model and "/" in default_model and policy_id and not slug_ok:
        report.warn(
            f"model.default '{default_model}' uses a vendor/model slug but provider is '{provider_raw}'",
            "(vendor-prefixed slugs belong to aggregators like openrouter)",
        )
        report.add_issue(
            f"model.default '{default_model}' is vendor-prefixed for provider '{provider_raw}' — "
            "set model.provider to 'openrouter', or drop the vendor prefix"
        )

    if runtime_provider and runtime_provider not in ("auto", "custom"):
        if runtime_provider == "openrouter":
            from hermes_cli.config import get_env_value
            configured = bool(
                str(get_env_value("OPENROUTER_API_KEY") or "").strip()
                or str(get_env_value("OPENAI_API_KEY") or "").strip()
            )
        else:
            from hermes_cli.auth import PROVIDER_REGISTRY, get_auth_status
            pconfig = PROVIDER_REGISTRY.get(runtime_provider)
            configured = True
            if pconfig and getattr(pconfig, "auth_type", "") == "api_key":
                status = get_auth_status(runtime_provider) or {}
                configured = bool(status.get("configured") or status.get("logged_in") or status.get("api_key"))
        if not configured:
            report.fail(
                f"model.provider '{runtime_provider}' is set but no API key is configured",
                "(check ~/.hermes/.env or run 'hermes setup')",
                fix=f"run 'hermes setup' or set the API key in {_DHH}/.env",
            )


@register("Configuration Files", "config-version", priority=30)
def check_config_version(report):
    from hermes_cli.doctor import HERMES_HOME

    config_path = HERMES_HOME / "config.yaml"
    if not config_path.exists():
        return

    from hermes_cli.config import check_config_version as _ccv, migrate_config
    current_ver, latest_ver = _ccv()
    if current_ver < latest_ver:
        def _fix(r):
            migrate_config(interactive=False, quiet=False)
            r.ok("Config migrated to latest version")

        report.warn(f"Config version outdated (v{current_ver} → v{latest_ver})", "(new settings available)")
        report.add_issue(
            "config.yaml is outdated — run 'hermes setup' to migrate",
            fix_fn=_fix,
        )
    else:
        report.ok(f"Config version up to date (v{current_ver})")


@register("Configuration Files", "stale-root-keys", priority=40)
def check_stale_root_keys(report):
    from hermes_cli.doctor import HERMES_HOME

    config_path = HERMES_HOME / "config.yaml"
    if not config_path.exists():
        return

    import yaml
    with open(config_path, encoding="utf-8") as f:
        raw_config = yaml.safe_load(f) or {}

    stale = [k for k in ("provider", "base_url") if k in raw_config and isinstance(raw_config[k], str)]
    if not stale:
        return

    def _fix(r):
        raw_model = raw_config.get("model")
        if isinstance(raw_model, dict):
            model_section = raw_model
        elif isinstance(raw_model, str) and raw_model.strip():
            model_section = {"default": raw_model.strip()}
            raw_config["model"] = model_section
        else:
            model_section = {}
            raw_config["model"] = model_section
        for k in stale:
            if not model_section.get(k):
                model_section[k] = raw_config.pop(k)
            else:
                raw_config.pop(k)
        from utils import atomic_yaml_write
        atomic_yaml_write(config_path, raw_config)
        r.ok("Migrated stale root-level keys into model section")

    report.warn(
        f"Stale root-level config keys: {', '.join(stale)}",
        "(should be under 'model:' section)",
    )
    report.add_issue(
        f"stale root-level keys {stale} in config.yaml",
        fix_fn=_fix,
    )


@register("Configuration Files", "max-iterations-ghost", priority=50)
def check_max_iterations_ghost(report):
    from hermes_cli.doctor import HERMES_HOME, _DHH

    config_path = HERMES_HOME / "config.yaml"
    if not config_path.exists():
        return

    import yaml
    from hermes_cli.config import load_env, remove_env_value

    with open(config_path, encoding="utf-8") as f:
        raw_config = yaml.safe_load(f) or {}

    agent_cfg = raw_config.get("agent")
    cfg_max_turns = agent_cfg.get("max_turns") if isinstance(agent_cfg, dict) else None
    if cfg_max_turns is None:
        cfg_max_turns = raw_config.get("max_turns")

    env_ghost = load_env().get("HERMES_MAX_ITERATIONS")
    if not (cfg_max_turns is not None and env_ghost is not None
            and str(cfg_max_turns).strip() != str(env_ghost).strip()):
        return

    def _fix(r):
        if remove_env_value("HERMES_MAX_ITERATIONS"):
            r.ok(
                "Removed stale HERMES_MAX_ITERATIONS from .env "
                f"(config.yaml agent.max_turns={cfg_max_turns} is now authoritative)"
            )
        else:
            raise RuntimeError(
                f"could not remove HERMES_MAX_ITERATIONS from {_DHH}/.env — edit manually"
            )

    report.warn(
        f"HERMES_MAX_ITERATIONS={env_ghost} in .env shadows agent.max_turns={cfg_max_turns} in config.yaml",
        "(stale ghost from an earlier `hermes setup` run)",
    )
    report.add_issue(
        "stale HERMES_MAX_ITERATIONS in .env shadows config.yaml",
        fix_fn=_fix,
    )


@register("Config Structure", "config-structure-validation", priority=10)
def check_config_structure(report):
    from hermes_cli.config import validate_config_structure
    config_issues = validate_config_structure()
    if not config_issues:
        return
    for ci in config_issues:
        if ci.severity == "error":
            report.fail(ci.message)
        else:
            report.warn(ci.message)
        for hint_line in ci.hint.splitlines():
            report.info(hint_line)
        report.add_issue(ci.message)
