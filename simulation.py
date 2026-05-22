"""
simulation.py
論文準拠のシミュレーションエンジン + GAS版の基本計算ロジック
"""

import numpy as np
import pandas as pd
from scipy import stats

# ── Shiller市場データ (1926–2022) ─────────────────────────────
MARKET_DATA_RAW = [
    (1926,0.114991,0.0368,17.7),(1927,0.37101,0.0334,17.3),
    (1928,0.475713,0.0333,17.1),(1929,-0.094594,0.036,17.2),
    (1930,-0.227246,0.0329,16.1),(1931,-0.441963,0.0334,14.6),
    (1932,-0.058116,0.0368,13.1),(1933,0.567454,0.0331,13.2),
    (1934,-0.080121,0.0312,13.4),(1935,0.549299,0.0279,13.8),
    (1936,0.325451,0.0265,14.0),(1937,-0.321062,0.0268,14.4),
    (1938,0.174993,0.0256,14.0),(1939,0.029804,0.0236,14.0),
    (1940,-0.089142,0.0221,14.1),(1941,-0.090929,0.0195,15.5),
    (1942,0.217384,0.0246,16.9),(1943,0.236012,0.0247,17.4),
    (1944,0.196681,0.0248,17.8),(1945,0.393458,0.0237,18.2),
    (1946,-0.120538,0.0219,21.5),(1947,0.025611,0.0225,23.4),
    (1948,0.095076,0.0244,24.1),(1949,0.174821,0.0231,23.6),
    (1950,0.34383,0.0232,25.0),(1951,0.219161,0.0257,26.5),
    (1952,0.146899,0.0268,26.7),(1953,0.030097,0.0283,26.9),
    (1954,0.467921,0.0248,26.7),(1955,0.289089,0.0261,26.8),
    (1956,0.06865,0.029,27.6),(1957,-0.058096,0.0346,28.4),
    (1958,0.403844,0.0309,28.9),(1959,0.076305,0.0402,29.4),
    (1960,0.065327,0.0472,29.8),(1961,0.190854,0.0384,30.0),
    (1962,-0.025947,0.0408,30.4),(1963,0.212099,0.0383,30.9),
    (1964,0.159758,0.0417,31.2),(1965,0.115994,0.0419,31.8),
    (1966,-0.064147,0.0461,32.9),(1967,0.161169,0.0458,33.9),
    (1968,0.106159,0.0553,35.5),(1969,-0.085532,0.0604,37.7),
    (1970,0.075437,0.0779,39.8),(1971,0.140003,0.0624,41.1),
    (1972,0.178641,0.0595,42.5),(1973,-0.162883,0.0646,46.2),
    (1974,-0.210751,0.0699,51.9),(1975,0.391907,0.075,55.5),
    (1976,0.112093,0.0774,58.2),(1977,-0.090407,0.0721,62.1),
    (1978,0.162352,0.0796,67.7),(1979,0.171154,0.091,76.7),
    (1980,0.260202,0.108,86.3),(1981,-0.072209,0.1257,94.0),
    (1982,0.301138,0.1459,97.6),(1983,0.203721,0.1046,101.3),
    (1984,0.079156,0.1167,105.3),(1985,0.263861,0.1138,109.3),
    (1986,0.313966,0.0919,110.5),(1987,-0.023927,0.0708,115.4),
    (1988,0.17925,0.0867,120.5),(1989,0.229694,0.0909,126.1),
    (1990,-0.008515,0.0821,133.8),(1991,0.319522,0.0809,137.9),
    (1992,0.077388,0.0703,141.9),(1993,0.117056,0.066,145.8),
    (1994,0.011523,0.0575,149.7),(1995,0.353152,0.0778,153.5),
    (1996,0.273633,0.0565,158.6),(1997,0.279097,0.0658,161.3),
    (1998,0.31508,0.0554,163.9),(1999,0.155757,0.0472,168.3),
    (2000,-0.052107,0.0666,174.0),(2001,-0.134709,0.0516,176.7),
    (2002,-0.20128,0.0504,180.9),(2003,0.285689,0.0405,184.3),
    (2004,0.060438,0.0415,190.3),(2005,0.101211,0.0422,196.8),
    (2006,0.133759,0.0442,201.8),(2007,-0.014394,0.0476,210.036),
    (2008,-0.35629,0.0374,210.228),(2009,0.333247,0.0252,215.949),
    (2010,0.163817,0.0373,219.179),(2011,0.033823,0.0339,225.672),
    (2012,0.161927,0.0197,229.601),(2013,0.255843,0.0191,233.049),
    (2014,0.134571,0.0286,234.812),(2015,-0.034561,0.0188,236.525),
    (2016,0.211016,0.0209,241.432),(2017,0.2498,0.0243,246.524),
    (2018,-0.047619,0.0258,251.233),(2019,0.281337,0.0271,256.974),
    (2020,0.178662,0.0176,260.474),(2021,0.22208,0.0108,278.802),
    (2022,-0.120211,0.0176,296.797),
]

