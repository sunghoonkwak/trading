import sys
import os
import json
import logging
import argparse
from datetime import datetime
import pandas as pd
import yfinance as yf

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, "../../../"))
src_path = os.path.join(project_root, "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from strategy.raoeo import calculate_orders
from strategy.base import OrderSide
from core.constants import ORDER_TYPE_US_LOC, ORDER_TYPE_US_LIMIT

# Configure logging to WARNING so calculate_orders logs don't spam output
logging.basicConfig(level=logging.WARNING, format="%(message)s")

CONFIG_PATH = os.path.expanduser("~/KIS_config/strategy_config.json")
def load_config(ticker: str):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, "strategy_config.json")

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
    except FileNotFoundError:
        raise ValueError(f"Config file not found: {config_path}")

    cfg = config_data.get("raoeo", {}).get("targets", {}).get(ticker)
    if not cfg:
        raise ValueError(f"RAOEO configuration for {ticker} not found in strategy_config.json")
    return cfg

class SimulationState:
    def __init__(self, seed: float, duration: int, case: int):
        self.initial_seed = seed
        self.seed = seed
        self.duration = duration
        self.case = case # 1 = Hold at 100%, 2 = Hold at 200%, 3 = 150% Recursive Cut
        self.daily_budget = seed / duration
        self.qty = 0
        self.spent = 0.0 # Net Cash
        self.cost_basis = 0.0 # For Average Price
        self.max_spent = 0.0
        self.realized_profit = 0.0
        self.cycles = 0
        self.over_100_periods = []
        self._current_over_100_start = None
        self.over_200_periods = []
        self._current_over_200_start = None
        self.did_notify_suspension = False
        self.available_extra_cash = 0.0 # From defensive sales

    @property
    def avg_price(self):
        return self.cost_basis / self.qty if self.qty > 0 else 0.0

    @property
    def progress_ratio(self):
        return self.spent / self.seed if self.seed > 0 else 0.0

    @property
    def progress_ratio_initial(self):
        return self.spent / self.initial_seed if self.initial_seed > 0 else 0.0

    def reset_cycle(self, end_date_str=None):
        self.cycles += 1
        self.qty = 0
        self.spent = 0.0
        self.cost_basis = 0.0
        self.did_notify_suspension = False
        self.available_extra_cash = 0.0
        if self._current_over_100_start:
            end_val = end_date_str if end_date_str else "진행중"
            self.over_100_periods.append((self._current_over_100_start, end_val))
            self._current_over_100_start = None
        if self._current_over_200_start:
            end_val = end_date_str if end_date_str else "진행중"
            self.over_200_periods.append((self._current_over_200_start, end_val))
            self._current_over_200_start = None

