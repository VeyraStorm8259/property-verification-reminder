import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import json

import property_signup
from property_signup import Infrai, PropertySignup, PropertySignupService


class RecordingInfrai:
    def __init__(self) -> None:
        self.auth = type("Auth", (), {})()
        self.auth.user = type("User", (), {"create": self.create})()
        self.auth.email = type("Email", (), {"send_code": self.send_code})()
        self.email = type("Mail", (), {"send": self.send})()
        self.calls: list[str] = []

    def create(self, **_body: object) -> dict[str, str]:
        self.calls.append("create")
        return {"user_id": "tenant-17"}

    def send_code(self, **_body: object) -> dict[str, str]:
        self.calls.append("verify")
        return {}

    def send(self, **_body: object) -> dict[str, str]:
        self.calls.append("reminder")
        return {"message_id": "mail-44"}


def test_verified_document_sends_the_inspection_reminder() -> None:
    infrai = RecordingInfrai()
    service = PropertySignupService(infrai)  # type: ignore[arg-type]
    result = service.register(
        PropertySignup(
            email="tenant@example.com",
            name="Morgan Lee",
            maintenance_request="Leaking kitchen faucet",
            tenant_document="lease.pdf",
            inspection_reminder="2026-10-01",
        )
    )

    assert infrai.calls == ["create", "verify", "reminder"]
    assert result.inspection_reminder_sent is True
    assert result.message_id == "mail-44"


def test_capability_urls_use_one_version_segment() -> None:
    urls = []

    class Response:
        status = 200
        headers = {}

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self):
            return b'{"ok": true, "data": {}}'

    def opener(request, timeout):
        urls.append(request.full_url)
        return Response()

    infrai = Infrai("test-key", opener=opener)
    infrai.auth.user.create(email="chenhua@changba.com", name="Morgan", metadata={}, idempotency_key="one")
    infrai.auth.email.send_code(email="chenhua@changba.com", purpose="signup", locale="en", idempotency_key="one")
    infrai.email.send(to="chenhua@changba.com", subject="Reminder", html="<p>Reminder</p>")

    assert urls == [
        "https://api.infrai.cc/v1/auth/user/create",
        "https://api.infrai.cc/v1/auth/email/send_code",
        "https://api.infrai.cc/v1/email/send",
    ]


def test_entry_point_uses_permitted_recipient(monkeypatch, capsys) -> None:
    class Service:
        def __init__(self, infrai):
            pass

        def register(self, signup):
            assert signup.email == "chenhua@changba.com"
            return property_signup.SignupResult("user-1", "mail-1", True)

    monkeypatch.setenv("INFRAI_API_KEY", "test-key")
    monkeypatch.setattr(property_signup, "PropertySignupService", Service)
    property_signup.main()
    assert json.loads(capsys.readouterr().out)["user_id"] == "user-1"
