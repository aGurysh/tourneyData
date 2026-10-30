import { QueryClient } from "@tanstack/react-query"
import type { Query } from "@tanstack/react-query"
import { createAsyncStoragePersister } from "@tanstack/query-async-storage-persister"
import { removeOldestQuery } from "@tanstack/react-query-persist-client"

export const CACHE_MAX_AGE = 24 * 60 * 60 * 1000 // 24hr

export function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: "static", // db modified infrequently, just gc after 24h
        gcTime: CACHE_MAX_AGE,
        retry: 1,
      },
    },
  })
}

export const queryClient = createQueryClient()

export const queryPersistOptions = {
  persister: createAsyncStoragePersister({
    key: "tournament-analytics:query-cache",
    storage: {
      getItem: (key: string) => {
        try {
          return window.localStorage.getItem(key)
        } catch {
          return null
        }
      },
      // The persister catches write failures and evicts older cached queries.
      setItem: (key: string, value: string) => window.localStorage.setItem(key, value),
      removeItem: (key: string) => {
        try {
          window.localStorage.removeItem(key)
        } catch {
          // In-memory caching still works when browser storage is blocked.
        }
      },  
    },  
    retry: removeOldestQuery,  
  }),  
  maxAge: CACHE_MAX_AGE,
  buster: "summary-v1",
  dehydrateOptions: {
    shouldDehydrateQuery: (query: Query) =>
      query.meta?.persist === true && query.state.status === "success",
    shouldDehydrateMutation: () => false,
  },
}
