import { useId } from "react"
import { Combobox } from "@base-ui/react/combobox"
import { Check, ChevronsUpDown, X } from "lucide-react"

export function AnglerCombobox({ anglers, value, onValueChange }: {
  anglers: { id: number; name: string }[]
  value: number[]
  onValueChange: (value: number[]) => void
}) {
  const id = useId()
  const ids = anglers.map((angler) => angler.id)
  const label = (id: number) => {
    const angler = anglers.find((item) => item.id === id)
    if (!angler) return String(id)
    return anglers.filter((item) => item.name === angler.name).length > 1
      ? `${angler.name} (#${id})` : angler.name
  }
  return (
    <div className="max-w-xl space-y-2">
      <label htmlFor={id} className="text-sm font-medium">Highlighted anglers</label>
      <Combobox.Root multiple items={ids} itemToStringLabel={label} value={value} autoHighlight onValueChange={onValueChange}>
        <div className="relative pt-1">
          <Combobox.Chips className="flex min-h-9 flex-wrap items-center gap-1 rounded-lg border border-input bg-background p-1 pr-9 focus-within:ring-2 focus-within:ring-ring">
            <Combobox.Value>
              {(selected: number[]) => selected.map((anglerId) => (
                <Combobox.Chip key={anglerId} className="flex max-w-full items-center gap-1 rounded-md bg-muted px-2 py-1 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring">
                  <span className="truncate">{label(anglerId)}</span>
                  <Combobox.ChipRemove aria-label={`Remove ${label(anglerId)}`} className="rounded-sm p-0.5 hover:bg-accent focus-visible:outline-2 focus-visible:outline-ring">
                    <X className="size-3" />
                  </Combobox.ChipRemove>
                </Combobox.Chip>
              ))}
            </Combobox.Value>
            <Combobox.Input id={id} placeholder="Search anglers…"
              className="h-7 min-w-32 flex-1 bg-transparent px-2 text-sm outline-none" />
          </Combobox.Chips>
          <Combobox.Trigger aria-label="Show anglers" className="absolute inset-y-0 right-0 flex w-9 items-center justify-center text-muted-foreground">
            <ChevronsUpDown className="size-4" />
          </Combobox.Trigger>
        </div>
        <Combobox.Portal>
          <Combobox.Positioner sideOffset={4} className="z-50">
            <Combobox.Popup className="w-[var(--anchor-width)] rounded-lg border bg-popover p-1 text-popover-foreground shadow-md">
              <Combobox.Empty className="px-3 py-2 text-sm text-muted-foreground">No anglers found.</Combobox.Empty>
              <Combobox.List className="max-h-64 overflow-y-auto overscroll-contain">
                {(anglerId: number) => (
                  <Combobox.Item key={anglerId} value={anglerId} className="flex cursor-default items-center justify-between gap-3 rounded-md px-3 py-2 text-sm outline-none data-highlighted:bg-accent data-highlighted:text-accent-foreground">
                    {label(anglerId)}<Combobox.ItemIndicator><Check className="size-4" /></Combobox.ItemIndicator>
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