def run_simulation(df: pd.DataFrame, ticker: str, config: dict, case: int, compound: bool = False) -> SimulationState:
    seed = float(config['seed'])
    duration = int(config['duration'])
    phases = config['phase']

    state = SimulationState(seed, duration, case)

    prev_close = None

    for date, row in df.iterrows():
        d_str = date.strftime("%Y-%m-%d")
        high_p = row['High']
        close_p = row['Close']
        open_p = row['Open']

        if prev_close is None:
            prev_close = close_p
            continue

        cur_price = prev_close # Assuming we calculate orders before market open based on yesterday's close
        base_price = state.avg_price if state.qty > 0 else cur_price

        can_buy = True
        # Check boundaries and determine can_buy
        can_buy = True
        limit_ratio = 1.0 if state.case == 1 else 2.0
        if state.case == 3:
            limit_ratio = 1.5

        if state.progress_ratio >= 1.0:
            if state._current_over_100_start is None:
                state._current_over_100_start = d_str

            if state.case == 1:
                can_buy = False
            elif state.case == 3:
                can_buy = True # Will handle cuts recursively
            else:
                if state.progress_ratio >= 2.0:
                    if state._current_over_200_start is None:
                        state._current_over_200_start = d_str
                    can_buy = False

        # Notifications (Now accounting for extra cash)
        is_over_limit = (state.progress_ratio >= limit_ratio)
        if is_over_limit and state.available_extra_cash <= 0.01 and not state.did_notify_suspension:
            if state.case == 3:
                print(f"  [🚨 방어 구간] {d_str} 원금 1.5배 도달! 필요시 방어 매도를 병행합니다.")
            else:
                print(f"  [🛑 투입 중단] {d_str} 원금 {int(limit_ratio*100)}% 돌파! 더이상 추가 매수하지 않습니다.")
            state.did_notify_suspension = True
        elif not is_over_limit and state.did_notify_suspension:
            state.did_notify_suspension = False
        elif state.available_extra_cash > 0.01 and state.did_notify_suspension:
             # We have cash to spend, so we are not 'suspended' in the sense of 'can't buy'
             state.did_notify_suspension = False

        # Call real strategy logic
        target_cfg = config.copy()
        target_cfg['seed'] = state.seed
        targets_config = {ticker: target_cfg}
        portfolio = {ticker: {'qty': state.qty, 'avg_price': state.avg_price, 'cur_price': prev_close}}
        current_prices = {ticker: prev_close}

        orders, info = calculate_orders(targets_config, portfolio, current_prices)

        sell_orders = [o for o in orders if o.side == OrderSide.SELL]
        buy_orders = [o for o in orders if o.side == OrderSide.BUY]

        # Simulate End of Day Sells
        sold_qty = 0
        revenue = 0.0

        for sell in sell_orders:
            target_px = sell.price
            sell_qty = sell.quantity
            stype = "LOC" if sell.order_type == ORDER_TYPE_US_LOC else "Limit"

            executed = False
            exec_price = 0.0

            if stype == "Limit":
                if high_p >= target_px:
                    executed = True
                    exec_price = target_px # Limit orders fill at limit price usually
            elif stype == "LOC":
                if close_p >= target_px:
                    executed = True
                    exec_price = close_p

            if executed:
                sold_qty += sell_qty
                revenue += (sell_qty * exec_price)

        if sold_qty > 0:
            sold_cost_basis = state.avg_price * sold_qty
            trade_profit = revenue - sold_cost_basis
            state.realized_profit += trade_profit
            state.qty -= sold_qty
            state.spent -= revenue # Revenue reduces Net Cash Outflow
            state.cost_basis -= sold_cost_basis

            if state.qty == 0:
                if compound:
                    state.seed += trade_profit
                    state.seed = max(1.0, state.seed)
                    state.daily_budget = state.seed / state.duration
                    print(f"[{d_str}] 사이클 익절 완료: 총 매도액 ${revenue:.2f}, 수익금 ${trade_profit:.2f}. (누적: ${state.realized_profit:.2f}, 📈 복리 시드: ${state.seed:.2f})")
                else:
                    print(f"[{d_str}] 사이클 익절 완료: 총 매도액 ${revenue:.2f}, 수익금 ${trade_profit:.2f}. (누적 총수익: ${state.realized_profit:.2f})")
                state.reset_cycle(d_str)
                prev_close = close_p
                continue # Skip buys if we sold everything today

        # Simulate Buys
        if can_buy:
            bought_today_qty = 0
            spent_today = 0.0

            # Defensive Cuts for Case 3
            if state.case == 3:
                # Only cut if over limit AND out of extra cash
                if state.progress_ratio >= 1.5 and state.available_extra_cash <= 0.01 and state.qty > 0:
                    emergency_sell_qty = max(1, int(state.qty / 3.0))
                    rev = emergency_sell_qty * close_p
                    basis = state.avg_price * emergency_sell_qty
                    t_profit = rev - basis

                    state.qty -= emergency_sell_qty
                    state.spent -= rev
                    state.cost_basis -= basis
                    state.realized_profit += t_profit
                    state.available_extra_cash += rev

                    if compound:
                        print(f"  [🚨 방어 매도] {d_str} 원금 1.5배 돌파! 1/3 매도 (수익: ${t_profit:.2f}, 확보현금: ${rev:.2f}, 📈 시드축소: ${state.seed+t_profit:.2f})")
                        state.seed += t_profit
                        state.seed = max(1.0, state.seed)
                        state.daily_budget = state.seed / state.duration
                    else:
                        print(f"  [🚨 방어 매도] {d_str} 원금 1.5배 돌파! 1/3 매도 (수익: ${t_profit:.2f}, 확보현금: ${rev:.2f})")

            for buy in buy_orders:
                target_buy_px = buy.price
                order_qty = buy.quantity

                # RAOEO assumes all normal/average/filling are evaluated as LOC against close
                if close_p <= target_buy_px:
                    bought_today_qty += order_qty
                    spent_today += (order_qty * close_p)

            if bought_today_qty > 0:
                state.qty += bought_today_qty
                state.spent += spent_today
                state.cost_basis += spent_today
                if state.available_extra_cash > 0:
                    deduct = min(state.available_extra_cash, spent_today)
                    state.available_extra_cash -= deduct

                if state.spent > state.max_spent:
                    state.max_spent = state.spent

        prev_close = close_p

    if state._current_over_100_start:
        state.over_100_periods.append((state._current_over_100_start, "진행중"))

    return state


