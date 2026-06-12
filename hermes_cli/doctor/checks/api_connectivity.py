"""API connectivity checks — run in parallel."""

from __future__ import annotations

import concurrent.futures
import os

from hermes_cli.doctor._registry import register
from hermes_cli.doctor._output import color, _Ansi


# ── Individual probes ─────────────────────────────────────────────────────
# Each returns (label, lines, issues) where lines = list of (glyph, label, detail).

def _probe_openrouter():
    from hermes_constants import OPENROUTER_MODELS_URL
    from hermes_cli.models import _HERMES_USER_AGENT

    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        return ("OpenRouter API", [(color("⚠", _Ansi.YELLOW), "OpenRouter API", color("(not configured)", _Ansi.DIM))], [])

    import httpx
    r = httpx.get(OPENROUTER_MODELS_URL, headers={"Authorization": f"Bearer {key}"}, timeout=10)
    if r.status_code == 200:
        return ("OpenRouter API", [(color("✓", _Ansi.GREEN), "OpenRouter API", "")], [])
    if r.status_code == 401:
        return ("OpenRouter API", [(color("✗", _Ansi.RED), "OpenRouter API", color("(invalid API key)", _Ansi.DIM))], ["Check OPENROUTER_API_KEY in .env"])
    if r.status_code == 402:
        return ("OpenRouter API", [(color("✗", _Ansi.RED), "OpenRouter API", color("(out of credits — payment required)", _Ansi.DIM))],
                ["OpenRouter account has insufficient credits. Fix: run 'hermes config set model.provider <provider>' to switch providers, or fund your OpenRouter account at https://openrouter.ai/settings/credits"])
    if r.status_code == 429:
        return ("OpenRouter API", [(color("✗", _Ansi.RED), "OpenRouter API", color("(rate limited)", _Ansi.DIM))],
                ["OpenRouter rate limit hit — consider switching to a different provider or waiting"])
    return ("OpenRouter API", [(color("✗", _Ansi.RED), "OpenRouter API", color(f"(HTTP {r.status_code})", _Ansi.DIM))], [])


def _probe_anthropic():
    from hermes_cli.auth import get_anthropic_key
    key = get_anthropic_key()
    if not key:
        return ("Anthropic API", [], [])

    import httpx
    from agent.anthropic_adapter import _is_oauth_token, _COMMON_BETAS, _OAUTH_ONLY_BETAS, _CONTEXT_1M_BETA
    headers = {"anthropic-version": "2023-06-01"}
    is_oauth = _is_oauth_token(key)
    if is_oauth:
        headers["Authorization"] = f"Bearer {key}"
        headers["anthropic-beta"] = ",".join(_COMMON_BETAS + _OAUTH_ONLY_BETAS)
    else:
        headers["x-api-key"] = key
    r = httpx.get("https://api.anthropic.com/v1/models", headers=headers, timeout=10)
    if is_oauth and r.status_code == 400 and "long context beta" in r.text.lower() and "not yet available" in r.text.lower():
        headers["anthropic-beta"] = ",".join(
            [b for b in _COMMON_BETAS if b != _CONTEXT_1M_BETA] + list(_OAUTH_ONLY_BETAS)
        )
        r = httpx.get("https://api.anthropic.com/v1/models", headers=headers, timeout=10)
    if r.status_code == 200:
        return ("Anthropic API", [(color("✓", _Ansi.GREEN), "Anthropic API", "")], [])
    if r.status_code == 401:
        return ("Anthropic API", [(color("✗", _Ansi.RED), "Anthropic API", color("(invalid API key)", _Ansi.DIM))], [])
    return ("Anthropic API", [(color("⚠", _Ansi.YELLOW), "Anthropic API", color("(couldn't verify)", _Ansi.DIM))], [])


