"""Kavenegar OTP delivery adapter, inspired by Smart-MEC's SMSService.

Secrets are read at call time so production environment updates do not require
restarting Python imports in tests or application workers.
"""
import json
import os
import urllib.error
import urllib.parse
import urllib.request


class SMSDeliveryError(RuntimeError):
    """Raised when Kavenegar cannot confirm OTP delivery."""


def get_template() -> str:
    # Keep the Kidareh-specific variable compatible with Smart-MEC's name.
    return (os.environ.get("KAVENEGAR_VERIFY_TEMPLATE") or os.environ.get("KAVENEGAR_TEMPLATE") or "verify").strip()


def send_otp(phone: str, code: str) -> bool:
    api_key = os.environ.get("KAVENEGAR_API_KEY", "").strip()
    template = get_template()
    if not api_key:
        raise SMSDeliveryError("KAVENEGAR_API_KEY is not configured")
    if not template:
        raise SMSDeliveryError("Kavenegar verification template is not configured")
    if len(phone) != 11 or not phone.startswith("09") or not phone.isdigit():
        raise SMSDeliveryError("Invalid Iranian mobile number")
    if len(code) != 6 or not code.isdigit():
        raise SMSDeliveryError("OTP must be six digits")

    url = f"https://api.kavenegar.com/v1/{urllib.parse.quote(api_key, safe='')}/verify/lookup.json"
    body = urllib.parse.urlencode({"receptor": phone, "token": code, "template": template}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        timeout = max(2, min(20, int(os.environ.get("KAVENEGAR_TIMEOUT_SECONDS", "10"))))
        with urllib.request.urlopen(req, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
        raise SMSDeliveryError("Kavenegar request failed") from exc

    if not isinstance(payload, dict) or payload.get("return", {}).get("status") != 200:
        raise SMSDeliveryError("Kavenegar did not accept the OTP request")
    return True
