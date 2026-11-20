# Protected Gemini gateway (Vercel)

The dashboard supports two ways to run Gemini evaluations:

- **Bring your own key:** enter a Gemini key in Configuration; the browser calls Google directly as before.
- **Protected server key:** enter a separate operator access token in Configuration; the browser calls `POST /api/gemini`, and only the server uses `GEMINI_API_KEY`.

## Required production secrets

Set both in Vercel project Settings → Environment Variables, Production, Sensitive:

- `GEMINI_API_KEY`: your existing Google Gemini key (already configured).
- `LAB_RUNNER_TOKEN`: a **new, independent, random 32+ character secret**. Do not reuse the Gemini key or any GitHub/Vercel token. Generate it with a trusted password manager.

Redeploy after adding the second secret. Then enter the **operator token**, not the Gemini key, in Configuration → Protected Vercel Gemini runner. The token stays in page memory; never commit it, put it in a URL, or share it publicly.

## Security boundaries

The endpoint is disabled unless **both** secrets exist. It uses constant-time token comparison, POST-only requests, a limited model allowlist, request size limits, message count and text length limits, a 45-second timeout, and non-diagnostic upstream error responses. The Gemini key is never returned to clients.

**This is an operator-only endpoint, not a public API.** The token is an access credential; if it leaks, rotate it immediately. A shared token does not provide per-user quotas, identity, or persistent distributed rate limits. Before granting access to other people, add identity-based authorization and durable per-user quota enforcement. Avoid distributing the operator token.

The existing frontend test suite should be run before merging; this branch has not yet been verified in a live preview deployment.