def _probe_apikey_provider(pname, env_vars, default_url, base_env, supports_hc):
    key = ""
    for ev in env_vars:
        key = os.getenv(ev, "")
        if key:
            break
    if not key:
        return (pname, [], [])

    label = pname.ljust(20)
    if not supports_hc:
        return (pname, [(color("✓", _Ansi.GREEN), label, color("(key configured)", _Ansi.DIM))], [])

    import httpx
    from hermes_cli.models import _HERMES_USER_AGENT
    from utils import base_url_host_matches

    base = os.getenv(base_env, "") if base_env else ""
    if not base and key.startswith("sk-kimi-"):
        base = "https://api.kimi.com/coding/v1"
    if base and base.rstrip("/").endswith("/anthropic"):
        from agent.auxiliary_client import _to_openai_base_url
        base = _to_openai_base_url(base)
    if base_url_host_matches(base, "api.kimi.com") and base.rstrip("/").endswith("/coding"):
        base = base.rstrip("/") + "/v1"
    url = (base.rstrip("/") + "/models") if base else default_url
    headers = {"Authorization": f"Bearer {key}", "User-Agent": _HERMES_USER_AGENT}
    if base_url_host_matches(base, "api.kimi.com"):
        headers["User-Agent"] = "claude-code/0.1.0"
    if url and base_url_host_matches(url, "generativelanguage.googleapis.com"):
        headers.pop("Authorization", None)
        headers["x-goog-api-key"] = key
    r = httpx.get(url, headers=headers, timeout=10)
    if pname == "Alibaba/DashScope" and not base and r.status_code == 401:
        r = httpx.get("https://dashscope.aliyuncs.com/compatible-mode/v1/models", headers=headers, timeout=10)
    if r.status_code == 200:
        return (pname, [(color("✓", _Ansi.GREEN), label, "")], [])
    if r.status_code == 401:
        return (pname, [(color("✗", _Ansi.RED), label, color("(invalid API key)", _Ansi.DIM))], [f"Check {env_vars[0]} in .env"])
    return (pname, [(color("⚠", _Ansi.YELLOW), label, color(f"(HTTP {r.status_code})", _Ansi.DIM))], [])


def _probe_bedrock():
    from agent.bedrock_adapter import has_aws_credentials, resolve_aws_auth_env_var, resolve_bedrock_region
    if not has_aws_credentials():
        return ("AWS Bedrock", [], [])

    import boto3
    from botocore.config import Config as _BotoConfig

    auth_var = resolve_aws_auth_env_var()
    region = resolve_bedrock_region()
    label = "AWS Bedrock".ljust(20)
    cfg = _BotoConfig(connect_timeout=5, read_timeout=10, retries={"max_attempts": 1})
    client = boto3.client("bedrock", region_name=region, config=cfg)
    resp = client.list_foundation_models()
    n = len(resp.get("modelSummaries", []))
    return ("AWS Bedrock", [(color("✓", _Ansi.GREEN), label, color(f"({auth_var}, {region}, {n} models)", _Ansi.DIM))], [])


def _probe_azure_entra():
    from hermes_cli.config import load_config
    cfg = load_config()
    model_cfg = cfg.get("model") if isinstance(cfg, dict) else {}
    if not isinstance(model_cfg, dict):
        return ("Azure Foundry (Entra ID)", [], [])
    if str(model_cfg.get("provider") or "").strip().lower() != "azure-foundry":
        return ("Azure Foundry (Entra ID)", [], [])
    if str(model_cfg.get("auth_mode") or "").strip().lower() != "entra_id":
        return ("Azure Foundry (Entra ID)", [], [])

    label = "Azure Foundry (Entra ID)".ljust(28)
    from agent.azure_identity_adapter import (
        EntraIdentityConfig, SCOPE_AI_AZURE_DEFAULT,
        describe_active_credential, has_azure_identity_installed,
    )
    if not has_azure_identity_installed():
        return ("Azure Foundry (Entra ID)",
                [(color("⚠", _Ansi.YELLOW), label, color("(azure-identity not installed)", _Ansi.DIM))],
                ["Install azure-identity: uv pip install azure-identity"])

    entra_cfg = model_cfg.get("entra") or {}
    if not isinstance(entra_cfg, dict):
        entra_cfg = {}
    scope = str(entra_cfg.get("scope") or "").strip() or SCOPE_AI_AZURE_DEFAULT
    info = describe_active_credential(config=EntraIdentityConfig(scope=scope), timeout_seconds=10.0)
    if info.get("ok"):
        env_sources = info.get("env_sources") or []
        tag = ", ".join(env_sources) if env_sources else "default credential chain"
        return ("Azure Foundry (Entra ID)",
                [(color("✓", _Ansi.GREEN), label, color(f"({tag}, scope={scope})", _Ansi.DIM))], [])
    err = info.get("error") or "credential chain exhausted"
    hint = info.get("hint") or (
        "Run `az login`, set AZURE_TENANT_ID/AZURE_CLIENT_ID/AZURE_CLIENT_SECRET, "
        "or attach a managed identity to this VM."
    )
    return ("Azure Foundry (Entra ID)",
            [(color("⚠", _Ansi.YELLOW), label, color(f"({err})", _Ansi.DIM))],
            [f"Azure Foundry Entra: {err}. {hint}"])


