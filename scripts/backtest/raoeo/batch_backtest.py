import sys
import os
import json
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import numpy as np
from tqdm import tqdm

# Add src to path
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, "../../../"))
src_path = os.path.join(project_root, "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# Import simulation logic from backtest_raoeo
# We need to make sure we can import it.
sys.path.insert(0, script_dir)
from backtest_raoeo import run_simulation, load_config

def calculate_cagr(realized_profit, initial_seed, start_date, end_date):
    days = (end_date - start_date).days
    years = days / 365.25 if days > 0 else 1.0
    roi_ratio = realized_profit / initial_seed if initial_seed > 0 else 0
    
    if roi_ratio <= -1.0: # Total loss
        return -1.0
    
    try:
        cagr = ((1 + roi_ratio) ** (1 / years) - 1)
        return cagr
    except:
        return 0.0

def main():
    ticker = "SOXL"
    print(f"=== {ticker} 배치 백테스트 시작 ===")
    
    try:
        config = load_config(ticker)
    except Exception as e:
        print(f"Error loading config: {e}")
        return

    # 1. Generate date ranges
    # Start dates: 2022-01-01 ~ 2023-12-01 (1 month interval, 24 dates)
    start_dates = []
    curr = datetime(2022, 1, 1)
    for _ in range(24):
        start_dates.append(curr)
        # Move to next month
        if curr.month == 12:
            curr = datetime(curr.year + 1, 1, 1)
        else:
            curr = datetime(curr.year, curr.month + 1, 1)

    # End dates: 2025-01-01 ~ 2026-05-01 (1 month interval, 17 dates)
    end_dates = []
    curr = datetime(2025, 1, 1)
    for _ in range(17):
        end_dates.append(curr)
        if curr.month == 12:
            curr = datetime(curr.year + 1, 1, 1)
        else:
            curr = datetime(curr.year, curr.month + 1, 1)

    print(f"시작일 조합: {len(start_dates)}개")
    print(f"종료일 조합: {len(end_dates)}개")
    print(f"총 시뮬레이션 기간 조합: {len(start_dates) * len(end_dates)}개")

    # 2. Fetch full data once
    fetch_start = min(start_dates).strftime("%Y-%m-%d")
    fetch_end = (max(end_dates) + timedelta(days=5)).strftime("%Y-%m-%d") # Buff for market close
    print(f"데이터 다운로드 중 ({fetch_start} ~ {fetch_end})...")
    full_df = yf.Ticker(ticker).history(start=fetch_start, end=fetch_end)
    
    if full_df.empty:
        print("데이터를 가져오는데 실패했습니다.")
        return

    # Make timezone naive to avoid comparison issues
    if full_df.index.tz is not None:
        full_df.index = full_df.index.tz_localize(None)

    cash_ticker = config.get("cash_ticker")
    if cash_ticker:
        print(f"캐시 티커({cash_ticker}) 데이터 다운로드 중...")
        cash_df = yf.Ticker(cash_ticker).history(start=fetch_start, end=fetch_end, auto_adjust=False)
        if cash_df.index.tz is not None:
            cash_df.index = cash_df.index.tz_localize(None)
        if not cash_df.empty:
            cash_df = cash_df[['Close', 'Dividends']].rename(columns={'Close': 'Cash_Close', 'Dividends': 'Cash_Dividends'})
            full_df = full_df.join(cash_df, how='left')

    # 3. Simulation Loop
    results = {i: [] for i in range(1, 7)} # Case 1 to 6
    benchmark_results = {ticker: [], "SOXX": [], "VOO": [], "QQQ": []}
    
    total_combinations = len(start_dates) * len(end_dates)
    pbar = tqdm(total=total_combinations, desc="Simulating")

    import io
    from contextlib import redirect_stdout

    # Fetch benchmark data
    print("벤치마크 데이터 다운로드 중...")
    bench_data = {}
    for b_ticker in ["SOXX", "VOO", "QQQ"]:
        b_df = yf.Ticker(b_ticker).history(start=fetch_start, end=fetch_end)
        if b_df.index.tz is not None:
            b_df.index = b_df.index.tz_localize(None)
        bench_data[b_ticker] = b_df

    for s_date in start_dates:
        for e_date in end_dates:
            # Slice main ticker data
            mask = (full_df.index >= s_date) & (full_df.index <= e_date)
            df_slice = full_df.loc[mask]
            
            if df_slice.empty:
                pbar.update(1)
                continue
            
            actual_start = df_slice.index[0]
            actual_end = df_slice.index[-1]
            
            # Main ticker buy and hold
            start_px = df_slice['Close'].iloc[0]
            end_px = df_slice['Close'].iloc[-1]
            roi_ratio = (end_px - start_px) / start_px
            cagr_bench = calculate_cagr(roi_ratio, 1.0, actual_start, actual_end)
            benchmark_results[ticker].append((cagr_bench, actual_start, actual_end))

            # Benchmarks buy and hold
            for b_ticker in ["SOXX", "VOO", "QQQ"]:
                b_df = bench_data[b_ticker]
                b_mask = (b_df.index >= actual_start) & (b_df.index <= actual_end)
                b_slice = b_df.loc[b_mask]
                if not b_slice.empty:
                    b_start_px = b_slice['Close'].iloc[0]
                    b_end_px = b_slice['Close'].iloc[-1]
                    b_roi_ratio = (b_end_px - b_start_px) / b_start_px
                    b_cagr = calculate_cagr(b_roi_ratio, 1.0, actual_start, actual_end)
                    benchmark_results[b_ticker].append((b_cagr, actual_start, actual_end))

            # Case 1-3: Simple, Case 4-6: Compound
            f_dummy = io.StringIO()
            with redirect_stdout(f_dummy):
                for case_idx in range(1, 4):
                    # Simple
                    state_simple = run_simulation(df_slice, ticker, config, case=case_idx, compound=False)
                    tot_profit_simple = state_simple.realized_profit + state_simple.tltw_realized_profit + state_simple.tltw_dividends
                    cagr_simple = calculate_cagr(tot_profit_simple, state_simple.initial_seed, actual_start, actual_end)
                    results[case_idx].append((cagr_simple, actual_start, actual_end, state_simple.tltw_realized_profit, state_simple.tltw_dividends, state_simple.realized_profit))
                    
                    # Compound
                    state_compound = run_simulation(df_slice, ticker, config, case=case_idx, compound=True)
                    tot_profit_compound = state_compound.realized_profit + state_compound.tltw_realized_profit + state_compound.tltw_dividends
                    cagr_compound = calculate_cagr(tot_profit_compound, state_compound.initial_seed, actual_start, actual_end)
                    results[case_idx + 3].append((cagr_compound, actual_start, actual_end, state_compound.tltw_realized_profit, state_compound.tltw_dividends, state_compound.realized_profit))
            
            pbar.update(1)
    
    pbar.close()

    # 4. Statistical Analysis
    case_names = {
        1: "Case 1 (단리 100% 투입중단)",
        2: "Case 2 (단리 200% 물타기)",
        3: "Case 3 (단리 150% 방어매도)",
        4: "Case 4 (복리 100% 투입중단)",
        5: "Case 5 (복리 200% 물타기)",
        6: "Case 6 (복리 150% 방어매도)"
    }

    def get_stats(data_list):
        if not data_list: return None
        cagrs = [x[0] for x in data_list]
        mean_val = np.mean(cagrs) * 100
        std_val = np.std(cagrs) * 100
        win_rate = (sum(1 for x in cagrs if x > 0) / len(cagrs)) * 100
        
        avg_tltw_loss = 0.0
        avg_tltw_div = 0.0
        avg_soxl_profit = 0.0
        if len(data_list[0]) > 3:
            avg_tltw_loss = np.mean([x[3] for x in data_list])
            avg_tltw_div = np.mean([x[4] for x in data_list])
            avg_soxl_profit = np.mean([x[5] for x in data_list])
        
        # Percentiles
        p10 = np.percentile(cagrs, 10) * 100
        p25 = np.percentile(cagrs, 25) * 100
        p50 = np.percentile(cagrs, 50) * 100 # Median
        p75 = np.percentile(cagrs, 75) * 100
        p90 = np.percentile(cagrs, 90) * 100
        
        max_idx = np.argmax(cagrs)
        min_idx = np.argmin(cagrs)
        
        max_val = cagrs[max_idx] * 100
        max_range = f"{data_list[max_idx][1].strftime('%Y-%m-%d')} ~ {data_list[max_idx][2].strftime('%Y-%m-%d')}"
        
        min_val = cagrs[min_idx] * 100
        min_range = f"{data_list[min_idx][1].strftime('%Y-%m-%d')} ~ {data_list[min_idx][2].strftime('%Y-%m-%d')}"
        
        iqr = p75 - p25
        lower_bound = p25 - 1.5 * iqr
        upper_bound = p75 + 1.5 * iqr
        
        outliers = []
        for x in data_list:
            cagr = x[0] * 100
            if cagr < lower_bound or cagr > upper_bound:
                outliers.append({
                    "cagr": cagr,
                    "range": f"{x[1].strftime('%Y-%m-%d')} ~ {x[2].strftime('%Y-%m-%d')}",
                    "type": "상방 예외" if cagr > upper_bound else "하방 예외"
                })
        
        outliers = sorted(outliers, key=lambda k: k['cagr'], reverse=True)
        
        return {
            "mean": mean_val, "std": std_val, "win_rate": win_rate,
            "max": max_val, "max_range": max_range,
            "min": min_val, "min_range": min_range,
            "p10": p10, "p25": p25, "p50": p50, "p75": p75, "p90": p90,
            "outliers": outliers,
            "avg_tltw_loss": avg_tltw_loss,
            "avg_tltw_div": avg_tltw_div,
            "avg_soxl_profit": avg_soxl_profit
        }

    plot_data = []
    plot_names = {
        "Case 1 (단리 100% 투입중단)": "C1 (Simple 100%)",
        "Case 2 (단리 200% 물타기)": "C2 (Simple 200%)",
        "Case 3 (단리 150% 방어매도)": "C3 (Simple 150%)",
        "Case 4 (복리 100% 투입중단)": "C4 (Comp 100%)",
        "Case 5 (복리 200% 물타기)": "C5 (Comp 200%)",
        "Case 6 (복리 150% 방어매도)": "C6 (Comp 150%)",
        f"Ref0 ({ticker} 단순 보유)": f"Ref0 ({ticker})",
        "Ref1 (SOXX 단순 보유)": "Ref1 (SOXX)",
        "Ref2 (VOO 단순 보유)": "Ref2 (VOO)",
        "Ref3 (QQQ 단순 보유)": "Ref3 (QQQ)"
    }

    cash_ticker_suffix = f"_{config.get('cash_ticker')}" if config.get("cash_ticker") else ""
    report_path = os.path.join(script_dir, f"batch_analysis_report{cash_ticker_suffix}.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"# RAOEO Batch Backtest Analysis Report: {ticker} (Cash: {config.get('cash_ticker', 'USD')})\n\n")
        f.write(f"- **분석 기간**: 2022-01 ~ 2026-05\n")
        f.write(f"- **시작일 조합**: {len(start_dates)}개 (매월 1일)\n")
        f.write(f"- **종료일 조합**: {len(end_dates)}개 (매월 1일)\n")
        f.write(f"- **총 시뮬레이션 횟수**: {total_combinations * 6}회\n")
        f.write(f"- **실행일시**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        f.write("## 📊 1. CAGR 성과 및 극값(Max/Min) 요약\n\n")
        if config.get("cash_ticker"):
            f.write("| 전략/벤치마크 | 평균(Mean) | 최대(Max) [기간] | 최소(Min) [기간] | 평균 매매손실 | 평균 배당금 | 본장(SOXL)수익 | Std | 승률 |\n")
            f.write("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n")
        else:
            f.write("| 전략/벤치마크 | 평균(Mean) | 최대(Max) [기간] | 최소(Min) [기간] | 표준편차(Std) | 승률 |\n")
            f.write("| :--- | :--- | :--- | :--- | :--- | :--- |\n")
        
        all_stats = {}
        # Strategy cases
        for i in range(1, 7):
            stats = get_stats(results[i])
            if not stats: continue
            all_stats[case_names[i]] = stats
            if config.get("cash_ticker"):
                f.write(f"| {case_names[i]} | **{stats['mean']:.2f}%** | {stats['max']:.2f}% <br>({stats['max_range']}) | {stats['min']:.2f}% <br>({stats['min_range']}) | **${stats['avg_tltw_loss']:,.0f}** | **${stats['avg_tltw_div']:,.0f}** | **${stats['avg_soxl_profit']:,.0f}** | {stats['std']:.2f}% | {stats['win_rate']:.1f}% |\n")
            else:
                f.write(f"| {case_names[i]} | **{stats['mean']:.2f}%** | {stats['max']:.2f}% <br>({stats['max_range']}) | {stats['min']:.2f}% <br>({stats['min_range']}) | {stats['std']:.2f}% | {stats['win_rate']:.1f}% |\n")
            for x in results[i]:
                plot_data.append({"Strategy": plot_names[case_names[i]], "CAGR": x[0] * 100})
        
        f.write("| --- | --- | --- | --- | --- | --- |\n")
        
        # Benchmarks
        bench_names = {
            ticker: f"Ref0 ({ticker} 단순 보유)",
            "SOXX": "Ref1 (SOXX 단순 보유)",
            "VOO": "Ref2 (VOO 단순 보유)",
            "QQQ": "Ref3 (QQQ 단순 보유)"
        }
        for b_ticker in [ticker, "SOXX", "VOO", "QQQ"]:
            stats = get_stats(benchmark_results[b_ticker])
            if not stats: continue
            all_stats[bench_names[b_ticker]] = stats
            if config.get("cash_ticker"):
                f.write(f"| **{bench_names[b_ticker]}** | **{stats['mean']:.2f}%** | {stats['max']:.2f}% <br>({stats['max_range']}) | {stats['min']:.2f}% <br>({stats['min_range']}) | - | - | - | {stats['std']:.2f}% | {stats['win_rate']:.1f}% |\n")
            else:
                f.write(f"| **{bench_names[b_ticker]}** | **{stats['mean']:.2f}%** | {stats['max']:.2f}% <br>({stats['max_range']}) | {stats['min']:.2f}% <br>({stats['min_range']}) | {stats['std']:.2f}% | {stats['win_rate']:.1f}% |\n")
            for x in benchmark_results[b_ticker]:
                plot_data.append({"Strategy": plot_names[bench_names[b_ticker]], "CAGR": x[0] * 100})

        f.write("\n## 📈 2. CAGR 분포 분석 (Percentiles)\n\n")
        f.write("| 전략/벤치마크 | 10% (하위) | 25% | 50% (Median) | 75% | 90% (상위) |\n")
        f.write("| :--- | :--- | :--- | :--- | :--- | :--- |\n")
        
        # Strategy cases distribution
        for i in range(1, 7):
            stats = all_stats.get(case_names[i])
            if stats:
                f.write(f"| {case_names[i]} | {stats['p10']:.2f}% | {stats['p25']:.2f}% | **{stats['p50']:.2f}%** | {stats['p75']:.2f}% | {stats['p90']:.2f}% |\n")
        
        f.write("| --- | --- | --- | --- | --- | --- |\n")
        
        # Benchmarks distribution
        for b_ticker in [ticker, "SOXX", "VOO", "QQQ"]:
            stats = all_stats.get(bench_names[b_ticker])
            if stats:
                f.write(f"| **{bench_names[b_ticker]}** | {stats['p10']:.2f}% | {stats['p25']:.2f}% | **{stats['p50']:.2f}%** | {stats['p75']:.2f}% | {stats['p90']:.2f}% |\n")
        
        f.write("\n---\n")
        f.write("## 🚨 3. 이상치(Outlier) 상세 분석\n\n")
        f.write("Tukey의 IQR(Interquartile Range) 기준을 벗어난 예외적인 대박/쪽박 시뮬레이션 구간입니다.\n\n")
        
        for i in range(1, 7):
            stats = all_stats.get(case_names[i])
            if stats and stats['outliers']:
                f.write(f"### {case_names[i]}\n")
                f.write("| 유형 | 수익률(CAGR) | 발생 기간 |\n")
                f.write("| :--- | :--- | :--- |\n")
                for out in stats['outliers']:
                    type_icon = "🔴 대박" if out['type'] == "상방 예외" else "🔵 쪽박"
                    f.write(f"| {type_icon} | **{out['cagr']:.2f}%** | {out['range']} |\n")
                f.write("\n")

        f.write("---\n")
        f.write("## 💡 분석 의견\n")
        f.write("- 다양한 시작점과 종료점에서의 성과를 분석함으로써 특정 기간에 편향되지 않은 전략의 견고성을 확인할 수 있습니다.\n")
        f.write("- 표준편차가 낮을수록 수익의 변동성이 적어 안정적인 전략임을 의미합니다.\n")

    print(f"\n✅ 분석 완료! 보고서가 저장되었습니다: {report_path}")

    # 5. Generate Boxplot
    try:
        import matplotlib.pyplot as plt
        import seaborn as sns
        
        if plot_data:
            print("분포 그래프(Box Plot)를 생성하는 중...")
            df_plot = pd.DataFrame(plot_data)
            
            plt.figure(figsize=(14, 8))
            sns.set_theme(style="whitegrid")
            
            ax = sns.boxplot(x="CAGR", y="Strategy", hue="Strategy", data=df_plot, orient="h", palette="Set2", legend=False)
            plt.title(f"{ticker} RAOEO Batch Backtest CAGR Distribution", fontsize=16, pad=20)
            plt.xlabel("CAGR (%)", fontsize=12)
            plt.ylabel("Strategy & Benchmark", fontsize=12)
            
            # Add a vertical line at 0%
            plt.axvline(x=0, color='red', linestyle='--', linewidth=1.5)
            
            plt.tight_layout()
            
            plot_path = os.path.join(script_dir, f"batch_cagr_distribution{cash_ticker_suffix}.png")
            plt.savefig(plot_path, dpi=300)
            plt.close()
            print(f"✅ 분포 그래프가 저장되었습니다: {plot_path}")
            
    except ImportError:
        print("\n[알림] matplotlib 또는 seaborn 라이브러리가 설치되어 있지 않아 그래프를 생성하지 못했습니다.")
        print("그래프를 생성하려면 환경에 맞게 설치해주세요: pip install matplotlib seaborn")
    except Exception as e:
        print(f"\n그래프 생성 중 오류가 발생했습니다: {e}")

if __name__ == "__main__":
    main()
