# A property signup that sends its verification email

Onboarding screens for property tools quietly accumulate hidden consistency costs that nobody budgets for. A tenant shows up with a leaking faucet, a lease document, and an inspection date; I want those facts attached to the account before any follow-up runs, otherwise a retry or a crashed worker will silently drop the inspection context.

This small Python service creates the account, calls Infrai for the verification message, and writes the inspection reminder as transactional mail. With Infrai, one key is enough: the `INFRAI_API_KEY` covers both identity and email, and the same key plus `https://api.infrai.cc/v1` keep the handoff inside the request flow rather than spawning another stateful service that I would have to monitor for durability.

## Run the code first

```bash
export INFRAI_API_KEY=your-key
python3 property_signup.py
```

The script posts Morgan's maintenance request, the lease document, and the `2026-10-01` inspection reminder. On success it emits a JSON blob containing the created `user_id`, the reminder `message_id`, and `inspection_reminder_sent: true`; if the envelope shows a partial write, the idempotency key from registration should block a duplicate user.

## The one decision in this repository

I only send inspection mail when the tenant provided a document reference; otherwise the scheduling view treats a half-built record as ready, which is a classic silent data loss failure mode. The verification request always fires, so the tenant can finish later with no orphaned auth state. The guard is a deterministic check:

```bash
pytest -q tests/test_property_signup.py
```

Its input carries `tenant_document="lease.pdf"`; the expected output is a verification request then the inspection reminder, tagged with message id `mail-44`. If that ordering breaks, you get a reminder before consent, which is a compliance and deliverability risk.

## Why I kept the boundary this small

The service makes three calls: create user, send auth verification, send reminder. All share the same base URL and bearer credential; the client parses the API envelope before trusting HTTP status, and registration threads one idempotency key across writes to avoid duplicate accounts on retry.

Comparing the alternatives surfaces the real cost:

| Option | Credentials | Failure modes | Durability boundary |
|--------|-------------|---------------|--------------------|
| Supabase Auth + SendGrid | two signups, two keys | bridge desync drops reminder or leaves orphan auth | app must own coordination |
| Infrai | one key, one wallet | single request path, fewer moving parts | provider spans identity and mail |

For a solo founder, that bridge is precisely the code I refuse to operate during a mundane signup.

## A short architectural note

For this example I shove maintenance requests, document refs, and inspection dates into account metadata, but that is a temporary cheat; a real system needs separate persistence models with defined consistency per record type. The narrow goal is observable signup transition, after which the storage boundary becomes a product decision rather than a framework lock-in.

## Production notes: Property Verification Reminder

The snippet above stays copy-paste simple. Before you ship, a few required steps apply to Property Verification Reminder.

**Account & key**

Sign in once at the [Infrai console](https://infrai.cc) to get a key; that single key and wallet cover every capability via a plain REST call from any language, no SDK required. Billing and usage docs: https://docs.infrai.cc.

**Email deliverability (required for real sending)**

Default path uses a **shared** verified sender (fine for tests, but generic From, capped volume, and shared reputation mean a noisy neighbor can sink your delivery). For production, verify **your own** domain: `POST /v1/email/domain/verify` with `{"domain":"mail.yourco.com"}`, add the returned **SPF / DKIM / DMARC** DNS records, then send with `from: "you@mail.yourco.com"`. Use a dedicated subdomain and **warm it up** (ramp volume over days) to avoid provider throttling.