def _has_healthy_oauth_fallback(provider_label: str) -> bool:
    normalized = (provider_label or "").strip().lower()
    if normalized in {"google / gemini", "gemini"}:
        try:
            from hermes_cli.auth import get_gemini_oauth_auth_status
            return bool((get_gemini_oauth_auth_status() or {}).get("logged_in"))
        except Exception:
            return False
    if normalized == "minimax":
        try:
            from hermes_cli.auth import get_minimax_oauth_auth_status
            return bool((get_minimax_oauth_auth_status() or {}).get("logged_in"))
        except Exception:
            return False
    if normalized == "xai":
        try:
            from hermes_cli.auth import get_xai_oauth_auth_status
            return bool((get_xai_oauth_auth_status() or {}).get("logged_in"))
        except Exception:
            return False
    return False


# Cache for the expensive provider list build
_APIKEY_PROVIDERS_CACHE: list | None = None


def _build_apikey_providers_list() -> list:
    """Build the API-key provider health-check list and cache it."""
    _static = [
        ("Z.AI / GLM",      ("GLM_API_KEY", "ZAI_API_KEY", "Z_AI_API_KEY"), "https://api.z.ai/api/paas/v4/models", "GLM_BASE_URL", True),
        ("Kimi / Moonshot",  ("KIMI_API_KEY",),                              "https://api.moonshot.ai/v1/models",   "KIMI_BASE_URL", True),
        ("StepFun Step Plan", ("STEPFUN_API_KEY",),                          "https://api.stepfun.ai/step_plan/v1/models", "STEPFUN_BASE_URL", True),
        ("Kimi / Moonshot (China)", ("KIMI_CN_API_KEY",),                    "https://api.moonshot.cn/v1/models",   None, True),
        ("Arcee AI",         ("ARCEEAI_API_KEY",),                           "https://api.arcee.ai/api/v1/models",  "ARCEE_BASE_URL", True),
        ("GMI Cloud",        ("GMI_API_KEY",),                               "https://api.gmi-serving.com/v1/models", "GMI_BASE_URL", True),
        ("DeepSeek",         ("DEEPSEEK_API_KEY",),                          "https://api.deepseek.com/v1/models",  "DEEPSEEK_BASE_URL", True),
        ("Hugging Face",     ("HF_TOKEN",),                                  "https://router.huggingface.co/v1/models", "HF_BASE_URL", True),
        ("NVIDIA NIM",       ("NVIDIA_API_KEY",),                            "https://integrate.api.nvidia.com/v1/models", "NVIDIA_BASE_URL", True),
        ("Alibaba/DashScope", ("DASHSCOPE_API_KEY",),                        "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/models", "DASHSCOPE_BASE_URL", True),
        ("MiniMax",          ("MINIMAX_API_KEY",),                           "https://api.minimax.io/v1/models",    "MINIMAX_BASE_URL", True),
        ("MiniMax (China)",  ("MINIMAX_CN_API_KEY",),                        "https://api.minimaxi.com/v1/models",  "MINIMAX_CN_BASE_URL", False),
        ("Kilo Code",        ("KILOCODE_API_KEY",),                          "https://api.kilo.ai/api/gateway/models", "KILOCODE_BASE_URL", True),
        ("OpenCode Zen",     ("OPENCODE_ZEN_API_KEY",),                      "https://opencode.ai/zen/v1/models",  "OPENCODE_ZEN_BASE_URL", True),
        ("OpenCode Go",      ("OPENCODE_GO_API_KEY",),                       None,                                  "OPENCODE_GO_BASE_URL", False),
    ]
    _known_names = {t[0] for t in _static}
    _name_to_canonical = {
        "Z.AI / GLM": "zai", "Kimi / Moonshot": "kimi-coding",
        "StepFun Step Plan": "stepfun", "Kimi / Moonshot (China)": "kimi-coding-cn",
        "Arcee AI": "arcee", "GMI Cloud": "gmi", "DeepSeek": "deepseek",
        "Hugging Face": "huggingface", "NVIDIA NIM": "nvidia",
        "Alibaba/DashScope": "alibaba", "MiniMax": "minimax",
        "MiniMax (China)": "minimax-cn",
        "Kilo Code": "kilocode", "OpenCode Zen": "opencode-zen",
        "OpenCode Go": "opencode-go",
    }
    _known_canonical = set(_name_to_canonical.values())
    _dedicated = {"anthropic", "openrouter", "bedrock"}
    _known_canonical.update(_dedicated)

    try:
        from providers import list_providers
        from providers.base import ProviderProfile as _PP
        try:
            from hermes_cli.providers import normalize_provider as _nrm
        except Exception:
            def _nrm(n): return (n or "").strip().lower()

        for pp in list_providers():
            if not isinstance(pp, _PP) or pp.auth_type != "api_key" or not pp.env_vars:
                continue
            label = pp.display_name or pp.name
            if label in _known_names or pp.name in _known_canonical:
                continue
            candidates = {_nrm(pp.name)} | {_nrm(a) for a in (pp.aliases or ())}
            if candidates & _dedicated:
                continue
            key_vars = tuple(v for v in pp.env_vars if not v.endswith(("_BASE_URL", "_URL")))
            base_var = next((v for v in pp.env_vars if v.endswith(("_BASE_URL", "_URL"))), None)
            if not key_vars:
                continue
            models_url = (
                (pp.models_url or (pp.base_url.rstrip("/") + "/models")) if pp.base_url else None
            )
            hc = getattr(pp, "supports_health_check", True)
            _static.append((label, key_vars, models_url, base_var, hc))
    except Exception:
        pass

    return _static


