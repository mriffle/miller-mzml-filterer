from __future__ import annotations

from miller import _version


def test_get_version_prefers_installed_distribution(monkeypatch) -> None:
    _version.get_version.cache_clear()
    monkeypatch.setattr(_version, "_get_installed_version", lambda: "1.2.3")
    monkeypatch.setattr(_version, "_get_exact_tag", lambda: "v9.9.9")
    monkeypatch.setattr(_version, "_get_git_hash", lambda: "abcdef0")

    assert _version.get_version() == "1.2.3"


def test_get_version_falls_back_to_exact_tag(monkeypatch) -> None:
    _version.get_version.cache_clear()
    monkeypatch.setattr(_version, "_get_installed_version", lambda: None)
    monkeypatch.setattr(_version, "_get_exact_tag", lambda: "v1.2.3")
    monkeypatch.setattr(_version, "_get_git_hash", lambda: "abcdef0")

    assert _version.get_version() == "1.2.3"


def test_get_version_falls_back_to_git_hash(monkeypatch) -> None:
    _version.get_version.cache_clear()
    monkeypatch.setattr(_version, "_get_installed_version", lambda: None)
    monkeypatch.setattr(_version, "_get_exact_tag", lambda: None)
    monkeypatch.setattr(_version, "_get_git_hash", lambda: "abcdef0")

    assert _version.get_version() == "git-abcdef0"


def test_get_version_returns_not_available_without_metadata(monkeypatch) -> None:
    _version.get_version.cache_clear()
    monkeypatch.setattr(_version, "_get_installed_version", lambda: None)
    monkeypatch.setattr(_version, "_get_exact_tag", lambda: None)
    monkeypatch.setattr(_version, "_get_git_hash", lambda: None)

    assert _version.get_version() == "not available"
