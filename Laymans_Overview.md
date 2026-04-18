# Gold Trading Bot - Simple Overview

This guide explains how your automated trading system works in plain English.

## 🚀 How to Run the System
You only need to do two things every day:

1. **Step 1 (Before Market):** Run `premarket.py`
   - This "wakes up" the bot and tells it to look at the latest gold prices and levels.
2. **Step 2 (At Market Open):** Run `main.py`
   - This starts the actual trading. You only need to run it **once**/day. It will either check on an existing trade or set up new ones for the day and then finish.

---

## 🧠 What the Bot Does (Section by Section)

### 🛠️ 1. The Daily Check-up (Maintenance)
Every time you start the bot, it first looks at your "Memory" (the `trading_state.json` file) to see what happened yesterday.
- **Morning Cleanup**: If it's a new day and you have leftover orders that never triggered, the bot automatically **cancels** them for you and starts with a clean slate.
- **How it "sees" triggers:** The bot sends a request to Upstox for each order ID. If Upstox replies that the status is **"TRIGGERED"**, the bot knows the market price reached your level.
- **Cross-Cancellation:** If a Buy order is hit, it automatically cancels your Sell orders so you don't get entered twice.
- **Locking in Profits:** If your first lot (Target) makes money and closes, the bot adjusts the safety level (Stop Loss) for your second lot to protect your gains.

### 📊 2. The Strategy (Analysis)
If you don't have a trade running, the bot prepares a new plan:
- **Daily Levels:** It looks at the Highs and Lows of the last 4 days to find the strongest "breakout" points.
- **Reliable Open Detection**: At 9:00:05 AM, the bot uses a special "Quote Check" (and retries if needed) to find the exact opening price immediately.
- **Gap Protection:** If the price "Gaps" (jumps) at opening, the bot waits until 9:15 AM to calculate its entry based on the market's first 15 minutes of action.
- **COMEX Gatekeeper (Optional)**: If enabled, the bot will wait for a "spark" from the international gold market (COMEX). It won't place MCX orders until gold breaks out globally, ensuring your trade is backed by global momentum.

### 📝 3. The Execution (Placement)
The bot doesn't just place one order; it splits your entry into two parts:
- **Lot 1 (The Sprinter):** This lot has a specific profit goal. It's meant to "get in and get out" with a quick profit.
- **Lot 2 (The Runner):** This lot stays in the market. Its job is to capture big trends. The bot will follow this trade day-by-day, moving the Stop Loss to lock in profits as gold moves in your favor.

---

## 📂 Key Files to Know

| File Name | Purpose |
| :--- | :--- |
| `config.py` | **Settings**. Adjust `TOTAL_LOTS` here to change your order size. |
| `trading_state.json` | The bot's **Memory**. It stores order IDs and current trade status. |
| `GOLD_MARKET.log` | The bot's **Diary**. Read this to see exactly what the bot did today. |
| `premarket_data.json` | The **Plan**. It stores the calculation levels for the day. |
| `System_flowchart.md` | The **Map**. A visual flow of every decision the bot makes. |

## 💡 Important Tips
- **Run Once:** You do NOT need to keep the bot running all day. Its new "Single Run" logic means it does its job and closes.
- **Logs:** If you are ever unsure what happened, look at `Logs/GOLD_MARKET.log`. It will tell you exactly which side triggered and what was cancelled.
- **Internet:** Ensure you have a stable internet connection when running the scripts so they can talk to Upstox.