@register("API Connectivity", "api-connectivity", priority=10)
def check_api_connectivity(report):
    global _APIKEY_PROVIDERS_CACHE
    if _APIKEY_PROVIDERS_CACHE is None:
        _APIKEY_PROVIDERS_CACHE = _build_apikey_providers_list()

    probes = [("OpenRouter API", _probe_openrouter), ("Anthropic API", _probe_anthropic)]
    for pname, env_vars, default_url, base_env, supports in _APIKEY_PROVIDERS_CACHE:
        probes.append((pname, lambda p=pname, e=env_vars, u=default_url, b=base_env, s=supports:
                       _probe_apikey_provider(p, e, u, b, s)))
    probes.append(("AWS Bedrock", _probe_bedrock))
    probes.append(("Azure Foundry (Entra ID)", _probe_azure_entra))

    print(
        f"  {color(f'Running {len(probes)} connectivity checks in parallel…', _Ansi.DIM)}",
        end="", flush=True,
    )

    prev_imds = os.environ.get("AWS_EC2_METADATA_DISABLED")
    os.environ["AWS_EC2_METADATA_DISABLED"] = "true"
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=8, thread_name_prefix="doctor-probe") as ex:
            futures = [ex.submit(fn) for _, fn in probes]
            results = []
            for f in futures:
                try:
                    results.append(f.result())
                except Exception as exc:
                    results.append((None, [(color("⚠", _Ansi.YELLOW), "probe", color(f"({exc})", _Ansi.DIM))], []))
    finally:
        if prev_imds is None:
            os.environ.pop("AWS_EC2_METADATA_DISABLED", None)
        else:
            os.environ["AWS_EC2_METADATA_DISABLED"] = prev_imds

    print("\r" + " " * 70 + "\r", end="")
    for label, lines, issues in results:
        for glyph, lbl, detail in lines:
            if detail:
                print(f"  {glyph} {lbl} {detail}")
            else:
                print(f"  {glyph} {lbl}")
        if issues and not _has_healthy_oauth_fallback(label or ""):
            for issue in issues:
                report.add_issue(issue)
