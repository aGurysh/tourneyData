# Frontend

Run `npm install` and `npm run dev` from this directory. Start the backend
on port 8000; Vite proxies `/api` requests to `http://localhost:8000`.

API helpers live in `src/api`. The tournament selector loads all pages from
`GET /tournaments`, ordered by the backend (newest tournament first).

For a separately hosted API, set `VITE_API_BASE_URL` to its base URL before
starting or building the frontend. Configure the backend's `CORS_ORIGINS` to
allow the frontend origin. Production hosting must either proxy `/api` to the
backend or build with `VITE_API_BASE_URL` set.

