# Frontend commands

[Local setup and startup](../../README.md#start-locally). Run from `App/frontend`.
Use Node from `.nvmrc` and npm from `package.json` (`npm install --global npm@11.16.0`
if your npm version differs).

```bash
npm ci
npm run dev
npm test
npm run build
npm run preview
```

Vite proxies `/api` to `http://localhost:8000`. For a separately hosted API,
set `VITE_API_BASE_URL` before starting/building and allow the client origin in
the API's `CORS_ORIGINS`. [Production hosting](../deploy/README.md).

For dependency changes, use `npm install PACKAGE` or `npm update PACKAGE`, run
checks, and commit `package.json` and `package-lock.json` together.
