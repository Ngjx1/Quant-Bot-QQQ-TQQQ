import yfinance as yf
import pandas as pd
import requests
import datetime
import os

class QuantStrategy:
    def __init__(self):
        self.ma_long_window = 200
        self.ma_short_window = 20
        self.vol_window = 60
        self.vol_factor = 2.0
        self.high_zone = 0.95
        
        self.state_label = "NORMAL"
        self.ath_price = 0.0
        self.risk_off_days = 0
        self.min_risk_off_days = 2
        
        # Reads dynamically from GitHub Variables
        self.cash_balance = float(os.environ.get("CASH_BALANCE", "10000.0"))
        self.qty_q = float(os.environ.get("HOLDING_QQQ", "0.0"))
        self.qty_t = float(os.environ.get("HOLDING_TQQQ", "0.0"))

        # Tokens & Identifiers
        self.bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.environ.get("TELEGRAM_CHAT_ID")
        self.gh_pat = os.environ.get("GH_PAT")
        self.gh_repo = os.environ.get("GITHUB_REPOSITORY") # Automatically provided by Actions

    def fetch_data(self, ticker):
        print(f"[DATA] Fetching data for {ticker}...")
        ticker_obj = yf.Ticker(ticker)
        data = ticker_obj.history(period="2y", interval="1d")
        return data

    def calculate_indicators(self, data):
        data['MA200'] = data['Close'].rolling(window=self.ma_long_window).mean()
        data['MA20'] = data['Close'].rolling(window=self.ma_short_window).mean()
        data['Vol_MA'] = data['Volume'].rolling(window=self.vol_window).mean()
        return data

    def _init_ath_price(self, data):
        recent_year = data.tail(252)
        self.ath_price = float(recent_year['High'].max())
        print(f"[INIT] ATH initialized: {self.ath_price:.2f}")

    def update_github_variable(self, var_name, new_value):
        """Uses GitHub API to overwrite the repository variable"""
        if not self.gh_pat or not self.gh_repo:
            print(f"[WARN] 无法更新 GitHub 变量 {var_name}: 缺少 GH_PAT 密钥")
            return

        url = f"https://api.github.com/repos/{self.gh_repo}/actions/variables/{var_name}"
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.gh_pat}",
            "X-GitHub-Api-Version": "2022-11-28"
        }
        data = {"name": var_name, "value": str(new_value)}
        
        try:
            res = requests.patch(url, headers=headers, json=data)
            if res.status_code == 204:
                print(f"[GITHUB] 成功更新变量 {var_name} = {new_value}")
            else:
                print(f"[GITHUB ERROR] 更新 {var_name} 失败: {res.text}")
        except Exception as e:
            print(f"[GITHUB CRASH] {e}")

    def send_daily_report(self, close_q, close_t, tg_q, tg_t):
        # 1. 实时资产计算 (Calculate Live Equity based on today's closing prices)
        val_q = float(self.qty_q) * close_q
        val_t = float(self.qty_t) * close_t
        live_equity = self.cash_balance + val_q + val_t
        
        # 2. 百分比计算 (Current vs Target Percentages)
        curr_pct_q = (val_q / live_equity * 100) if live_equity > 0 else 0.0
        curr_pct_t = (val_t / live_equity * 100) if live_equity > 0 else 0.0
        curr_pct_cash = (self.cash_balance / live_equity * 100) if live_equity > 0 else 0.0
        
        tg_pct_q = tg_q * 100
        tg_pct_t = tg_t * 100
        tg_pct_cash = max(0.0, (1.0 - tg_q - tg_t) * 100)

        # 3. 目标股数计算 (Target Shares)
        target_qty_q = round((live_equity * tg_q) / close_q, 4) if close_q > 0 else 0.0
        target_qty_t = round((live_equity * tg_t) / close_t, 4) if close_t > 0 else 0.0

        # Calculate what your NEW cash balance will be after executing these trades
        new_val_q = target_qty_q * close_q
        new_val_t = target_qty_t * close_t
        new_cash_balance = round(live_equity - new_val_q - new_val_t, 2)

        # 4. 状态 Emoji
        status_icons = {
            "NORMAL": "🟢", "ZONE_BATTLE_ATTACK": "⚔️", "ZONE_BATTLE_DEFEND": "🛡️",
            "ZONE_DESPAIR_TQQQ": "🔥", "TOP_ESCAPE": "🚨", "BEAR_CASH": "🐻"
        }
        icon = status_icons.get(self.state_label, "🔹")

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

        tz = datetime.timezone(datetime.timedelta(hours=8))
        now_str = datetime.datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")

        msg = (
            f"{icon} 【每日巡检】\n"
            f"当前状态: {self.state_label}\n\n"
            f"⏰ 报告时间(北京): {now_str}\n"
            f"💰 账户总资产: ${live_equity:.2f}\n"
            f"🏦 当前现金: ${self.cash_balance:.2f} ({curr_pct_cash:.1f}% | 目标: {tg_pct_cash:.1f}%)\n"
            f"📈 QQQ: ${close_q:.2f} | TQQQ: ${close_t:.2f}\n\n"
            f"📊 资产占比 (当前 ➜ 目标):\n"
            f"  • QQQ: ${val_q:.2f} ({curr_pct_q:.1f}% ➜ {tg_pct_q:.1f}%)\n"
            f"  • TQQQ: ${val_t:.2f} ({curr_pct_t:.1f}% ➜ {tg_pct_t:.1f}%)\n"
            f"  • 现金: ${self.cash_balance:.2f} ({curr_pct_cash:.1f}% ➜ {tg_pct_cash:.1f}%)\n\n"
            f"🎯 操作建议:\n"
            f"  • QQQ: {action_q}\n"
            f"  • TQQQ: {action_t}"
        )

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        try:
            res = requests.post(url, json={"chat_id": self.chat_id, "text": msg})
            if res.status_code == 200:
                print("[REPORT SENT] 巡检报告已成功发送至 Telegram!")
            else:
                print(f"[REPORT FAILED] Telegram 拒绝发送: {res.text}")
        except Exception as e:
            print(f"[REPORT CRASH] {e}")

        return target_qty_q, target_qty_t, new_cash_balance

    def run(self):
        print("[INIT] V22.1 Engine Started")

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

        if self.ath_price == 0.0:
            self._init_ath_price(df_qqq)

        if close_qqq > self.ath_price:
            self.ath_price = close_qqq

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

        if next_state in risk_off_list:
             self.risk_off_days += 1
        else:
             self.risk_off_days = 0

        self.state_label = next_state

        tg_q = 0.0
        tg_t = 0.0
        if next_state in ["ZONE_DESPAIR_TQQQ", "ZONE_BATTLE_ATTACK"]:
            tg_q = 0.0
            tg_t = 0.99
        elif next_state in ["ZONE_BATTLE_DEFEND", "TOP_ESCAPE"]:
            tg_q = 0.90
            tg_t = 0.0
        elif next_state == "NORMAL":
            tg_q = 0.45
            tg_t = 0.45
        elif next_state == "BEAR_CASH":
            tg_q = 0.0
            tg_t = 0.0

        # Send report AND capture the newly calculated target shares and cash balance
        target_qty_q, target_qty_t, new_cash = self.send_daily_report(close_qqq, close_tqqq, tg_q, tg_t)
        
        # Assuming you executed the trade perfectly, update GitHub's memory for tomorrow
        if target_qty_q != self.qty_q:
            self.update_github_variable("HOLDING_QQQ", target_qty_q)
        if target_qty_t != self.qty_t:
            self.update_github_variable("HOLDING_TQQQ", target_qty_t)
        if new_cash != self.cash_balance:
            self.update_github_variable("CASH_BALANCE", new_cash)

if __name__ == "__main__":
    bot = QuantStrategy()
    bot.run()
