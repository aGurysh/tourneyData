import { useId } from "react"
import { Combobox } from "@base-ui/react/combobox"
import { Check, ChevronsUpDown } from "lucide-react"

export function AnglerCombobox({ names, value, onValueChange }: {
  names: string[]
  value: string
  onValueChange: (value: string) => void
}) {
  const id = useId()
  return (
    <div className="max-w-sm space-y-2">
      <label htmlFor={id} className="text-sm font-medium">Highlighted angler</label>
      <Combobox.Root items={names} value={value} autoHighlight
        onValueChange={(name) => { if (name !== null) onValueChange(name) }}>
        <div className="relative">
          <Combobox.Input id={id} placeholder="Search anglers…"
            className="h-9 w-full rounded-lg border border-input bg-background px-3 pr-9 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring" />
          <Combobox.Trigger aria-label="Show anglers" className="absolute inset-y-0 right-0 flex w-9 items-center justify-center text-muted-foreground">
            <ChevronsUpDown className="size-4" />
          </Combobox.Trigger>
        </div>
        <Combobox.Portal>
          <Combobox.Positioner sideOffset={4} className="z-50">
            <Combobox.Popup className="w-[var(--anchor-width)] rounded-lg border bg-popover p-1 text-popover-foreground shadow-md">
              <Combobox.Empty className="px-3 py-2 text-sm text-muted-foreground">No anglers found.</Combobox.Empty>
              <Combobox.List className="max-h-64 overflow-y-auto overscroll-contain">
                {(name: string) => (
                  <Combobox.Item key={name} value={name} className="flex cursor-default items-center justify-between gap-3 rounded-md px-3 py-2 text-sm outline-none data-highlighted:bg-accent data-highlighted:text-accent-foreground">
                    {name}<Combobox.ItemIndicator><Check className="size-4" /></Combobox.ItemIndicator>
                  </Combobox.Item>
                )}
              </Combobox.List>
            </Combobox.Popup>
          </Combobox.Positioner>
        </Combobox.Portal>
      </Combobox.Root>
    </div>
  )
}
