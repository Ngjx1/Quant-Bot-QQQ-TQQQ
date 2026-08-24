import yfinance as yf
import pandas as pd
import requests
import datetime
import os  # <-- We need this to read GitHub Secrets

# --- Configuration ---
# Now it dynamically reads the secrets you saved in GitHub
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8845865365:AAFd76bQzxBJDKMgMlrKb44pmVRUBb99QlE")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "8578262364")

def alert(title, content):
    """Sends a Telegram notification."""
    # Safety check: don't crash if secrets are missing
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print(f"[LOCAL ALERT] {title} - {content}")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    message = f"🚨 *{title}*\n\n{content}"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload)
        print(f"[ALERT SENT] {title}")
    except Exception as e:
        print(f"[ALERT FAILED] {e}")

class QuantStrategy:
    def __init__(self):
        self.ma_long_window = 200
        self.ma_short_window = 20
        self.vol_window = 60
        self.vol_factor = 2.0
        self.high_zone = 0.95
        
        # State management (In a real bot, these should be saved to a database/file)
        self.state_label = "INIT"
        self.ath_price = 0.0
        self.days_since_rebal = 0
        self.risk_off_days = 0
        self.min_risk_off_days = 2
        
        self.pending_buy = False
        self.pending_target_q = 0.0
        self.pending_target_t = 0.0

    def fetch_data(self, ticker):
        """Fetches historical daily data using yfinance."""
        print(f"[DATA] Fetching data for {ticker}...")
        # Use yf.Ticker().history() instead of yf.download() to prevent MultiIndex data structure errors
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
        # Force the maximum value to be a standard Python float (decimal)
        self.ath_price = float(recent_year['High'].max())
        print(f"[INIT] ATH initialized: {self.ath_price:.2f}")

    def run(self):
        print("[INIT] Strategy V22.1 Started (yfinance + Telegram)")
        alert("【Strategy Started】", "V22.1 Initialization complete. Fetching data...")

        df_qqq = self.fetch_data("QQQ")
        df_tqqq = self.fetch_data("TQQQ")

        if df_qqq.empty or df_tqqq.empty:
            alert("【Data Error】", "Failed to fetch data from yfinance.")
            return

        df_qqq = self.calculate_indicators(df_qqq)

        latest = df_qqq.iloc[-1]
        prev = df_qqq.iloc[-2]
        
        close_qqq = latest['Close']
        open_qqq = latest['Open']
        vol_qqq = latest['Volume']
        close_tqqq = df_tqqq.iloc[-1]['Close']
        
        ma200 = latest['MA200']
        ma20 = latest['MA20']
        prev_ma20 = prev['MA20']
        vol_ma = latest['Vol_MA']

        if self.ath_price == 0.0:
            self._init_ath_price(df_qqq)

        if close_qqq > self.ath_price:
            self.ath_price = float(close_qqq)

        drawdown = (close_qqq / self.ath_price) - 1.0 if self.ath_price > 0 else 0.0

        is_top_signal = False
        if close_qqq >= self.ath_price * self.high_zone:
            if not pd.isna(vol_ma) and vol_qqq > vol_ma * self.vol_factor:
                if close_qqq < open_qqq:
                    is_top_signal = True

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

        raw_next_state = next_state
        risk_off_list = ["BEAR_CASH", "ZONE_BATTLE_DEFEND", "TOP_ESCAPE"]
        risk_on_list = ["ZONE_BATTLE_ATTACK", "NORMAL"]
        blocked = False
        blocked_reasons = []

        if self.state_label in risk_off_list:
            if raw_next_state in risk_on_list:
                if self.risk_off_days < self.min_risk_off_days:
                    blocked = True
                    blocked_reasons.append(f"Cool-down not met: Waited {self.risk_off_days}/{self.min_risk_off_days} days.")
                if not pd.isna(ma20) and not pd.isna(prev_ma20):
                    if ma20 <= prev_ma20:
                        blocked = True
                        blocked_reasons.append("MA20 slope is flat or downward.")
                else:
                    blocked = True
                    blocked_reasons.append("Insufficient MA20 data.")

        if blocked:
            next_state = self.state_label
            reason_text = "; ".join(blocked_reasons)
            alert("【Reversal Filter Active】", f"Delaying switch to {raw_next_state}. Reasons: {reason_text}")

        if next_state in risk_off_list:
             self.risk_off_days += 1
        else:
             self.risk_off_days = 0

        if next_state != self.state_label:
            alert("【Signal Triggered】", f"State changed from {self.state_label} -> {next_state}")
            self.state_label = next_state
        else:
            print(f"[STATUS] Maintaining state: {self.state_label}")

if __name__ == "__main__":
    bot = QuantStrategy()
    bot.run()