def load_market_data() -> pd.DataFrame:
    df = pd.DataFrame(MARKET_DATA_RAW, columns=["year","sp500","bond","cpi"])
    df["cpi_inf"] = df["cpi"].pct_change().fillna(0)
    return df

MARKET_DF = load_market_data()

# ── 定数 ─────────────────────────────────────────────────────
INITIAL_ASSET  = 1_000_000
SIM_YEARS      = 30
RANDOM_SEED    = 42

MC_PARAMS = {
    "baseline":   dict(eq_mu=0.118, eq_sd=0.195, bd_mu=0.033, inf_mu=0.030, inf_sd=0.040),
    "low_return": dict(eq_mu=0.070, eq_sd=0.220, bd_mu=0.015, inf_mu=0.040, inf_sd=0.045),
}
T_DF = 5

# ── コアシミュレーション（論文完全準拠） ────────────────────
def simulate_window(seq, wr, labor_ratio, stock_w, bond_w, thr_mult):
    """
    seq: list of (sp500, bond, cpi_inf) tuples, length 30
    labor_ratio: 0.0=完全停止, 0.5=半額停止, 1.0=ベースライン
    thr_mult: 閾値乗数（5/7/10など）
    """
    asset      = INITIAL_ASSET
    base_wd    = asset * wr
    cpi_factor = 1.0
    labor_yrs  = 0
    labor_events = 0
    labor_active = False
    max_asset  = asset
    max_dd     = 0.0
    trajectory = []

    for sp, bond, cpi_inf in seq:
        port_ret = stock_w * sp + bond_w * bond
        asset   *= (1 + port_ret)
        max_asset = max(max_asset, asset)

        cpi_factor *= (1 + cpi_inf)
        cpi_wd      = min(base_wd * cpi_factor, asset)
        threshold   = cpi_wd * thr_mult

        if asset < threshold:
            if not labor_active:
                labor_events += 1
            labor_active = True
        else:
            labor_active = False

        if labor_active:
            labor_yrs += 1

        wd    = cpi_wd * labor_ratio if labor_active else cpi_wd
        asset = max(asset - wd, 0.0)

        dd = (max_asset - asset) / max_asset if max_asset > 0 else 0
        max_dd = max(max_dd, dd)

        trajectory.append({
            "asset": asset, "threshold": threshold,
            "labor_active": labor_active, "cpi_factor": cpi_factor,
        })
        if asset <= 0:
            break

    return {
        "final_asset":   asset,
        "success":       asset > 0,
        "labor_years":   labor_yrs,
        "labor_events":  labor_events,
        "max_drawdown":  max_dd,
        "trajectory":    trajectory,
    }

# ── ローリングウィンドウ ────────────────────────────────────
def run_rolling(wr, labor_ratio, stock_w, bond_w, thr_mult=10) -> list:
    df   = MARKET_DF
    n    = len(df)
    results = []
    for start in range(n - SIM_YEARS + 1):
        seg = df.iloc[start:start + SIM_YEARS]
        seq = list(zip(seg["sp500"], seg["bond"], seg["cpi_inf"]))
        r   = simulate_window(seq, wr, labor_ratio, stock_w, bond_w, thr_mult)
        r["start_year"] = int(df.iloc[start]["year"])
        results.append(r)
    return results

