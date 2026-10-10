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

    def __init__(self, message: str, *, reason: str = "unknown"):
        super().__init__(message)
        self.reason = reason  # safe machine-readable code for logs


def get_template() -> str:
    # Keep the Kidareh-specific variable compatible with Smart-MEC's name.
    return (
        os.environ.get("KAVENEGAR_VERIFY_TEMPLATE")
        or os.environ.get("KAVENEGAR_TEMPLATE")
        or "verify"
    ).strip()


def send_otp(phone: str, code: str) -> bool:
    api_key = os.environ.get("KAVENEGAR_API_KEY", "").strip()
    template = get_template()
    if not api_key:
        raise SMSDeliveryError(
            "KAVENEGAR_API_KEY is not configured",
            reason="missing_api_key",
        )
    if not template:
        raise SMSDeliveryError(
            "Kavenegar verification template is not configured",
            reason="missing_template",
        )
    if len(phone) != 11 or not phone.startswith("09") or not phone.isdigit():
        raise SMSDeliveryError("Invalid Iranian mobile number", reason="invalid_phone")
    if len(code) != 6 or not code.isdigit():
        raise SMSDeliveryError("OTP must be six digits", reason="invalid_otp")

    # Never put the raw API key into exception messages that may be logged.
    url = f"https://api.kavenegar.com/v1/{urllib.parse.quote(api_key, safe='')}/verify/lookup.json"
    body = urllib.parse.urlencode(
        {"receptor": phone, "token": code, "template": template}
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    try:
        timeout = max(2, min(20, int(os.environ.get("KAVENEGAR_TIMEOUT_SECONDS", "10"))))
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            payload = json.loads(raw)
    except urllib.error.HTTPError as exc:
        # Kavenegar often returns JSON body even on non-2xx.
        status_code = getattr(exc, "code", None)
        body_status = None
        try:
            err_body = exc.read().decode("utf-8", errors="replace")
            err_json = json.loads(err_body)
            body_status = (
                err_json.get("return", {}).get("status")
                if isinstance(err_json, dict)
                else None
            )
        except Exception:
            pass
        raise SMSDeliveryError(
            f"Kavenegar HTTP error (http={status_code}, api_status={body_status})",
            reason=f"http_{status_code}_api_{body_status}",
        ) from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise SMSDeliveryError(
            f"Kavenegar network error: {type(exc).__name__}",
            reason="network_error",
        ) from None
    except (ValueError, json.JSONDecodeError):
        raise SMSDeliveryError(
            "Kavenegar returned invalid JSON",
            reason="invalid_json",
        ) from None

    if not isinstance(payload, dict):
        raise SMSDeliveryError(
            "Kavenegar returned unexpected payload",
            reason="bad_payload",
        )

    api_status = payload.get("return", {}).get("status")
    if api_status != 200:
        # Common Kavenegar statuses: 414 template, 411 receptor, 418 account, etc.
        raise SMSDeliveryError(
            f"Kavenegar rejected OTP (api_status={api_status}, template={template})",
            reason=f"api_status_{api_status}",
        )
    return True
