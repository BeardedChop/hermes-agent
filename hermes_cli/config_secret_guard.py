"""Reject display-only credential masks before a config file is changed."""

from typing import Any


def _looks_like_redacted_secret(value: str) -> bool:
    value = value.strip()
    folded = value.casefold()
    if "***" in value:
        return True
    if folded in {"redacted", "[redacted]", "<redacted>", "(redacted)", "[secret]", "<secret>"}:
        return True
    if folded.startswith("[redact") and value.endswith("]"):
        return True
    if folded.startswith("«redacted") and value.endswith("»"):
        return True
    return len(value) <= 64 and ("..." in value or "…" in value)


def refuse_redacted_secrets_in_config(data: dict[str, Any]) -> None:
    """Use the same credential-key rules as config display, never echoing the value."""
    from hermes_cli.config import _is_secret_config_key

    def walk(value: Any, path: tuple[str, ...] = ()) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                key_text = str(key)
                child_path = (*path, key_text)
                if (_is_secret_config_key(key_text) and isinstance(child, str)
                        and _looks_like_redacted_secret(child)):
                    raise ValueError(
                        f"Refusing to write a redacted credential placeholder at {'.'.join(child_path)} "
                        "to config.yaml. Enter the real credential through Hermes setup instead.")
                walk(child, child_path)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, (*path, str(index)))

    walk(data)
