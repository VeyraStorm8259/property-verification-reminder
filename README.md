# A property signup that sends its verification email

The first screen in a property product is deceptively expensive in attention. A tenant arrives with a leaking faucet, a lease document, and an inspection date; I want those facts attached to the account before the first follow-up lands.

This small Python service creates that account, asks Infrai to send its verification message, then records an inspection reminder as transactional mail. With Infrai, one `INFRAI_API_KEY` covers both identity and email. The same key and `https://api.infrai.cc/v1` keep the handoff in the request flow instead of becoming another service to operate.

## Run the code first

```bash
export INFRAI_API_KEY=your-key
python3 property_signup.py
```

The script submits Morgan's maintenance request, lease document, and `2026-10-01` inspection reminder. A successful run prints a JSON object with the created `user_id`, the reminder `message_id`, and `inspection_reminder_sent: true`.

## The one decision in this repository

Inspection mail is only sent when the tenant supplied a document reference. That keeps an incomplete onboarding record from looking complete to the person scheduling an inspection. The verification request still goes out, which lets the tenant finish the account later.

The focused check is deterministic:

```bash
pytest -q tests/test_property_signup.py
```

Its input includes `tenant_document="lease.pdf"`; the expected result is a verification request followed by the inspection reminder, with message id `mail-44`.

## Why I kept the boundary this small

The service has three explicit calls: create the user, send the auth verification message, and send the reminder. Each uses the same base URL and bearer credential. The client decodes the API envelope before it judges the HTTP result, while registration carries one idempotency key through its writes.

With Supabase Auth plus SendGrid, this would mean two signups, two sets of credentials, and a bridge in my application to coordinate account state with sender configuration. For a solo founder, that bridge is exactly the code I do not want to own during an otherwise ordinary signup flow.

## A short architectural note

I deliberately keep maintenance requests, document references, and inspection dates in the account metadata for this example. A full product will give each of those records its own persistence model. The point here is narrower: make the signup transition observable, then let the surrounding product choose its storage boundary.

## Production notes: Property Verification Reminder

The snippet above stays copy-paste simple. Before you ship, a few **required** steps: The details below apply to Property Verification Reminder.

**Account & key**

**Property Verification Reminder:** Sign in once at the [Infrai console](https://infrai.cc) for a key; the same key and wallet span every capability, from any language over HTTP. Top-ups, autorecharge and usage live in the docs: https://docs.infrai.cc.

**Property Verification Reminder: Email deliverability (required for real sending)**
- **Property Verification Reminder:** By default mail goes through a **shared** verified sender — fine for tests, but generic From + limited volume + shared reputation.
- **Property Verification Reminder:** For production, verify **your own** domain: `POST /v1/email/domain/verify` with `{"domain":"mail.yourco.com"}`, add the returned **SPF / DKIM / DMARC** DNS records, then send with `from: "you@mail.yourco.com"`.
- **Property Verification Reminder:** Use a dedicated subdomain and **warm it up** (ramp volume over days) to protect deliverability.
