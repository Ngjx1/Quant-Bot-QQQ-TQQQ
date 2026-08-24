import yfinance as yf
import pandas as pd
import requests
import datetime
import os

class QuantStrategy:
    def __init__(self):
        # Strategy Parameters
        self.ma_long_window = 200
        self.ma_short_window = 20
        self.vol_window = 60
        self.vol_factor = 2.0
        self.high_zone = 0.95
        
        # State Management
        self.state_label = "NORMAL"
        self.ath_price = 0.0
        self.risk_off_days = 0
        self.min_risk_off_days = 2
        
        # Account Balance & Holdings (Reads dynamically from GitHub Variables)
        self.equity = float(os.environ.get("ACCOUNT_EQUITY", "600.0"))
        # Changed int() to float() to support fractional inputs like "2.27"
        self.qty_q = float(os.environ.get("HOLDING_QQQ", "0.0"))
        self.qty_t = float(os.environ.get("HOLDING_TQQQ", "0.0"))

        # Telegram Setup (Reads from GitHub Secrets, falls back to your provided keys for testing)
        self.bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "8845865365:AAFd76bQzxBJDKMgMlrKb44pmVRUBb99QlE")
        self.chat_id = os.environ.get("TELEGRAM_CHAT_ID", "8578262364")

    def fetch_data(self, ticker):
        """Fetches historical daily data using yfinance."""
        print(f"[DATA] Fetching data for {ticker}...")
        ticker_obj = yf.Ticker(ticker)
        data = ticker_obj.history(period="2y", interval="1d")
        return data

    def calculate_indicators(self, data):
        """Calculates MAs and Volume averages using Pandas."""
        data['MA200'] = data['Close'].rolling(window=self.ma_long_window).mean()
        data['MA20'] = data['Close'].rolling(window=self.ma_short_window).mean()
        data['Vol_MA'] = data['Volume'].rolling(window=self.vol_window).mean()
        return data

    def _init_ath_price(self, data):
        recent_year = data.tail(252)
        self.ath_price = float(recent_year['High'].max())
        print(f"[INIT] ATH initialized: {self.ath_price:.2f}")

    def send_daily_report(self, close_q, close_t, tg_q, tg_t):
        """Generates and sends the daily inspection report with percentage breakdowns."""
        
        # 1. 资产与现金计算 (Asset & Cash Breakdown)
        val_q = float(self.qty_q) * close_q
        val_t = float(self.qty_t) * close_t
        cash = max(0.0, self.equity - val_q - val_t)
        
        # 2. 百分比计算 (Current vs Target Percentages)
        curr_pct_q = (val_q / self.equity * 100) if self.equity > 0 else 0.0
        curr_pct_t = (val_t / self.equity * 100) if self.equity > 0 else 0.0
        curr_pct_cash = (cash / self.equity * 100) if self.equity > 0 else 0.0
        
        tg_pct_q = tg_q * 100
        tg_pct_t = tg_t * 100
        tg_pct_cash = max(0.0, (1.0 - tg_q - tg_t) * 100)

        # 3. 目标股数计算 (Target Shares)
        target_qty_q = round((self.equity * tg_q) / close_q, 4) if close_q > 0 else 0.0
        target_qty_t = round((self.equity * tg_t) / close_t, 4) if close_t > 0 else 0.0

        # 4. 状态 Emoji
        status_icons = {
            "NORMAL": "🟢",
            "ZONE_BATTLE_ATTACK": "⚔️",
            "ZONE_BATTLE_DEFEND": "🛡️",
            "ZONE_DESPAIR_TQQQ": "🔥",
            "TOP_ESCAPE": "🚨",
            "BEAR_CASH": "🐻",
            "INIT": "🔹"
        }
        icon = status_icons.get(self.state_label, "🔹")

        # 5. 操作建议文本生成 (Action String with % and Units)
        def get_action_str(current, target, tg_pct):
            diff = round(target - current, 4)
            pct_str = f"{tg_pct:.1f}%"
            if diff > 0:
                return f"🟢 买入 {diff} 股 (目标: {pct_str} | {target}股)"
            elif diff < 0:
                return f"🔴 卖出 {abs(diff)} 股 (目标: {pct_str} | {target}股)"
            else:
                return f"⚪️ 维持持仓 (目标: {pct_str} | {target}股)"

        action_q = get_action_str(self.qty_q, target_qty_q, tg_pct_q)
        action_t = get_action_str(self.qty_t, target_qty_t, tg_pct_t)

        # 6. 北京时间格式化 (UTC+8)
        tz = datetime.timezone(datetime.timedelta(hours=8))
        now_str = datetime.datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")

        # 7. 组装完整消息
        msg = (
            f"{icon} 【每日巡检】\n"
            f"当前状态: {self.state_label}\n\n"
            f"⏰ 报告时间(北京): {now_str}\n"
            f"💰 账户总资产: ${self.equity:.2f}\n"
            f"🏦 当前现金: ${cash:.2f} ({curr_pct_cash:.1f}% | 目标: {tg_pct_cash:.1f}%)\n"
            f"📈 QQQ: ${close_q:.2f} | TQQQ: ${close_t:.2f}\n\n"
            f"📊 资产占比 (当前 ➜ 目标):\n"
            f"  • QQQ: ${val_q:.2f} ({curr_pct_q:.1f}% ➜ {tg_pct_q:.1f}%)\n"
            f"  • TQQQ: ${val_t:.2f} ({curr_pct_t:.1f}% ➜ {tg_pct_t:.1f}%)\n"
            f"  • 现金: ${cash:.2f} ({curr_pct_cash:.1f}% ➜ {tg_pct_cash:.1f}%)\n\n"
            f"🎯 操作建议:\n"
            f"  • QQQ: {action_q}\n"
            f"  • TQQQ: {action_t}"
        )

        # 8. 发送至 Telegram
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        try:
            res = requests.post(url, json={"chat_id": self.chat_id, "text": msg})
            if res.status_code == 200:
                print("[REPORT SENT] 巡检报告已成功发送至 Telegram!")
            else:
                print(f"[REPORT FAILED] Telegram 拒绝发送: {res.text}")
        except Exception as e:
            print(f"[REPORT CRASH] {e}")

    def run(self):
        print("[INIT] V22.1 Engine Started")

        # Fetch Data
        df_qqq = self.fetch_data("QQQ")
        df_tqqq = self.fetch_data("TQQQ")

        if df_qqq.empty or df_tqqq.empty:
            print("[ERROR] Failed to fetch data from yfinance.")
            return

        df_qqq = self.calculate_indicators(df_qqq)

        latest = df_qqq.iloc[-1]
        prev = df_qqq.iloc[-2]
        
        close_qqq = float(latest['Close'])
        open_qqq = float(latest['Open'])
        vol_qqq = float(latest['Volume'])
        close_tqqq = float(df_tqqq.iloc[-1]['Close'])
        
        ma200 = latest['MA200']
        ma20 = latest['MA20']
        prev_ma20 = prev['MA20']
        vol_ma = latest['Vol_MA']

        # Update ATH
        if self.ath_price == 0.0:
            self._init_ath_price(df_qqq)

        if close_qqq > self.ath_price:
            self.ath_price = close_qqq

        drawdown = (close_qqq / self.ath_price) - 1.0 if self.ath_price > 0 else 0.0

        # --- Top Signal Logic ---
        is_top_signal = False
        if close_qqq >= self.ath_price * self.high_zone:
            if not pd.isna(vol_ma) and vol_qqq > vol_ma * self.vol_factor:
                if close_qqq < open_qqq:
                    is_top_signal = True

        # --- State Machine Logic ---
        next_state = self.state_label

        if is_top_signal:
            next_state = "TOP_ESCAPE"
        elif not pd.isna(ma200) and close_qqq < ma200:
            if drawdown <= -0.30:
                next_state = "ZONE_DESPAIR_TQQQ"
            elif drawdown <= -0.10:
                if not pd.isna(ma20) and close_qqq > ma20:
                    next_state = "ZONE_BATTLE_ATTACK"
                else:
                    next_state = "ZONE_BATTLE_DEFEND"
            else:
                next_state = "BEAR_CASH"
        else:
            if drawdown < -0.10:
                next_state = "ZONE_BATTLE_ATTACK"
            else:
                next_state = "NORMAL"

        # --- Anti-V Filter ---
        raw_next_state = next_state
        risk_off_list = ["BEAR_CASH", "ZONE_BATTLE_DEFEND", "TOP_ESCAPE"]
        risk_on_list = ["ZONE_BATTLE_ATTACK", "NORMAL"]
        blocked = False

        if self.state_label in risk_off_list:
            if raw_next_state in risk_on_list:
                if self.risk_off_days < self.min_risk_off_days:
                    blocked = True
                if not pd.isna(ma20) and not pd.isna(prev_ma20):
                    if ma20 <= prev_ma20:
                        blocked = True
                else:
                    blocked = True

        if blocked:
            next_state = self.state_label
            print("[FILTER] 反转过滤已拦截，保持当前状态")

        # Update risk-off days
        if next_state in risk_off_list:
             self.risk_off_days += 1
        else:
             self.risk_off_days = 0

        self.state_label = next_state

        # Target Weights
        tg_q = 0.0
        tg_t = 0.0
        if next_state == "ZONE_DESPAIR_TQQQ" or next_state == "ZONE_BATTLE_ATTACK":
            tg_q = 0.0
            tg_t = 0.99
        elif next_state == "ZONE_BATTLE_DEFEND" or next_state == "TOP_ESCAPE":
            tg_q = 0.90
            tg_t = 0.0
        elif next_state == "NORMAL":
            tg_q = 0.45
            tg_t = 0.45

        # Dispatch the Daily Report via Telegram
        self.send_daily_report(close_qqq, close_tqqq, tg_q, tg_t)

if __name__ == "__main__":
    bot = QuantStrategy()
    bot.run()
