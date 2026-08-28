# Security policy

## Supported version

Only the latest commit on `main` is supported.

## Reporting a vulnerability

Do not open a public issue containing a bot token, database URL, Telegram ID, private
message, exploit payload or other sensitive information. Contact the repository owner
privately and include only the minimum reproduction details needed.

If a token is exposed, revoke it first, rotate the Railway variable, redeploy, and then
investigate the logs and audit trail. Do not wait for a code fix before revoking a secret.

## Operational expectations

- Production secrets must be sealed Railway variables.
- Moderator and Railway/GitHub accounts must use two-factor authentication.
- Database backups and restore tests must be scheduled.
- Dependabot, CodeQL, secret scanning and CI alerts must be reviewed.
- Production data must not be copied into local or staging environments.
