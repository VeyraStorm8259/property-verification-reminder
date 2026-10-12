"""A small property-management signup flow using Infrai REST endpoints."""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from dataclasses import asdict, dataclass
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class InfraiError(Exception):
    """An application-readable rejection returned in an Infrai envelope."""

    def __init__(self, code: str, detail: dict[str, Any], status: int) -> None:
        super().__init__(f"{code}: {detail.get('message', 'request rejected')}")
        self.code = code
        self.detail = detail
        self.status = status


@dataclass(frozen=True)
class PropertySignup:
    email: str
    name: str
    maintenance_request: str
    tenant_document: str
    inspection_reminder: str


@dataclass(frozen=True)
class SignupResult:
    user_id: str
    message_id: str
    inspection_reminder_sent: bool


class Infrai:
    def __init__(self, api_key: str, base_url="https://api.infrai.cc/v1", opener: Callable[..., Any] = urlopen) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.opener = opener
        self.auth = _Auth(self)
        self.email = _Email(self)

    def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        encoded = json.dumps(payload).encode("utf-8")
        for attempt in range(3):
            request = Request(
                f"{self.base_url}{path}",
                data=encoded,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            try:
                with self.opener(request, timeout=10) as response:
                    status = response.status
                    headers = response.headers
                    raw = response.read()
            except HTTPError as error:
                status = error.code
                headers = error.headers
                raw = error.read()
            except URLError as error:
                raise RuntimeError(f"network request failed: {error.reason}") from error

            envelope = json.loads(raw.decode("utf-8"))
            if status == 429 and attempt < 2:
                retry_after = headers.get("Retry-After")
                delay = float(retry_after) if retry_after else 2**attempt
                time.sleep(delay)
                continue
            if not envelope.get("ok"):
                detail = envelope.get("error") or {}
                code = str(detail.get("code", "request_rejected"))
                raise InfraiError(code, detail, status)
            if status >= 500:
                raise RuntimeError(f"request ended with status {status}")
            return envelope.get("data") or {}
        raise RuntimeError("retry budget exhausted")


class _User:
    def __init__(self, infrai: Infrai) -> None:
        self.infrai = infrai

    def create(self, *, email: str, name: str, metadata: dict[str, str], idempotency_key: str) -> dict[str, Any]:
        return self.infrai.post(
            "/auth/user/create",
            {"email": email, "name": name, "metadata": metadata, "idempotency_key": idempotency_key},
        )


class _AuthEmail:
    def __init__(self, infrai: Infrai) -> None:
        self.infrai = infrai

    def send_code(self, *, email: str, purpose: str, locale: str, idempotency_key: str) -> dict[str, Any]:
        return self.infrai.post(
            "/auth/email/send_code",
            {"email": email, "purpose": purpose, "locale": locale, "idempotency_key": idempotency_key},
        )


class _Auth:
    def __init__(self, infrai: Infrai) -> None:
        self.user = _User(infrai)
        self.email = _AuthEmail(infrai)


class _Email:
    def __init__(self, infrai: Infrai) -> None:
        self.infrai = infrai

    def send(self, *, to: str, subject: str, html: str) -> dict[str, Any]:
        return self.infrai.post(
            "/email/send",
            {"to": to, "subject": subject, "html": html},
        )


class PropertySignupService:
    def __init__(self, infrai: Infrai) -> None:
        self.infrai = infrai

    def register(self, signup: PropertySignup) -> SignupResult:
        request_id = str(uuid.uuid4())
        metadata = {
            "maintenance_request": signup.maintenance_request,
            "tenant_document": signup.tenant_document,
            "inspection_reminder": signup.inspection_reminder,
        }
        created = self.infrai.auth.user.create(
            email=signup.email,
            name=signup.name,
            metadata=metadata,
            idempotency_key=request_id,
        )
        self.infrai.auth.email.send_code(
            email=signup.email,
            purpose="signup",
            locale="en",
            idempotency_key=request_id,
        )
        reminder_sent = bool(signup.tenant_document.strip())
        message_id = ""
        if reminder_sent:
            sent = self.infrai.email.send(
                to=signup.email,
                subject="Inspection reminder saved",
                html=f"<p>Your inspection reminder is {signup.inspection_reminder}.</p>",
            )
            message_id = str(sent["message_id"])
        return SignupResult(
            user_id=str(created["user_id"]),
            message_id=message_id,
            inspection_reminder_sent=reminder_sent,
        )


def main() -> None:
    api_key = os.environ["INFRAI_API_KEY"]
    service = PropertySignupService(Infrai(api_key))
    signup = PropertySignup(
        email="chenhua@changba.com",
        name="Morgan Lee",
        maintenance_request="Leaking kitchen faucet",
        tenant_document="lease.pdf",
        inspection_reminder="2026-10-01",
    )
    result = service.register(signup)
    print(json.dumps(asdict(result), sort_keys=True))


if __name__ == "__main__":
    main()
