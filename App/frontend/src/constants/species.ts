// Keep complete Tailwind class names here so they are included in the build.
export const SPECIES_COLORS: Readonly<Partial<Record<string, {
  readonly background: string
  readonly text: string
}>>> = {
  "Largemouth Bass": {
    background: "bg-[#196e36]",
    text: "text-[#FFFF]",
  },
  "Smallmouth Bass": {
    background: "bg-[#885726]",
    text: "text-[#FFFF]",
  },
}

