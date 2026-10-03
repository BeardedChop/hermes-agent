"""#111105: a config.yaml replacement that keeps mtime and size (``cp -p``, ``rsync -t``, a
timestamp-pinning writer) must still invalidate the load_config() cache, while an unchanged
file keeps serving the cached object."""
import os
import shutil
from unittest.mock import patch

import pytest

from hermes_cli import config as config_mod


def _replace_pinning_mtime(path, content: str) -> None:
    before = path.stat()
    other = path.with_name("other.yaml")
    other.write_text(content, encoding="utf-8")
    # POSIX ctime has a coarse clock; wait until its change can be observed.
    # Windows ctime is creation time, so utime cannot advance it.
    if os.name == "posix":
        while other.stat().st_ctime_ns <= before.st_ctime_ns:
            os.utime(other)
    shutil.copy2(other, path)
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))


@pytest.mark.parametrize("reader", ["_load_config_impl", "_read_raw_config_impl"])
def test_load_config_sees_replacement_with_pinned_mtime_and_size(tmp_path, reader):
    with patch.dict(os.environ, {"HERMES_HOME": str(tmp_path)}):
        config_mod._LOAD_CONFIG_CACHE.clear()
        config_mod._RAW_CONFIG_CACHE.clear()
        cfg = tmp_path / "config.yaml"
        cfg.write_text("model:\n  default: aaaa-route\n", encoding="utf-8")
        read = getattr(config_mod, reader)
        first = read(want_deepcopy=False)
        assert read(want_deepcopy=False) is first  # unchanged file: cache hit
        _replace_pinning_mtime(cfg, "model:\n  default: bbbb-route\n")
        assert read(want_deepcopy=False)["model"]["default"] == "bbbb-route"


def test_managed_config_sees_replacement_with_pinned_mtime_and_size(tmp_path, monkeypatch):
    managed = tmp_path / "managed"
    managed.mkdir()
    monkeypatch.setenv("HERMES_MANAGED_DIR", str(managed))
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "home"))
    config_mod.managed_scope.invalidate_managed_cache()
    config_mod._LOAD_CONFIG_CACHE.clear()
    cfg = managed / "config.yaml"
    cfg.write_text("model:\n  default: aaaa-route\n", encoding="utf-8")
    assert config_mod.load_config()["model"]["default"] == "aaaa-route"
    _replace_pinning_mtime(cfg, "model:\n  default: bbbb-route\n")
    assert config_mod.load_config()["model"]["default"] == "bbbb-route"
    assert config_mod.managed_scope.load_managed_config()["model"]["default"] == "bbbb-route"
