import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs"

export default function App() {
  return (
    <div className="min-h-svh bg-background text-foreground">
      <header className="border-b bg-card">
        <div className="mx-auto max-w-6xl px-4 py-6 sm:px-8">
          <p className="text-lg font-semibold tracking-tight">
            Tournament Analytics
          </p>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-6 sm:px-8 sm:py-8">
        <Tabs defaultValue="single" className="gap-8">
          <TabsList aria-label="Analytics views" className="w-full group-data-horizontal/tabs:h-auto sm:w-fit">
            <TabsTrigger value="single" className="whitespace-normal px-4 py-2">
              Single tournament summary
            </TabsTrigger>
            <TabsTrigger value="aggregated" className="whitespace-normal px-4 py-2">
              Aggregated results
            </TabsTrigger>
          </TabsList>

          <TabsContent value="single">
            <h1 className="text-2xl font-semibold tracking-tight">
              Single tournament summary
            </h1>
            <p className="mt-2 text-sm text-muted-foreground">
              Tournament standings and catch activity will appear here.
            </p>
          </TabsContent>

          <TabsContent value="aggregated">
            <h1 className="text-2xl font-semibold tracking-tight">
              Aggregated results
            </h1>
            <p className="mt-2 text-sm text-muted-foreground">
              Trends across tournaments, waterbodies, and species will appear here.
            </p>
          </TabsContent>
        </Tabs>
      </main>
    </div>
  )
}
