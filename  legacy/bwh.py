import json
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from collections import defaultdict
import os
import matplotlib.dates as mdates

# Example JSON data
# data = [
#     ["John Smith", "2025-09-13T07:14:00", 18.5],
#     ["John Smith", "2025-09-13T07:48:00", 18.25],
#     ["John Smith", "2025-09-13T10:36:00", 17.75],
# ]

filename = "biteWindows-presque-batb-2026.png"
catches = []

if os.path.exists("catches.json"):
    print("Loading cached data from catches.json...")
    with open("catches.json", "r") as f:
        catches = json.load(f)
       
    # Convert timestamps back to datetime
    catches = [
        (
            record[0],
            datetime.fromisoformat(record[1]),
            record[2],
            record[3] if len(record) > 3 else None,
        )
        for record in catches
    ]


# Parse timestamps and bucket into 30-minute increments
buckets = defaultdict(float)

for _, dt, value, _species in catches:
    
    # Round down to nearest 30 minutes
    bucket_time = dt.replace(minute=(dt.minute // 30) * 30, second=0, microsecond=0)
    buckets[bucket_time] += 1

# Sort buckets by time
times = sorted(buckets.keys())
totals = [buckets[t] for t in times]

# Plot as a histogram/bar chart
plt.bar(times, totals, width=0.02)  # width in days (0.02 ~ 30 min on datetime axis)
plt.gcf().autofmt_xdate()

plt.xlabel("Time (5 min intervals)")

plt.gca().xaxis.set_major_formatter(mdates.DateFormatter("%I:%M"))
#plt.gca().xaxis.set_major_locator(mdates.MinuteLocator(interval=5))
plt.ylabel("Total Catch")
plt.title("Submitted fish per 30 minute interval")
print(f"Creating or updating {filename}")
plt.savefig(filename)