def print_over_100(periods):
    if not periods:
        print("시드 100% 초과 구간: 없음")
        return
    print("시드 100% 초과 구간 (시작일 -> 종료일/현재):")
    for start_ds, end_ds in periods:
        if end_ds == "진행중":
            today_str = datetime.now().strftime("%Y-%m-%d")
            dt1 = datetime.strptime(start_ds, "%Y-%m-%d")
            dt2 = datetime.strptime(today_str, "%Y-%m-%d")
            days_diff = (dt2 - dt1).days
            print(f"  {start_ds} -> {end_ds} (현재 {days_diff}일째 초과 진행중)")
        else:
            try:
                dt1 = datetime.strptime(start_ds, "%Y-%m-%d")
                dt2 = datetime.strptime(end_ds, "%Y-%m-%d")
                days_diff = (dt2 - dt1).days
                print(f"  {start_ds} -> {end_ds} (총 {days_diff}일간 초과)")
            except:
                print(f"  {start_ds} -> {end_ds}")

def get_max_stuck_days(periods):
    max_days = 0
    for start_ds, end_ds in periods:
        end_str = end_ds if end_ds != "진행중" else datetime.now().strftime("%Y-%m-%d")
        try:
            dt1 = datetime.strptime(start_ds, "%Y-%m-%d")
            dt2 = datetime.strptime(end_str, "%Y-%m-%d")
            days_diff = (dt2 - dt1).days
            if days_diff > max_days:
                max_days = days_diff
        except:
            pass
    return max_days

def get_buy_and_hold_roi(ticker, start_date, end_date):
    try:
        ref_df = yf.Ticker(ticker).history(start=start_date, end=end_date)
        if ref_df.empty: return 0.0
        start_px = ref_df['Close'].iloc[0]
        end_px = ref_df['Close'].iloc[-1]
        return ((end_px - start_px) / start_px) * 100
    except:
        return 0.0

