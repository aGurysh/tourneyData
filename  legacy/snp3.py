from datetime import timedelta
from collections import defaultdict
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from scrape import scrape_tourneyx

filename = "liveStandings.png"  # output filename
#URL = "https://tourneyx.com/leaderboard/standings/kawpa-bass-on-the-bay-11"

URL ="https://tourneyx.com/leaderboard/standings/kawpa-bass-on-the-bay-11"
max_angler = 73
highlight_anglers = [  "Adam Gurysh"]  # <- list of anglers to highlight

# List to hold all catches: (angler_name, timestamp, length, species)
catches = scrape_tourneyx(URL, max_anglers=max_angler)



# --- Build cumulative totals per angler ---
angler_totals = defaultdict(list)
for angler, dt, length, _species in sorted(catches, key=lambda x: x[1]):
    prev_total = angler_totals[angler][-1][1] if angler_totals[angler] else 0
    angler_totals[angler].append((dt, prev_total + length))

# --- Aggregate at 5-minute intervals ---
if not catches:
    exit()
print("Processing data...")

all_times = [dt for _, dt, _, _ in catches]
start_time = min(all_times) - timedelta(minutes=10)
end_time = max(all_times) + timedelta(minutes=10)
interval = timedelta(minutes=5)

time_slots = []
t = start_time
while t <= end_time:
    time_slots.append(t)
    t += interval

angler_series = defaultdict(list)
for angler, totals in angler_totals.items():
    idx = 0
    current_total = 0
    for slot in time_slots:
        while idx < len(totals) and totals[idx][0] <= slot:
            current_total = totals[idx][1]
            idx += 1
        angler_series[angler].append(current_total)

# --- Plot the chart with highlighted anglers ---
plt.figure(figsize=(12, 6))

# Plot everyone else first in gray
for angler, series in angler_series.items():
    if angler not in highlight_anglers:
        plt.plot(time_slots, series, marker='o', color='gray', alpha=0.5, linewidth=1)

# Plot highlighted anglers on top with unique colors
colors = ["red", "blue", "green", "orange", "purple", "brown", "pink", "olive", "cyan", "magenta"]
i =0
for angler in highlight_anglers:
    if angler in angler_series:
        plt.plot(
            time_slots,
            angler_series[angler],
            marker='o',
            color=colors[i % len(colors)],
            linewidth=2.5,
            label=angler
        )
        i += 1


# --- Compute standings after each catch ---
# Sort all catches by time
catches_sorted = sorted(catches, key=lambda x: x[1])

# Track running totals
running_totals = defaultdict(float)
standings_over_time = []  # list of (timestamp, {angler: total})

for angler, dt, length, _species in catches_sorted:
    running_totals[angler] += length
    # snapshot standings at this time
    standings_over_time.append((dt, dict(running_totals)))

def get_rank(standings, angler):
    # Sort by total descending
    sorted_anglers = sorted(standings.items(), key=lambda x: x[1], reverse=True)
    for i, (a, _) in enumerate(sorted_anglers, start=1):
        if a == angler:
            return i
    return None








plt.xlabel("Time")
plt.ylabel("Cumulative Length")
plt.title("Live Standings")
#plt.xticks(rotation=45)

# Format x-axis labels to show only time
plt.gca().xaxis.set_major_formatter(mdates.DateFormatter("%I:%M"))
plt.gca().xaxis.set_major_locator(mdates.MinuteLocator(interval=25))
plt.gca().yaxis.set_major_locator(plt.MaxNLocator(24))


for angler in highlight_anglers:
    if angler not in angler_series:
        continue
    
    # Go through all their catches
    angler_catches = [c for c in catches_sorted if c[0] == angler]
    for angler_name, dt, length, _species in angler_catches:
        # Get standings *before* and *after* this catch
        # Find the snapshot just before this dt
        prev_snap = None
        for snap_dt, standings in standings_over_time:
            if snap_dt < dt:
                prev_snap = standings
            else:
                break
        after_snap = None
        for snap_dt, standings in standings_over_time:
            if snap_dt == dt:
                after_snap = standings
                break

        if prev_snap:
            prev_rank = get_rank(prev_snap, angler)
        else:
            prev_rank = None
        after_rank = get_rank(after_snap, angler) if after_snap else None

        # Get angler’s current total after this catch
        total = after_snap[angler] if after_snap else 0

        # Annotate near the point
        if after_rank is not None:
            plt.text(
                dt, total + 2,  # small vertical offset
                f"{prev_rank}→{after_rank}",
                fontsize=8,
                ha="center",
                va="bottom",
                color="black",
                bbox=dict(boxstyle="round,pad=0.2", fc="white", alpha=0.6, lw=0)
            )



plt.legend(loc='upper left')
plt.tight_layout()
print(f"Creating or updating {filename}")
plt.savefig(filename)
