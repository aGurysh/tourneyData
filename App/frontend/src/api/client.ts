export const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || "/api").replace(/\/$/, "")

export class ApiError extends Error {
  constructor(public readonly status: number) {
    super(`API request failed (${status})`)
    this.name = "ApiError"
  }
}

export async function get<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    headers: { Accept: "application/json" },
    signal,
  })

  if (!response.ok) {
    throw new ApiError(response.status)
  }

  return response.json() as Promise<T>
}
