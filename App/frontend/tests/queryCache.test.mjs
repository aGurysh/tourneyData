import assert from "node:assert/strict"
import { test } from "node:test"
import { QueryObserver } from "@tanstack/react-query"
import {
  persistQueryClientRestore,
  persistQueryClientSave,
} from "@tanstack/react-query-persist-client"
import {
  CACHE_MAX_AGE,
  createQueryClient,
  queryPersistOptions,
} from "../src/lib/queryClient.ts"

const listKey = ["tournaments", "/api", "list"]
const detailKey = ["tournaments", "/api", "detail", 42]
const summary = { id: 42, name: "Test tournament" }

function mockStorage() {
  const values = new Map()
  const storage = {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
    removeItem: (key) => values.delete(key),
  }
  globalThis.window = { localStorage: storage }
  return storage
}

test("cached summaries survive reload without fetching fresh data again", async () => {
  mockStorage()
  const original = createQueryClient()
  const reloaded = createQueryClient()
  try {
    await original.fetchQuery({ queryKey: listKey, queryFn: async () => [summary], meta: { persist: true } })
    await original.fetchQuery({ queryKey: detailKey, queryFn: async () => summary, meta: { persist: true } })
    original.setQueryData(["catches", 42], [{ id: 1 }])
    await persistQueryClientSave({ queryClient: original, ...queryPersistOptions })
    await persistQueryClientRestore({ queryClient: reloaded, ...queryPersistOptions })

    assert.deepEqual(reloaded.getQueryData(listKey), [summary])
    assert.deepEqual(reloaded.getQueryData(detailKey), summary)
    assert.equal(reloaded.getQueryData(["catches", 42]), undefined)
    let requests = 0
    const data = await reloaded.fetchQuery({
      queryKey: detailKey,
      queryFn: async () => { requests++; return summary },
    })
    assert.deepEqual(data, summary)
    assert.equal(requests, 0)
    assert.equal(reloaded.getQueryData(["tournaments", "https://other-api", "detail", 42]), undefined)
  } finally {
    original.clear()
    reloaded.clear()
  }
})

test("expired, incompatible, and corrupt snapshots are discarded", async () => {
  const storage = mockStorage()
  const key = "tournament-analytics:query-cache"
  for (const snapshot of [
    JSON.stringify({ timestamp: Date.now() - CACHE_MAX_AGE - 1, buster: queryPersistOptions.buster }),
    JSON.stringify({ timestamp: Date.now(), buster: "old-version" }),
    "invalid JSON",
  ]) {
    storage.setItem(key, snapshot)
    const client = createQueryClient()
    // TanStack removes corrupt snapshots, then reports the restoration error
    // to the provider, which resumes normal fetching.
    const warn = console.warn
    const error = console.error
    console.warn = console.error = () => {}
    try {
      const restore = persistQueryClientRestore({ queryClient: client, ...queryPersistOptions })
      if (snapshot === "invalid JSON") {
        await assert.rejects(restore, SyntaxError)
      } else {
        await restore
      }
      assert.equal(storage.getItem(key), null)
      assert.equal(client.getQueryCache().getAll().length, 0)
    } finally {
      console.warn = warn
      console.error = error
      client.clear()
    }
  }
})


// swap with below test if we change 'static' staleTime
// test("refresh updates a cached summary and failed refresh retains its last data", async () => {
//   const client = createQueryClient()
//   let fail = false
//   let requests = 0
//   const observer = new QueryObserver(client, {
//     queryKey: detailKey,
//     queryFn: async () => {
//       requests++
//       if (fail) throw new Error("API unavailable")
//       return { ...summary, name: `Revision ${requests}` }
//     },
//     retry: false,
//   })
//   const unsubscribe = observer.subscribe(() => {})
//   try {
//     await observer.refetch()
//     const before = requests
//     await client.invalidateQueries({ queryKey: ["tournaments", "/api"] })
//     assert.equal(requests, before + 1)
//     const latest = client.getQueryData(detailKey)
//     fail = true
//     await observer.refetch()
//     assert.deepEqual(client.getQueryData(detailKey), latest)
//     assert.equal(observer.getCurrentResult().isRefetchError, true)
//   } finally {
//     unsubscribe()
//     client.clear()
//   }
// })

test("failed refresh retains its last data", async () => {
  const client = createQueryClient()
  let fail = false
  let requests = 0
  const observer = new QueryObserver(client, {
    queryKey: detailKey,
    queryFn: async () => {
      requests++
      if (fail) throw new Error("API unavailable")
      return { ...summary, name: `Revision ${requests}` }
    },
    retry: false,
  })
  const unsubscribe = observer.subscribe(() => {})
  try {
    await observer.refetch()
    const latest = client.getQueryData(detailKey)
    fail = true
    await observer.refetch()
    assert.deepEqual(client.getQueryData(detailKey), latest)
    assert.equal(observer.getCurrentResult().isRefetchError, true)
  } finally {
    unsubscribe()
    client.clear()
  }
})

test("blocked browser storage does not break fetching or in-memory caching", async () => {
  globalThis.window = {
    get localStorage() { throw new Error("Storage blocked") },
  }
  const client = createQueryClient()
  try {
    await client.fetchQuery({ queryKey: detailKey, queryFn: async () => summary, meta: { persist: true } })
    await persistQueryClientSave({ queryClient: client, ...queryPersistOptions })
    await persistQueryClientRestore({ queryClient: client, ...queryPersistOptions })
    assert.deepEqual(client.getQueryData(detailKey), summary)
  } finally {
    client.clear()
  }
})
