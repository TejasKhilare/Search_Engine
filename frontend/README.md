# Frontend: DocSearch

React single-page app for uploading PDFs, hybrid search with a page-accurate PDF viewer, and
AI answers with clickable citations.

**Stack:** React 19 · Vite · React Router · Zustand · Axios · react-pdf (PDF.js)

## Run locally

Requires Node 20+ and the backend running (see [../backend/README.md](../backend/README.md)).

```bash
npm ci
npm run dev            # http://localhost:5173
```

The dev server proxies `/api` to the backend, so the browser sees one origin and auth cookies
work without any CORS setup. If the backend isn't on `http://127.0.0.1:8000`, create
`.env.local`:

```bash
VITE_PROXY_TARGET=http://127.0.0.1:8011
```

Other scripts: `npm run lint`, `npm run build` (output in `dist/`), `npm run preview`.

## Production build

Set `VITE_API_URL` to the backend's origin (no path), then build:

```bash
VITE_API_URL=https://api.example.com npm run build
```

If the frontend and API are on **different sites**, cookies must be cross-site. That requires:
- HTTPS on both
- `COOKIE_SAMESITE=none` and `COOKIE_SECURE=true` on the backend
- the frontend origin listed in the backend's `CORS_ORIGINS`

Serving both from one domain (for example, `/api` routed to the backend) avoids all of this.

## How it works

### Authentication
- **Cookie-based, no tokens in JavaScript.** Login sets HttpOnly cookies. The app only keeps
  the user and the CSRF token in memory (`store/authStore.js`).
- **CSRF header:** `shared/utils/axios.js` adds `X-CSRF-Token` to every POST, PUT, PATCH and
  DELETE.
- **Silent refresh:** on a `401`, the client refreshes the session once and retries the
  request. Concurrent 401s share a single refresh, because refresh tokens are single-use and
  parallel refreshes would look like token theft to the server.
- **Page reload:** `App.jsx` calls `/auth/refresh` to restore the session.
- **Route guards:** `ProtectedRoute` and `GuestRoute` wait for that check before redirecting.

### Documents
- Uploads show a progress percentage.
- One shared poller (`hooks/useDocumentPolling.js`) tracks pending and processing documents,
  announces when each is ready or failed, and stops by itself.
- Failed documents show the reason and a **Retry** button.
- Clicking a ready document **scopes search and AI answers to it**. Click it again, or the ×
  on the scope chip, to go back to all documents.

### Search
- Results come one per page and are best first.
- Snippets are highlighted from character ranges returned by the API, never from HTML, so
  document text can't inject markup.
- Clicking a result opens the PDF at that page. The PDF streams from `/documents/{id}/file`
  with the session cookie, and the PDF.js worker is bundled with the app.

### AI Ask
- Answers stream in over Server-Sent Events, read with `fetch` because `EventSource` can't
  send POST requests.
- A Stop button cancels the answer while it streams.
- `[n]` markers become buttons that open the cited page in a preview. Cited sources are marked
  in the source list.

## Layout

```
src/
  app/           App (session bootstrap), routes, route guards
  features/
    auth/        login/register pages, auth API
    documents/   sidebar, list, upload, documents API
    search/      search page, snippet, PDF viewer + highlight layer
    rag/         AI page, answer panel, source preview, streaming API
  hooks/         useAuth, useDocumentPolling, useSearch, useRag
  store/         authStore, documentStore (Zustand)
  shared/        API client, layout, navbar, scope chip, toasts
```
