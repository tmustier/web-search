from __future__ import annotations

from wstk.urlutil import DomainRules, get_host, is_allowed, redact_url


def test_get_host() -> None:
    assert get_host("https://Example.COM/path") == "example.com"


def test_is_allowed_block_wins() -> None:
    rules = DomainRules(allow=("example.com",), block=("blocked.example.com",))
    assert is_allowed("https://example.com", rules) is True
    assert is_allowed("https://blocked.example.com/page", rules) is False


def test_is_allowed_allowlist() -> None:
    rules = DomainRules(allow=("example.com",), block=())
    assert is_allowed("https://example.com", rules) is True
    assert is_allowed("https://sub.example.com", rules) is True
    assert is_allowed("https://other.com", rules) is False


def test_redact_url() -> None:
    assert redact_url("https://example.com/a?token=abc#frag") == "https://example.com/a"
