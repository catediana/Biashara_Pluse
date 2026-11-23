# Biashara Pulse frontend

React, TypeScript, Vite, Tailwind CSS, React Router, TanStack Query, React Hook
Form, and Zod frontend application.

## Development

```powershell
npm install
npm run dev
```

By default, Vite proxies `/api` requests to `http://127.0.0.1:8000`. Set
`VITE_API_PROXY_TARGET` to use another backend address, or
`VITE_API_BASE_URL` when the API should be reached directly from the browser.
Cross-origin deployments must configure the backend's session cookie, CSRF, and
CORS settings appropriately.

The API client uses the backend's secure session-cookie and CSRF flow. It does
not store credentials or auth tokens in browser storage. The active organisation
UUID is kept in `sessionStorage` and sent as `X-Organisation-ID`.

## Authentication

Guest authentication screens are available at `/login`, `/signup`,
`/forgot-password`, and `/reset-password/:uidb64/:token`. Registration signs the
new user in with the returned session cookie. Password reset requests always
show a generic confirmation so the interface does not reveal whether an email
address has an account.

## Checks

```powershell
npm run build
npm test
npm run lint
```