# ── モンテカルロ（t分布 fat-tail） ──────────────────────────
def run_monte_carlo(scenario, wr, labor_ratio, stock_w, bond_w,
                    thr_mult=10, n_sim=500, seed=RANDOM_SEED) -> list:
    rng = np.random.default_rng(seed)
    p   = MC_PARAMS[scenario]

    def t_sample(mu, sd, size):
        z    = rng.standard_normal(size)
        chi2 = rng.standard_gamma(T_DF / 2, size) * 2
        t    = z / np.sqrt(chi2 / T_DF)
        return mu + sd * t * np.sqrt((T_DF - 2) / T_DF)

    results = []
    for _ in range(n_sim):
        eq  = t_sample(p["eq_mu"],  p["eq_sd"],  SIM_YEARS)
        bd  = np.full(SIM_YEARS, p["bd_mu"]) + rng.standard_normal(SIM_YEARS) * 0.01
        inf = np.clip(t_sample(p["inf_mu"], p["inf_sd"], SIM_YEARS), -0.05, None)
        seq = list(zip(eq, bd, inf))
        results.append(simulate_window(seq, wr, labor_ratio, stock_w, bond_w, thr_mult))
    return results

# ── 集計ヘルパー ─────────────────────────────────────────────
def summarize(results: list) -> dict:
    finals  = [r["final_asset"] for r in results]
    success = [r["success"]     for r in results]
    labors  = [r["labor_years"] for r in results]
    dds     = [r["max_drawdown"] for r in results]
    finals_sorted = sorted(finals)
    n = len(finals_sorted)
    return {
        "success_rate":    np.mean(success),
        "median_final":    np.median(finals) / INITIAL_ASSET,
        "mean_labor_yrs":  np.mean(labors),
        "mean_labor_events": np.mean([r["labor_events"] for r in results]),
        "mean_max_dd":     np.mean(dds),
        "p10_final":       finals_sorted[int(n * 0.10)] / INITIAL_ASSET,
        "p25_final":       finals_sorted[int(n * 0.25)] / INITIAL_ASSET,
        "p75_final":       finals_sorted[int(n * 0.75)] / INITIAL_ASSET,
        "p90_final":       finals_sorted[int(n * 0.90)] / INITIAL_ASSET,
    }

def percentile_bands(results: list, scale: float = 1.0) -> pd.DataFrame:
    """30年分のパーセンタイル帯をDataFrameで返す"""
    rows = []
    for yr in range(SIM_YEARS):
        vals = [r["trajectory"][yr]["asset"] * scale
                for r in results if len(r["trajectory"]) > yr]
        if not vals:
            continue
        vals_s = sorted(vals)
        n = len(vals_s)
        rows.append({
            "year": yr + 1,
            "p10":  vals_s[max(0, int(n * 0.10))],
            "p25":  vals_s[max(0, int(n * 0.25))],
            "p50":  vals_s[max(0, int(n * 0.50))],
            "p75":  vals_s[max(0, int(n * 0.75))],
            "p90":  vals_s[min(n-1, int(n * 0.90))],
        })
    return pd.DataFrame(rows)

# ── GAS版の基本計算ロジック（Python移植） ────────────────────
TAKEHOME_TABLE = [
    (500,0.80),(600,0.78),(700,0.76),(800,0.74),(900,0.72),
    (1000,0.70),(1200,0.68),(1500,0.66),(1800,0.65),(2000,0.64),
    (2500,0.62),(3000,0.60),(3500,0.59),(4000,0.58),(4500,0.57),(5000,0.56),
]

def get_takehome_rate(income: float) -> float:
    tbl = TAKEHOME_TABLE
    for i in range(len(tbl) - 1):
        x1, y1 = tbl[i]
        x2, y2 = tbl[i + 1]
        if income <= x1:
            return y1
        if income < x2:
            return y1 + (income - x1) * (y2 - y1) / (x2 - x1)
    return 0.55

