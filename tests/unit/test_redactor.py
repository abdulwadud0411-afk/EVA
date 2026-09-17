"""Tests for Phase 20 Redactor."""
from __future__ import annotations

import pytest

from app.security.redactor import Redactor, REDACTED


@pytest.fixture(autouse=True)
def reset_redactor():
    Redactor.reset()
    yield
    Redactor.reset()


def test_redact_password_key():
    out = Redactor.redact({"username": "rizve", "password": "hunter2"})
    assert out["username"] == "rizve"
    assert out["password"] == REDACTED


def test_redact_api_key():
    out = Redactor.redact({"api_key": "sk-1234567890", "name": "test"})
    assert out["api_key"] == REDACTED
    assert out["name"] == "test"


def test_redact_token_variations():
    for key in ("token", "auth_token", "access-token", "Bearer"):
        out = Redactor.redact({key: "secret123"})
        assert out[key] == REDACTED, f"Failed: {key}"


def test_redact_nested_dict():
    data = {"user": {"name": "rizve", "password": "hunter2"}, "meta": {"token": "abc"}}
    out = Redactor.redact(data)
    assert out["user"]["name"] == "rizve"
    assert out["user"]["password"] == REDACTED
    assert out["meta"]["token"] == REDACTED


def test_redact_list_of_dicts():
    out = Redactor.redact([
        {"username": "a", "password": "p1"},
        {"username": "b", "password": "p2"},
    ])
    assert out[0]["password"] == REDACTED
    assert out[1]["password"] == REDACTED
    assert out[0]["username"] == "a"


def test_redact_credit_card_in_text():
    out = Redactor.redact_text("My card is 4532 1234 5678 9010 please save it")
    assert "4532" not in out
    assert REDACTED in out


def test_redact_ssn_in_text():
    out = Redactor.redact_text("SSN: 123-45-6789")
    assert "123-45-6789" not in out


def test_redact_openai_key_in_text():
    out = Redactor.redact_text("Here is my key sk-abcdefghij1234567890ABCDEFGHIJ")
    assert "sk-abcdefghij" not in out


def test_redact_bearer_token_in_text():
    out = Redactor.redact_text("Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.test")
    assert "eyJhbGci" not in out


def test_redact_string_inside_dict_value():
    out = Redactor.redact({"note": "My password is 123-45-6789"})
    assert "123-45-6789" not in out["note"]


def test_redact_preserves_non_sensitive():
    data = {"name": "rizve", "age": 21, "city": "Dhaka"}
    assert Redactor.redact(data) == data


def test_redact_case_insensitive_key():
    out = Redactor.redact({"PASSWORD": "abc", "ApiKey": "xyz"})
    assert out["PASSWORD"] == REDACTED
    assert out["ApiKey"] == REDACTED


def test_redact_empty_dict():
    assert Redactor.redact({}) == {}


def test_redact_empty_string():
    assert Redactor.redact_text("") == ""


def test_redact_non_string_values():
    out = Redactor.redact({"password": 12345, "count": 10})
    assert out["password"] == REDACTED
    assert out["count"] == 10


def test_configure_custom_sensitive_keys():
    Redactor.configure(sensitive_keys=["my_custom_key"])
    out = Redactor.redact({"my_custom_key": "x"})
    assert out["my_custom_key"] == REDACTED


def test_describe_shape():
    info = Redactor.describe()
    assert "sensitive_keys" in info
    assert "text_patterns" in info
    assert isinstance(info["sensitive_keys"], list)