def main():
    parser = argparse.ArgumentParser(description="RAOEO Backtest Script")
    parser.add_argument("--ticker", type=str, required=True, help="Ticker symbol (e.g., SOXL)")
    parser.add_argument("--start", type=str, required=True, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, default=None, help="End date (YYYY-MM-DD), default: today")
    parser.add_argument("--compound", action="store_true", help="Enable compounding (reinvest profits into initial seed)")
    args = parser.parse_args()

    ticker = args.ticker
    start_date = args.start
    end_date = args.end
    compound_flag = args.compound

    print(f"=== {ticker} 설정 로딩 중... ===")
    try:
        config = load_config(ticker)
    except Exception as e:
        print(e)
        return

    end_label = end_date if end_date else "현재"
    print(f"=== {ticker} 야후 파이낸스 데이터 로딩 중 ({start_date} ~ {end_label}) ===")
    ticker_obj = yf.Ticker(ticker)
    df = ticker_obj.history(start=start_date, end=end_date)

    if df.empty:
        print("데이터를 찾을 수 없습니다. 티커와 시작일을 다시 확인해주세요.")
        return

    actual_start_str = df.index[0].strftime('%Y%m%d')
    actual_end_str = df.index[-1].strftime('%Y%m%d')
    script_dir = os.path.dirname(os.path.abspath(__file__))
    report_filename = os.path.join(script_dir, f"{ticker}_{actual_start_str}_{actual_end_str}.md")

    class Logger(object):
        def __init__(self, filename):
            self.terminal = sys.stdout
            self.log = open(filename, "w", encoding='utf-8')
        def write(self, message):
            self.terminal.write(message)
            self.log.write(message)
        def flush(self):
            self.terminal.flush()
            self.log.flush()

    sys.stdout = Logger(report_filename)

    print(f"# 라오어 RAOEO 백테스트 결과 보고서: {ticker}")
    print(f"- **입력 시작일**: {start_date}")
    print(f"- **실제 데이터 기간**: {df.index[0].strftime('%Y-%m-%d')} ~ {df.index[-1].strftime('%Y-%m-%d')}")
    print(f"- **실행일시**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("---")
    print(f"- **총 가져온 거래일 수**: {len(df)}일\n")

    print(f"## ⚙️ 적용된 전략 설정 (Strategy Config)")
    print("```json")
    print(json.dumps(config, indent=4, ensure_ascii=False))
    print("```\n")

    print(f"## CASE 1: 단리 100% 투입 중단 (Simple Stop at 100%)")
    print("```text")
    state1 = run_simulation(df, ticker, config, case=1, compound=False)
    print("```\n")

    print(f"## CASE 2: 단리 200% 물타기 (Simple Buy up to 200%)")
    print("```text")
    state2 = run_simulation(df, ticker, config, case=2, compound=False)
    print("```\n")

    print(f"## CASE 3: 단리 150% 방어매도 (Simple 150% Defensive Cut)")
    print("```text")
    state3 = run_simulation(df, ticker, config, case=3, compound=False)
    print("```\n")

    print(f"## CASE 4: 복리 100% 투입 중단 (Compound Stop at 100%)")
    print("```text")
    state4 = run_simulation(df, ticker, config, case=1, compound=True)
    print("```\n")

    print(f"## CASE 5: 복리 200% 물타기 (Compound Buy up to 200%)")
    print("```text")
    state5 = run_simulation(df, ticker, config, case=2, compound=True)
    print("```\n")

    print(f"## CASE 6: 복리 150% 방어매도 (Compound 150% Defensive Cut)")
    print("```text")
    state6 = run_simulation(df, ticker, config, case=3, compound=True)
    print("```\n")

    days = (df.index[-1] - df.index[0]).days
    years = days / 365.25 if days > 0 else 1.0

    print(f"\n## 📊 전략 비교 요약")
    print("| 전략 (Strategy) | 총 수익률 | 연평균(CAGR) | 최종 누적 수익금 | 결과 시드 규모 | 최대 매수 자금(Max Spent) | 100% 초과 | 200% 초과 | 익절 성공 |")
    print("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")

    def print_row(name, state):
        roi_ratio = state.realized_profit / state.initial_seed if state.initial_seed > 0 else 0
        roi_perc = roi_ratio * 100
        roi = f"{roi_perc:.2f}%" if state.initial_seed > 0 else "-"

        cagr_val = ((1 + roi_ratio) ** (1 / years) - 1) if years > 0 and (1 + roi_ratio) > 0 else 0
        cagr = f"{cagr_val * 100:.2f}%" if state.initial_seed > 0 else "-"

        stuck_100 = f"{get_max_stuck_days(state.over_100_periods)}일"
        stuck_200 = f"{get_max_stuck_days(state.over_200_periods)}일"
        print(f"| **{name}** | {roi} | **{cagr}** | ${state.realized_profit:.2f} | ${state.seed:.2f} | **${state.max_spent:.2f}** | {stuck_100} | {stuck_200} | {state.cycles}회 |")

    print_row("CASE 1 (단리 100% 투입중단)", state1)
    print_row("CASE 2 (단리 200% 물타기)", state2)
    print_row("CASE 3 (단리 150% 방어매도)", state3)
    print_row("CASE 4 (복리 100% 투입중단)", state4)
    print_row("CASE 5 (복리 200% 물타기)", state5)
    print_row("CASE 6 (복리 150% 방어매도)", state6)

    # Calculate Benchmark ROIs
    ref_start = df.index[0].strftime('%Y-%m-%d')
    ref_end = (df.index[-1] + pd.Timedelta(days=1)).strftime('%Y-%m-%d')
    soxx_roi = get_buy_and_hold_roi("SOXX", ref_start, ref_end)
    soxl_roi = get_buy_and_hold_roi(ticker, ref_start, ref_end)
    voo_roi = get_buy_and_hold_roi("VOO", ref_start, ref_end)
    qqq_roi = get_buy_and_hold_roi("QQQ", ref_start, ref_end)

    def print_benchmark(name, b_roi):
        b_ratio = b_roi / 100.0
        b_cagr_val = ((1 + b_ratio) ** (1 / years) - 1) if years > 0 and (1 + b_ratio) > 0 else 0
        b_cagr = f"{b_cagr_val * 100:.2f}%"
        print(f"| **{name}** | {b_roi:.2f}% | **{b_cagr}** | - | - | - | - | - | - |")

    print_benchmark(f"Ref0 ({ticker} 단순 보유)", soxl_roi)
    print_benchmark("Ref1 (SOXX 단순 보유)", soxx_roi)
    print_benchmark("Ref2 (VOO 단순 보유)", voo_roi)
    print_benchmark("Ref3 (QQQ 단순 보유)", qqq_roi)

    # Close logger to flush file
    if hasattr(sys.stdout, 'log'):
        sys.stdout.log.close()
        sys.stdout = sys.stdout.terminal
        print(f"\n✅ 리포트가 성공적으로 저장되었습니다: {report_filename}")

if __name__ == "__main__":
    main()
