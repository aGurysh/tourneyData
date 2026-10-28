import { useEffect, useState } from "react"

// Persist UI pereferences 
// API response data are persisted by TanStack Query
export function usePersistentState<T extends string>(
  key: string,
  defaultValue: T,
  isValid: (value: string) => value is T,
) {
  const [value, setValue] = useState<T>(() => {
    try {
      const saved = localStorage.getItem(key)
      if (saved !== null && isValid(saved)) return saved
    } catch {
      // Browser storage may be blocked; keep using in-memory state.
    }
    return defaultValue
  })

  useEffect(() => {
    try {
      localStorage.setItem(key, value)
    } catch {
      // A storage failure should not prevent changing the selection.
    }
  }, [key, value])

  return [value, setValue] as const
}
