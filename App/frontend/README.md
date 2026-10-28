# Frontend

Run `npm install` and `npm run dev` from this directory. Start the backend
on port 8000; Vite proxies `/api` requests to `http://localhost:8000`.

API helpers live in `src/api`. The tournament selector loads all pages from
`GET /tournaments`, ordered by the backend (newest tournament first).

For a separately hosted API, set `VITE_API_BASE_URL` to its base URL before
starting or building the frontend. Configure the backend's `CORS_ORIGINS` to
allow the frontend origin. Production hosting must either proxy `/api` to the
backend or build with `VITE_API_BASE_URL` set.

Tournament lists and summaries use TanStack Query. Responses are fresh for five
minutes, with stale data displayed while a background refresh runs. The Refresh
button refreshes the list and active summary and marks other summaries stale.
Failed background requests retain visible cached data and expose a retry action.

Successful list and summary queries are persisted to localStorage under
`tournament-analytics:query-cache`, with a 24-hour maximum snapshot age and
`summary-v1` cache version. Query keys include the API URL. Browser storage
failures fall back to in-memory caching; storage quota failures evict older
queries before retrying. Catch datasets are not persisted by this setup.

Cache configuration lives in `src/lib/queryClient.ts`, and tournament query
definitions live in `src/api/queries.ts`. Increment the cache version when
changing response formats. Existing tab and tournament-selection preferences
remain separate from the response cache.

The Single Tournament Summary also loads every page of
`GET /tournaments/{id}/catches` for the Bite Windows card. Catches are cached
in memory by TanStack Query, excluded from localStorage persistence, and
refreshed by the same Refresh button.

`src/components/charts/BiteWindowsCard.tsx` displays precomputed half-hour counts
without knowing about tournaments or API requests. `src/lib/biteWindows.ts`
groups timestamp/timezone samples by local time of day, combining dates and
retaining empty bins between the first and last populated bins. Each bin includes
its start and excludes its end (7:30 belongs to 7:30–8:00). Invalid timestamps or
timezones are excluded and counted. The single-summary adapter supplies the
tournament timezone; future aggregations can supply each catch's local timezone.
Species and minimum-length filters operate on the fetched catch records before
binning. Species options come from the tournament's unfiltered catches, with
All species including catches with unknown species. Unknown species is also
available as an option when present. Filtering does not refetch the dataset.

Run cache behavior checks with `npm test` using Node.js 22.18+ (native TypeScript
support). Run `npm run build` for TypeScript and production-bundle checks.