EDU_DEFAULTS = {
    "elem":  {"public": 100,  "private": 600},
    "mid":   {"public": 150,  "private": 300},
    "high":  {"public": 150,  "private": 300},
    "uni":   {"national": 250, "private_liberal": 400,
               "private_science": 600, "medical": 3000},
}

def calc_edu_pv(child_age: int, elem, mid, high, uni,
                r: float,
                edu_manual: dict = None) -> float:
    """子1人分の教育費現在価値（万円）"""
    if edu_manual is None:
        edu_manual = {}
    total = 0.0

    def pv(cost, years):
        return cost / (1 + r) ** years if years > 0 else cost

    stages = [
        ("elem", 6,  elem),
        ("mid",  12, mid),
        ("high", 15, high),
        ("uni",  18, uni),
    ]
    for stage, start_age, choice in stages:
        if child_age < start_age:
            if stage in edu_manual:
                cost = edu_manual[stage]
            else:
                cost = EDU_DEFAULTS[stage][choice]
            total += pv(cost, start_age - child_age)

    return total

def basic_fire_calc(
    age, income, assets, monthly_expense, monthly_fun,
    children_ages, elem, mid, high, uni,
    risk, can_work, return_mode, manual_return,
    inflation_mode, manual_inflation,
    invest_mode, manual_invest,
    edu_manual=None,
) -> dict:
    """GAS版のcalculate()をPythonに完全移植"""

    # 手取り
    rate      = get_takehome_rate(income)
    take_home = income * rate

    # 支出
    base_annual = (monthly_expense + monthly_fun) * 12
    emergency   = monthly_expense * 6

    # 利回り
    if return_mode == "manual":
        r       = manual_return
        sp_r    = None
        nq_r    = None
    else:
        nq = {"low": 0.0, "mid": 0.20, "high": 0.35}[risk]
        sp = 1 - nq
        r  = sp * 0.10 + nq * 0.15
        sp_r = sp
        nq_r = nq

    # インフレ
    inflation = manual_inflation if inflation_mode == "manual" else 0.02

    # 取り崩し率（論文準拠：can_workでも閾値モデル使用、ここでは初期設定値）
    wr = 0.06 if can_work else 0.04

    # 教育費PV
    edu_pv = 0.0
    for ca in children_ages:
        edu_pv += calc_edu_pv(ca, elem, mid, high, uni, r, edu_manual)

    # 投資可能資産
    investable   = max(0.0, assets - emergency - edu_pv)

    # 月間投資額
    if invest_mode == "manual":
        invest_per_year = manual_invest * 12
    else:
        invest_per_year = take_home - base_annual

    fire_target = base_annual / wr

    # シミュレーション
    current    = investable
    assets_arr = []
    t          = 0
    fire_age   = None
    is_fire    = False

    while current > 0 and t < 100:
        annual_expense = base_annual * (1 + inflation) ** t
        if not is_fire and current >= fire_target:
            fire_age = age + t
            is_fire  = True
        assets_arr.append(round(current))
        if is_fire:
            current = current * (1 + r) - annual_expense
        else:
            current = current * (1 + r) + invest_per_year
        if current <= 0:
            assets_arr.append(0)
            break
        t += 1

    return {
        "take_home":        round(take_home),
        "annual_expense":   round(base_annual),
        "emergency":        round(emergency),
        "monthly_invest":   round(invest_per_year / 12),
        "fire_age":         fire_age,
        "fire_target":      round(fire_target),
        "monthly_withdraw": round(base_annual / 12),
        "withdraw_rate":    round(wr * 100),
        "current_withdraw": round((investable * wr) / 12),
        "edu_pv":           round(edu_pv),
        "assets_arr":       assets_arr,
        "r":                round(r * 100, 1),
        "inflation":        round(inflation * 100, 1),
        "sp_ratio":         round(sp_r * 100) if sp_r is not None else None,
        "nq_ratio":         round(nq_r * 100) if nq_r is not None else None,
        "investable":       round(investable),
    }
