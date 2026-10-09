import json
import urllib.parse

import pytest

from kidareh.services import sms


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload
    def __enter__(self): return self
    def __exit__(self, *_args): return False
    def read(self): return json.dumps(self.payload).encode("utf-8")


def test_kavenegar_uses_smart_mec_template_variable_and_form_post(monkeypatch):
    monkeypatch.setenv("KAVENEGAR_API_KEY", "test-key")
    monkeypatch.delenv("KAVENEGAR_VERIFY_TEMPLATE", raising=False)
    monkeypatch.setenv("KAVENEGAR_TEMPLATE", "smartmechanicregister")
    seen = {}
    def fake_urlopen(request, timeout):
        seen["url"] = request.full_url
        seen["method"] = request.get_method()
        seen["body"] = urllib.parse.parse_qs(request.data.decode())
        seen["timeout"] = timeout
        return FakeResponse({"return": {"status": 200}})
    monkeypatch.setattr(sms.urllib.request, "urlopen", fake_urlopen)
    assert sms.send_otp("09123456789", "123456") is True
    assert "/verify/lookup.json" in seen["url"]
    assert seen["method"] == "POST"
    assert seen["body"] == {"receptor": ["09123456789"], "token": ["123456"], "template": ["smartmechanicregister"]}
    assert seen["timeout"] == 10


def test_kidareh_template_variable_has_precedence(monkeypatch):
    monkeypatch.setenv("KAVENEGAR_VERIFY_TEMPLATE", "kidareh-otp")
    monkeypatch.setenv("KAVENEGAR_TEMPLATE", "smartmechanicregister")
    assert sms.get_template() == "kidareh-otp"


def test_sms_fails_closed_without_api_key(monkeypatch):
    monkeypatch.delenv("KAVENEGAR_API_KEY", raising=False)
    with pytest.raises(sms.SMSDeliveryError):
        sms.send_otp("09123456789", "123456")


def test_sms_rejects_kavenegar_error_response(monkeypatch):
    monkeypatch.setenv("KAVENEGAR_API_KEY", "test-key")
    monkeypatch.setattr(sms.urllib.request, "urlopen", lambda *_a, **_k: FakeResponse({"return": {"status": 400}}))
    with pytest.raises(sms.SMSDeliveryError):
        sms.send_otp("09123456789", "123456")


def test_sms_validates_phone_and_otp(monkeypatch):
    monkeypatch.setenv("KAVENEGAR_API_KEY", "test-key")
    with pytest.raises(sms.SMSDeliveryError): sms.send_otp("123", "123456")
    with pytest.raises(sms.SMSDeliveryError): sms.send_otp("09123456789", "12")
