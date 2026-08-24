# QQQ / TQQQ Quantitative Trading Bot (V22.1)

An automated regime-switching quantitative trading strategy designed for **QQQ** (Invesco QQQ Trust) and **TQQQ** (ProShares UltraPro QQQ). 

The bot runs on a daily schedule via **GitHub Actions**, fetches real-time market data through `yfinance`, dynamically calculates regime-based asset allocations, and sends formatted inspection reports directly to **Telegram**.

---

## 🚀 Key Features

* **Dynamic Regime Switching:** Automatically shifts allocations across 6 market regimes based on moving averages (MA20/MA200), historical drawdowns, and volume breakout signals.
* **Anti-V Reversal Filter:** Implements a mandatory 2-day cool-down period and MA20 slope verification to prevent false-breakout whipsaws during high-volatility market transitions.
* **Fractional Share Allocation:** Computes exact decimal share amounts to maximize capital efficiency down to the penny.
* **Fully Automated Daily Reports:** Scheduled execution via GitHub Actions with rich Telegram push notifications displaying:
  * Current Market Regime & Status Emoji
  * Account Total Equity & Remaining Cash Buffer
  * Live Asset Allocation (% vs. Target %)
  * Concrete Action Suggestions (Buy / Sell / Hold with exact share units)

---

## 📊 Strategy Regimes & Allocations

| State | Regime Condition | Target Allocation |
| :--- | :--- | :--- |
| **`NORMAL`** | Price > MA200 & Drawdown > -10% | **45% QQQ / 45% TQQQ / 10% Cash** |
| **`ZONE_BATTLE_ATTACK`** | Drawdown -10% to -30% & Price > MA20 | **0% QQQ / 99% TQQQ / 1% Cash** |
| **`ZONE_DESPAIR_TQQQ`** | Price < MA200 & Drawdown ≤ -30% | **0% QQQ / 99% TQQQ / 1% Cash** |
| **`ZONE_BATTLE_DEFEND`** | Drawdown -10% to -30% & Price < MA20 | **90% QQQ / 0% TQQQ / 10% Cash** |
| **`TOP_ESCAPE`** | Near ATH (top 5%) + 2x Vol Spike + Red Day | **90% QQQ / 0% TQQQ / 10% Cash** |
| **`BEAR_CASH`** | Price < MA200 & Drawdown > -10% (Trap Zone) | **0% QQQ / 0% TQQQ / 100% Cash** |

---

## ⚙️ Telegram Alert Format

Every trading day, the bot outputs a unified inspection brief:

```text
🟢 【每日巡检】
当前状态: NORMAL

⏰ 报告时间(北京): 2026-08-24 22:00:00
💰 账户总资产: $10000.00
🏦 当前现金: $1000.00 (10.0% | 目标: 10.0%)
📈 QQQ: $713.44 | TQQQ: $71.17

📊 资产占比 (当前 ➜ 目标):
  • QQQ: $4500.00 (45.0% ➜ 45.0%)
  • TQQQ: $4500.00 (45.0% ➜ 45.0%)
  • 现金: $1000.00 (10.0% ➜ 10.0%)

🎯 操作建议:
  • QQQ: 🟢 买入 6.3075 股 (目标: 45.0% | 6.3075股)
  • TQQQ: 🟢 买入 63.2298 股 (目标: 45.0% | 63.2298股)
