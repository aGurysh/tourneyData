import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/layout/Tabs"
import SingleSummary from "@/components/SingleSumamry/SingleSummary"

export default function App() {
  return (
    <Tabs defaultValue="single" className="min-h-svh gap-0 bg-background text-foreground">
      <header className="border-b bg-card">
        <div className="mx-auto grid max-w-6xl items-center gap-4 px-4 py-6 sm:px-8 lg:grid-cols-[1fr_auto_1fr]">
          <p className="whitespace-nowrap text-lg font-semibold tracking-tight">
             Kayak Tournament Advantage
          </p>
          <div className="flex min-w-0 overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
            <TabsList variant="line" aria-label="Analytics views" className="mx-auto shrink-0 group-data-horizontal/tabs:h-auto">
              <TabsTrigger value="single" className="whitespace-nowrap px-4 py-2">
                Single Tournament Summary
              </TabsTrigger>
              <TabsTrigger value="aggregated" className="whitespace-nowrap px-4 py-2">
                Aggregated Results
              </TabsTrigger>
            </TabsList>
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-6xl px-4 py-6 sm:px-8 sm:py-8">
          <TabsContent value="single">
            <SingleSummary />
          </TabsContent>

          <TabsContent value="aggregated">
            <h1 className="text-2xl font-semibold tracking-tight">
              Aggregated results
            </h1>
            <p className="mt-2 text-sm text-muted-foreground">
              Trends across tournaments, waterbodies, and species will appear here.
            </p>
          </TabsContent>
      </main>
    </Tabs>
  )
}
