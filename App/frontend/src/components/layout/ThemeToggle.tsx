import { useState } from "react"
import { Button } from "@/components/ui/button"

export default function ThemeToggle() {
  const [dark, setDark] = useState(() => document.documentElement.classList.contains("dark"))

  function toggleTheme() {
    const nextDark = !dark
    document.documentElement.classList.toggle("dark", nextDark)
    setDark(nextDark)
    try {
      localStorage.setItem("theme", nextDark ? "dark" : "light")
    } catch {
      // The toggle still works when browser storage is unavailable.
    }
  }

  return (
    <Button
      variant="outline"
      size="lg"
      type="button"
      onClick={toggleTheme}
      aria-label="Dark mode"
      aria-pressed={dark}
      title={`Switch to ${dark ? "light" : "dark"} mode`}
    >
      <svg aria-hidden="true" className="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
        {dark ? (
          <>
            <circle cx="12" cy="12" r="4" />
            <path d="M12 2v2m0 16v2M2 12h2m16 0h2M4.93 4.93l1.42 1.42m11.3 11.3 1.42 1.42M4.93 19.07l1.42-1.42m11.3-11.3 1.42-1.42" />
          </>
        ) : (
          <path d="M20.9 13A9 9 0 0 1 11 3.1 9 9 0 1 0 20.9 13Z" />
        )}
      </svg>
      {dark ? "Light mode" : "Dark mode"}
    </Button>
  )
}
