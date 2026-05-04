import pandas as pd
from pathlib import Path

print("✅ Script started")

# =========================
# Paths
# =========================
DATA_PATH = Path("data")
RESULTS_PATH = Path("results")
RESULTS_PATH.mkdir(exist_ok=True)

# =========================
# Load CSV files
# =========================
menu = pd.read_csv(DATA_PATH / "menujackels.csv")
orders = pd.read_csv(DATA_PATH / "ordersjackels.csv")
order_items = pd.read_csv(DATA_PATH / "orderitemsjackels.csv")

print("✅ Files loaded")

# =========================
# Fix dates
# =========================
orders["order_date"] = pd.to_datetime(orders["order_date"])

# =========================
# Merge tables
# =========================
merged = (
    order_items
    .merge(menu, on="item_id", how="left")
    .merge(orders, on="order_id", how="left")
)

print(f"Merged rows: {len(merged)}")

# =========================
# Use line_total (IMPORTANT)
# =========================
merged["revenue"] = merged["line_total"]

# =========================
# Monthly Revenue
# =========================
merged["month"] = merged["order_date"].dt.to_period("M")

monthly_revenue = (
    merged
    .groupby("month")["revenue"]
    .sum()
    .reset_index()
)

monthly_revenue["month"] = monthly_revenue["month"].astype(str)

# =========================
# Save result
# =========================
output_file = RESULTS_PATH / "monthly_revenue.csv"
monthly_revenue.to_csv(output_file, index=False)

print("🔥 Monthly revenue saved to results/monthly_revenue.csv")
print(monthly_revenue.head())

# =========================
# Orders per Day of Week
# =========================

merged["day_of_week"] = merged["order_date"].dt.day_name()

orders_by_day = (
    merged
    .groupby("day_of_week")["order_id"]
    .nunique()
    .reset_index()
    .rename(columns={"order_id": "total_orders"})
)

# Order days correctly
day_order = [
    "Monday", "Tuesday", "Wednesday",
    "Thursday", "Friday", "Saturday", "Sunday"
]

orders_by_day["day_of_week"] = pd.Categorical(
    orders_by_day["day_of_week"],
    categories=day_order,
    ordered=True
)

orders_by_day = orders_by_day.sort_values("day_of_week")

# Save result
output_file = RESULTS_PATH / "orders_by_day_of_week.csv"
orders_by_day.to_csv(output_file, index=False)

print("🔥 Orders by day of week saved to results/orders_by_day_of_week.csv")
print(orders_by_day)

