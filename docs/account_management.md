# Account management (Slice 25)

Email verification, password reset, and organization invitation groundwork. Real trading remains **disabled**; all execution stays **paper-only**.

## Email verification

1. **Register** creates a hashed verification token (48h default) and sends email when `EMAIL_SEND_ENABLED=true`.
2. **Confirm**: `POST /auth/verify-email/confirm` with `{ "token": "..." }`.
3. **Resend**: `POST /auth/verify-email/request` (rate limited: 5/hour per IP). Authenticated users resend to their profile email; unauthenticated requests may pass `{ "email": "..." }`.
4. **Login** returns `user.email_verified`. Staging/production default to requiring verified email (`must_verify_email`); local dev allows unverified login unless `REQUIRE_EMAIL_VERIFIED=true`.

Frontend: `/verify-email`, banner on Settings, redirect after register when unverified.

## Password reset

1. **Request**: `POST /auth/password-reset/request` — always returns a generic message (no email enumeration).
2. **Confirm**: `POST /auth/password-reset/confirm` with token + new password.
3. Tokens are **hashed**, **expire** (2h default), **one-time use**.
4. Successful reset **revokes all refresh tokens** and denylists the current access token when provided.

Frontend: `/forgot-password`, `/reset-password?token=...`

## Organization invitations (groundwork)

| Endpoint | Role | Description |
|----------|------|-------------|
| `POST /organizations/invitations` | OWNER | Create invite (TRADER/VIEWER) |
| `GET /organizations/invitations` | OWNER | List invites |
| `POST /organizations/invitations/{id}/accept` | Authenticated | Existing user accepts (email must match) |
| `POST /organizations/invitations/{id}/revoke` | OWNER | Revoke pending invite |

Invite tokens are hashed at rest. **New-user signup via invite** is documented as a future slice.

## Email provider modes

| `EMAIL_PROVIDER` | Behavior |
|------------------|----------|
| `mock` (default) | In-memory capture; safe for tests/local |
| `smtp` | Placeholder — configure `SMTP_HOST` |
| `resend` | Placeholder — configure `RESEND_API_KEY` |
| `sendgrid` | Placeholder — configure `SENDGRID_API_KEY` |

Status appears on `GET /providers/status` (`kind: email`). Email bodies are **never logged**; only template name and redacted recipient domain.

## Configuration

```bash
EMAIL_PROVIDER=mock
EMAIL_FROM_ADDRESS=noreply@alphatrade.local
EMAIL_BASE_URL=http://localhost:3000
EMAIL_SEND_ENABLED=true
REQUIRE_EMAIL_VERIFIED=   # unset → true in staging/production, false in local
```

## Security

- Verification/reset/invite tokens: SHA-256 at rest, never logged.
- Audit: verification sent/completed/failed, reset requested/completed/failed, invite created/accepted/revoked.
- Rate limits on resend and password-reset request.

## Known limitations

- SMTP/Resend/SendGrid delivery not fully wired (mock for dev).
- No invite acceptance flow for users without an existing account.
- No admin UI for org member management beyond invitation list.
- Email verification not enforced on every sensitive route in local dev.

## Verification

```bash
cd backend && uv run pytest tests/test_account_management.py -q
cd frontend && npm run test -- --run src/components/account src/app/(public)/forgot-password src/app/(public)/reset-password src/app/(app)/settings src/app/(app)/invitations
```
