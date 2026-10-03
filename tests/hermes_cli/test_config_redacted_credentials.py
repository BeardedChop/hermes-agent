"""Masked credentials must never replace working settings through either writer."""

import pytest

from hermes_cli.config import atomic_config_replace, atomic_config_write, save_config


@pytest.mark.parametrize("writer", [atomic_config_write, atomic_config_replace, save_config])
@pytest.mark.parametrize(
    "section, key, placeholder",
    [
        ("model", "api_key", "***"),
        ("model", "api_key", "[REDACTED]"),
        ("model", "api_key", "sk-a...z"),
        ("model", "api_key", "sk-a…z"),
        ("model", "api_key", "«redacted:sk-…»"),
        ("model", "api_key", "<redacted>"),
        ("model", "api_key", "(redacted)"),
        ("model", "api_key", "[secret]"),
        ("headers", "Authorization", "Bearer ***"),
        ("headers", "X-API-Key", "***"),
        ("env", "EXAMPLE_API_KEY", "sk-..."),
        ("env", "FAL_KEY", "***"),
        ("env", "EXAMPLE_PRIVATE_KEY", "***"),
        ("custom_providers", "api_key", "sk-..."),
    ],
)
def test_masked_credentials_are_refused_without_changing_the_file(
    tmp_path, monkeypatch, writer, section, key, placeholder,
):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    path = tmp_path / "config.yaml"
    original = b"# user settings\nmodel:\n  default: example-model\n"
    path.write_bytes(original)
    data: dict = {"model": {"default": "example-model"}}
    if section == "model":
        data["model"][key] = placeholder
    elif section == "custom_providers":
        data["custom_providers"] = [{"name": "example", key: placeholder}]
    else:
        data["mcp_servers"] = {"example": {section: {key: placeholder}}}

    with pytest.raises(ValueError, match="redacted credential placeholder") as error:
        if writer is save_config:
            writer(data)
        else:
            writer(path, data)

    assert path.read_bytes() == original
    assert placeholder not in str(error.value)


@pytest.mark.parametrize("writer", [atomic_config_write, atomic_config_replace, save_config])
@pytest.mark.parametrize(
    "value", ["${EXAMPLE_API_KEY}", "configured-value", "", "a" * 70 + "..."],
)
def test_valid_settings_survive_profile_switches(tmp_path, monkeypatch, writer, value):
    from hermes_constants import set_hermes_home_override, reset_hermes_home_override
    from hermes_cli.config import read_raw_config

    homes = [tmp_path / "a", tmp_path / "b"]
    for home in homes:
        home.mkdir()
        (home / "config.yaml").write_text("# user settings\nmodel:\n  default: example-model\n", encoding="utf-8")
    monkeypatch.setenv("HERMES_HOME", str(homes[0]))
    for index in (0, 1, 0):
        token = set_hermes_home_override(homes[index])
        try:
            data = {
                "model": {"default": "example-model", "api_key": value},
                "display": {"token_count": "***", "secret_santa": "***"},
            }
            if writer is save_config:
                writer(data)
            else:
                writer(homes[index] / "config.yaml", data)
            saved = read_raw_config()
            assert saved["model"]["api_key"] == value
            assert saved["display"]["token_count"] == "***"
            assert saved["display"]["secret_santa"] == "***"
            assert (homes[index] / "config.yaml").read_text(encoding="utf-8").startswith("# user settings")
        finally:
            reset_hermes_home_override(token)
