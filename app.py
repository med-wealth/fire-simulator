"""
app.py  — Medwealth Lab Tokyo | FIRE Simulator
Human Capital Safety Valve 論文準拠 + GAS版機能完全移植
v3: 基本FIREシミュレーションのみ無料公開 / 他タブは近日公開予定ロック
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from simulation import (
    run_rolling, run_monte_carlo, summarize, percentile_bands,
    basic_fire_calc, MARKET_DF, INITIAL_ASSET,
)

# ── ページ設定 ────────────────────────────────────────────────
st.set_page_config(
    page_title="FIRE Simulator | Medwealth Lab Tokyo",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

C = dict(
    complete="#009E73", half="#56B4E9", baseline="#E69F00",
    gray="#999999", blue="#0072B2", red="#D55E00",
)

st.markdown("""
<style>
.metric-card {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.09);
    border-radius: 12px; padding: 16px 20px; text-align: center;
}
.metric-label { font-size:11px; color:#8a9bb0; letter-spacing:1px; text-transform:uppercase; margin-bottom:6px; }
.metric-value { font-size:26px; font-weight:800; }
.warning-box {
    background:rgba(213,94,0,0.12); border:1px solid #D55E00;
    border-radius:10px; padding:14px 18px; font-size:13px; line-height:1.7;
}
.success-box {
    background:rgba(0,158,115,0.12); border:1px solid #009E73;
    border-radius:10px; padding:14px 18px; font-size:13px;
}
.section-title {
    font-size:11px; font-weight:700; color:#8a9bb0;
    letter-spacing:2px; text-transform:uppercase; margin-bottom:12px;
}
.lock-box {
    background:rgba(255,255,255,0.03);
    border:1px solid rgba(255,255,255,0.12);
    border-radius:14px;
    padding:48px 32px;
    text-align:center;
    margin-top:24px;
}
.lock-icon { font-size:48px; margin-bottom:16px; }
.lock-title { font-size:20px; font-weight:700; color:#c8d6e0; margin-bottom:10px; }
.lock-desc { font-size:14px; color:#8a9bb0; line-height:1.8; }
</style>
""", unsafe_allow_html=True)

# ── 有料ゲート ────────────────────────────────────────────────
def check_paid(pw):
    try:
        return pw == st.secrets["PAID_PASSWORD"]
    except Exception:
        return pw == "0216"

# ── 論文推奨シナリオ定義（session_state連携用） ──────────────
PAPER_SCENARIOS_DEF = [
    dict(label="Scenario A", wr_pct=6, port="100/0", hc="complete", thr=10),
    dict(label="Scenario B", wr_pct=5, port="100/0", hc="half",     thr=10),
    dict(label="Scenario C", wr_pct=5, port="75/25", hc="complete", thr=10),
    dict(label="4%ルール",   wr_pct=4, port="75/25", hc="complete", thr=10),
]

# ── ヘッダー ─────────────────────────────────────────────────
col_h1, col_h2 = st.columns([5, 1])
with col_h1:
    st.markdown("### 📊 FIRE Simulator")
    st.caption("Medwealth Lab Tokyo  |  Shillerデータ 1926–2022")
with col_h2:
    paid_pw = st.text_input("プロモード", type="password", key="pw", placeholder="パスワード")

is_paid = check_paid(paid_pw)
if is_paid:
    st.success("✅ プロモード有効")

# ── タブ ─────────────────────────────────────────────────────
tab_basic, tab_hcsv, tab_traj, tab_scenarios = st.tabs([
    "🏠 基本FIREシミュレーション",
    "🛡 人的資本セーフティバルブ",
    "📈 軌跡分析",
    "📋 論文推奨シナリオ",
])

# ════════════════════════════════════════════════════════════
# TAB 1: 基本FIREシミュレーション（完全無料）
# ════════════════════════════════════════════════════════════
with tab_basic:
    st.markdown('<div class="section-title">基本情報</div>', unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    with c1:
        age    = st.number_input("現在の年齢", 20, 70, 35)
        income = st.number_input("年収（万円）", 0, 10000, 1500, step=100)
        assets = st.number_input("現在の資産（万円）", 0, 100000, 3000, step=100)
    with c2:
        monthly_expense = st.number_input("月間生活費（万円）", 0, 100, 30)
        monthly_fun     = st.number_input("月間遊興費（万円）", 0, 50, 5)
        children_str    = st.text_input("子供の年齢（カンマ区切り）", "")
    with c3:
        risk        = st.selectbox("リスク許容度", ["low","mid","high"], index=1,
                                   format_func=lambda x: {"low":"低","mid":"中","high":"高"}[x])
        can_work    = st.selectbox("暴落時に働ける職種ですか？", [True, False],
                                   format_func=lambda x: "はい（医師・エンジニア等）" if x else "いいえ")
        return_mode = st.selectbox("利回り設定", ["auto","manual"],
                                   format_func=lambda x: "自動" if x=="auto" else "手動")
        manual_return = st.number_input("手動利回り（%）", 0.0, 20.0, 7.0) / 100 if return_mode=="manual" else 0.0

        wr_mode_basic = st.selectbox("取り崩し率設定", ["auto","manual"],
                                     format_func=lambda x: "自動（can_work連動）" if x=="auto" else "手動")
        manual_wr_basic = st.number_input("手動取り崩し率（%）", 1.0, 15.0, 6.0, step=0.5) / 100 if wr_mode_basic=="manual" else None

    with st.expander("詳細設定（インフレ・投資額・教育費）"):
        c4, c5 = st.columns(2)
        with c4:
            inflation_mode   = st.selectbox("インフレ設定", ["auto","manual"],
                                            format_func=lambda x: "自動（2%）" if x=="auto" else "手動")
            manual_inflation = st.number_input("手動インフレ率（%）", 0.0, 10.0, 2.0) / 100 if inflation_mode=="manual" else 0.0
            invest_mode      = st.selectbox("月間投資額", ["auto","manual"],
                                            format_func=lambda x: "自動（収入−支出）" if x=="auto" else "手動")
            manual_invest    = st.number_input("手動投資額（万円/月）", 0, 500, 30) if invest_mode=="manual" else 0
        with c5:
            st.markdown("**教育費設定**")
            edu_cols = st.columns(2)
            with edu_cols[0]:
                elem_mode = st.selectbox("小学校", ["public","private","manual"],
                                         format_func=lambda x: {"public":"公立","private":"私立","manual":"手動入力"}[x])
                elem_manual = st.number_input("小学校費用（万円）", 0, 2000, 100) if elem_mode=="manual" else None

                mid_mode  = st.selectbox("中学校", ["public","private","manual"],
                                          format_func=lambda x: {"public":"公立","private":"私立","manual":"手動入力"}[x])
                mid_manual = st.number_input("中学校費用（万円）", 0, 2000, 150) if mid_mode=="manual" else None
            with edu_cols[1]:
                high_mode = st.selectbox("高校", ["public","private","manual"],
                                          format_func=lambda x: {"public":"公立","private":"私立","manual":"手動入力"}[x])
                high_manual = st.number_input("高校費用（万円）", 0, 2000, 150) if high_mode=="manual" else None

                uni_mode  = st.selectbox("大学", ["national","private_liberal","private_science","medical","manual"],
                                          format_func=lambda x: {
                                              "national":"国公立","private_liberal":"私立文系",
                                              "private_science":"私立理系","medical":"私立医歯薬",
                                              "manual":"手動入力"}[x])
                uni_manual = st.number_input("大学費用（万円）", 0, 5000, 250) if uni_mode=="manual" else None

    if st.button("▶ 基本シミュレーション実行", type="primary", key="run_basic"):
        children_ages = [int(s.strip()) for s in children_str.split(",") if s.strip().isdigit()]

        edu_manual = {}
        for stage, mode, val in [
            ("elem", elem_mode, elem_manual),
            ("mid",  mid_mode,  mid_manual),
            ("high", high_mode, high_manual),
            ("uni",  uni_mode,  uni_manual),
        ]:
            if mode == "manual" and val is not None:
                edu_manual[stage] = val

        elem_key = "public" if elem_mode != "private" else "private"
        mid_key  = "public" if mid_mode  != "private" else "private"
        high_key = "public" if high_mode != "private" else "private"
        uni_key  = uni_mode if uni_mode not in ("manual",) else "national"

        res = basic_fire_calc(
            age=age, income=income, assets=assets,
            monthly_expense=monthly_expense, monthly_fun=monthly_fun,
            children_ages=children_ages,
            elem=elem_key, mid=mid_key, high=high_key, uni=uni_key,
            risk=risk, can_work=can_work,
            return_mode=return_mode, manual_return=manual_return,
            inflation_mode=inflation_mode, manual_inflation=manual_inflation,
            invest_mode=invest_mode, manual_invest=manual_invest,
            edu_manual=edu_manual,
            manual_wr=manual_wr_basic,
        )
        st.session_state["basic_res"] = res
        st.session_state["basic_age"] = age

    if "basic_res" in st.session_state:
        res      = st.session_state["basic_res"]
        base_age = st.session_state["basic_age"]

        k1, k2, k3, k4 = st.columns(4)
        fire_age_disp = f"{res['fire_age']}歳" if res["fire_age"] else "到達困難"
        fire_color    = C["complete"] if res["fire_age"] else C["red"]
        for col, label, value, color in [
            (k1, "FIRE到達年齢", fire_age_disp, fire_color),
            (k2, "必要資産",     f"{res['fire_target']:,}万円", C["blue"]),
            (k3, "手取り年収",   f"{res['take_home']:,}万円",   C["half"]),
            (k4, "教育費PV",     f"{res['edu_pv']:,}万円",      C["baseline"]),
        ]:
            col.markdown(f"""<div class="metric-card">
                <div class="metric-label">{label}</div>
                <div class="metric-value" style="color:{color}">{value}</div>
            </div>""", unsafe_allow_html=True)

        st.markdown("")
        s1, s2, s3, s4, s5 = st.columns(5)
        s1.metric("利回り", f"{res['r']}%")
        s2.metric("インフレ率", f"{res['inflation']}%")
        s3.metric("取り崩し率", f"{res['withdraw_rate']}%")
        s4.metric("月間取り崩し額", f"{res['monthly_withdraw']}万円")
        s5.metric("月間取り崩し可能額", f"{res['current_withdraw']}万円")

        if res["sp_ratio"] is not None:
            st.caption(f"ポートフォリオ：S&P500 {res['sp_ratio']}% / NASDAQ100 {res['nq_ratio']}%")

        arr  = res["assets_arr"]
        ages = list(range(base_age, base_age + len(arr)))

        fire_target = res["fire_target"]
        y_max = fire_target * 10

        clip = []
        for a, v in zip(ages, arr):
            if a > 100:
                break
            if v >= y_max:
                clip.append((a, y_max))
                break
            clip.append((a, v))

        if clip:
            ages_c, arr_c = zip(*clip)
        else:
            ages_c, arr_c = ages, arr

        x_max = ages_c[-1]

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=list(ages_c), y=list(arr_c), mode="lines",
            line=dict(color=C["complete"], width=2.5),
            name="資産推移",
            hovertemplate="年齢 %{x}歳<br>資産 %{y:,}万円<extra></extra>",
        ))
        if res["fire_age"] and res["fire_age"] <= x_max:
            fig.add_vline(x=res["fire_age"], line_dash="dash",
                          line_color=C["blue"], annotation_text=f"FIRE {res['fire_age']}歳")
        fig.add_hline(y=fire_target, line_dash="dot",
                      line_color=C["baseline"], annotation_text="必要資産")
        fig.update_layout(
            title="資産推移シミュレーション（〜100歳）",
            xaxis_title="年齢（歳）", yaxis_title="資産（万円）",
            xaxis=dict(range=[base_age, x_max]),
            yaxis=dict(range=[0, y_max]),
            template="plotly_dark", height=400,
            paper_bgcolor="#1a2635", plot_bgcolor="#1a2635",
        )
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("**年齢別資産（5年刻み）**")
        st.caption("※ 教育費（現在価値）を控除した投資可能資産をベースに計算しています。教育費は別途積み立てが必要です。")
        rows = [(base_age + i, f"{arr[i]:,}万円")
                for i in range(0, len(arr), 5) if base_age + i <= 100]
        st.dataframe(pd.DataFrame(rows, columns=["年齢","資産"]),
                     hide_index=True, use_container_width=False)

# ════════════════════════════════════════════════════════════
# ロック表示ヘルパー
# ════════════════════════════════════════════════════════════
def show_lock():
    st.markdown("""
    <div class="lock-box">
        <div class="lock-icon">🔒</div>
        <div class="lock-title">近日公開予定</div>
        <div class="lock-desc">
            この機能は現在準備中です。<br>
            公開をお楽しみに。
        </div>
    </div>
    """, unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════
# TAB 2: 人的資本セーフティバルブ
# ════════════════════════════════════════════════════════════
with tab_hcsv:
    if not is_paid:
        show_lock()
    else:
        st.markdown('<div class="section-title">Human Capital Safety Valve シミュレーション</div>',
                    unsafe_allow_html=True)
        st.caption("論文準拠：Shillerデータ 1926–2022 ローリングウィンドウ / モンテカルロ（t分布 df=5）")

        st.markdown("**論文推奨シナリオをワンクリックで反映：**")
        sc_cols = st.columns(4)
        for i, sc in enumerate(PAPER_SCENARIOS_DEF):
            if sc_cols[i].button(sc["label"], key=f"sc_hcsv_{i}"):
                st.session_state["hcsv_preset"] = sc

        preset = st.session_state.get("hcsv_preset", {})

        col_p1, col_p2, col_p3 = st.columns(3)
        with col_p1:
            hcsv_initial = st.number_input("初期資産（万円）", 100, 999999, 10000, step=500)
            wr_pct = st.select_slider("取り崩し率",
                                       options=[4,5,6,7,8,9,10],
                                       value=preset.get("wr_pct", 6))
            wr = wr_pct / 100
            portfolio = st.selectbox("ポートフォリオ（株/債券）", ["100/0","75/25","50/50"],
                                      index=["100/0","75/25","50/50"].index(preset.get("port","100/0")))
        with col_p2:
            hc_default = preset.get("hc", "complete")
            hc_model = st.radio("人的資本モデル", ["complete","half","none"],
                                 index=["complete","half","none"].index(hc_default),
                                 format_func=lambda x: {
                                     "complete":"Complete Cessation（取り崩しゼロ）",
                                     "half":    "Half Reduction（取り崩し50%）",
                                     "none":    "Baseline（人的資本なし）"}[x])
            labor_ratio = {"complete":0.0,"half":0.5,"none":1.0}[hc_model]
        with col_p3:
            thr_mult   = st.select_slider("閾値（生活費の何年分）",
                                           options=[5,7,10],
                                           value=preset.get("thr", 10))
            sim_method = st.radio("シミュレーション手法", ["rolling","montecarlo"],
                                   format_func=lambda x: "ローリングウィンドウ" if x=="rolling" else "モンテカルロ")

            sim_years_hcsv = st.slider(
                "シミュレーション期間（年）",
                min_value=10, max_value=50, value=30, step=1,
                help="📌 30年推奨（論文準拠）。50年まで延長可能。"
            )
            if sim_years_hcsv == 30:
                st.caption("✅ 30年（論文推奨）")
            else:
                st.caption(f"⚠️ {sim_years_hcsv}年（論文基準は30年）")

        if sim_method == "montecarlo":
            mc_col1, mc_col2 = st.columns(2)
            with mc_col1:
                mc_scenario = st.selectbox("MCシナリオ", ["baseline","low_return"],
                                            format_func=lambda x: "歴史的平均" if x=="baseline" else "低リターン（株式7%、インフレ4%）")
            with mc_col2:
                mc_n = st.slider("試行回数", 100, 1000, 500, step=100)

        stock_w, bond_w = {"100/0":(1.0,0.0),"75/25":(0.75,0.25),"50/50":(0.5,0.5)}[portfolio]

        if st.button("▶ シミュレーション実行", type="primary", key="run_hcsv"):
            with st.spinner(f"計算中...（{sim_years_hcsv}年間シミュレーション）"):
                if sim_method == "rolling":
                    results_hc   = run_rolling(wr, labor_ratio, stock_w, bond_w, thr_mult, sim_years=sim_years_hcsv)
                    results_base = run_rolling(wr, 1.0,         stock_w, bond_w, thr_mult, sim_years=sim_years_hcsv)
                else:
                    results_hc   = run_monte_carlo(mc_scenario, wr, labor_ratio, stock_w, bond_w, thr_mult, mc_n, sim_years=sim_years_hcsv)
                    results_base = run_monte_carlo(mc_scenario, wr, 1.0,         stock_w, bond_w, thr_mult, mc_n, sim_years=sim_years_hcsv)

            st.session_state["hcsv_hc"]      = results_hc
            st.session_state["hcsv_base"]    = results_base
            st.session_state["hcsv_initial"] = hcsv_initial
            st.session_state["hcsv_sim_yrs"] = sim_years_hcsv
            st.session_state["hcsv_params"]  = dict(wr=wr, portfolio=portfolio, hc_model=hc_model,
                                                      thr_mult=thr_mult, labor_ratio=labor_ratio,
                                                      stock_w=stock_w, bond_w=bond_w)

        if "hcsv_hc" in st.session_state:
            r_hc   = st.session_state["hcsv_hc"]
            r_base = st.session_state["hcsv_base"]
            h_init = st.session_state["hcsv_initial"]
            h_syrs = st.session_state["hcsv_sim_yrs"]
            params = st.session_state["hcsv_params"]

            s_hc   = summarize(r_hc)
            s_base = summarize(r_base)

            median_final_man = s_hc["median_final"] * h_init

            k1, k2, k3, k4, k5 = st.columns(5)
            sr_color = C["complete"] if s_hc["success_rate"] >= 0.95 else C["red"]
            for col, label, val, color in [
                (k1, "成功率（HC）",     f"{s_hc['success_rate']*100:.1f}%",  sr_color),
                (k2, "成功率（Base）",   f"{s_base['success_rate']*100:.1f}%", C["baseline"]),
                (k3, "中央値最終資産",   f"{median_final_man:,.0f}万円",       C["blue"]),
                (k4, "平均就労復帰年数", f"{s_hc['mean_labor_yrs']:.1f}年",   C["half"]),
                (k5, "平均最大DD",       f"{s_hc['mean_max_dd']*100:.0f}%",   C["red"]),
            ]:
                col.markdown(f"""<div class="metric-card">
                    <div class="metric-label">{label}</div>
                    <div class="metric-value" style="color:{color}">{val}</div>
                </div>""", unsafe_allow_html=True)

            st.markdown("")

            if s_hc["success_rate"] < 0.95:
                st.markdown(f"""<div class="warning-box">
                ⚠️ 成功率{s_hc['success_rate']*100:.0f}%。取り崩し率を下げるか、人的資本モデルを強化してください。
                </div>""", unsafe_allow_html=True)
            elif s_hc["mean_labor_yrs"] > 10:
                st.markdown(f"""<div class="warning-box">
                ⚠️ 成功率{s_hc['success_rate']*100:.0f}%ですが、平均就労復帰{s_hc['mean_labor_yrs']:.1f}年と長めです。
                </div>""", unsafe_allow_html=True)
            else:
                st.markdown(f"""<div class="success-box">
                ✅ 成功率{s_hc['success_rate']*100:.0f}%、平均就労復帰{s_hc['mean_labor_yrs']:.1f}年。現実的な範囲でのFIREが可能です。
                </div>""", unsafe_allow_html=True)

            st.markdown("")

            scale_man = h_init / INITIAL_ASSET
            df_hc  = percentile_bands(r_hc,   scale_man)
            df_bas = percentile_bands(r_base, scale_man)

            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=pd.concat([df_hc["year"], df_hc["year"][::-1]]),
                y=pd.concat([df_hc["p75"], df_hc["p25"][::-1]]),
                fill="toself", fillcolor="rgba(0,158,115,0.15)",
                line=dict(color="rgba(0,0,0,0)"), name="HC 25–75%tile", hoverinfo="skip",
            ))
            fig.add_trace(go.Scatter(
                x=df_hc["year"], y=df_hc["p50"],
                line=dict(color=C["complete"], width=2.5),
                name=f"HC中央値（{['Complete','Half','Baseline'][['complete','half','none'].index(hc_model)]}）",
            ))
            fig.add_trace(go.Scatter(
                x=df_hc["year"], y=df_hc["p10"],
                line=dict(color=C["complete"], width=1.2, dash="dot"),
                name="HC 10th pct", opacity=0.7,
            ))
            fig.add_trace(go.Scatter(
                x=df_bas["year"], y=df_bas["p50"],
                line=dict(color=C["baseline"], width=2.0, dash="dash"),
                name="Baseline中央値",
            ))
            fig.add_trace(go.Scatter(
                x=df_bas["year"], y=df_bas["p10"],
                line=dict(color=C["baseline"], width=1.0, dash="dot"),
                name="Base 10th pct", opacity=0.6,
            ))
            fig.add_hline(y=h_init, line_dash="dot", line_color=C["gray"], annotation_text="初期資産")
            fig.update_layout(
                title=f"資産推移パーセンタイル帯（初期資産{h_init:,}万円、{h_syrs}年間）",
                xaxis_title="退職後年数", yaxis_title="資産（万円）",
                template="plotly_dark", height=420,
                paper_bgcolor="#1a2635", plot_bgcolor="#1a2635",
                hovermode="x unified",
            )
            st.plotly_chart(fig, use_container_width=True)

            st.markdown('<div class="section-title">取り崩し率別 成功率比較</div>', unsafe_allow_html=True)
            with st.spinner("計算中..."):
                wrs_list, sr_hc_list, sr_base_list = [], [], []
                for w in [0.04,0.05,0.06,0.07,0.08,0.09,0.10]:
                    rh = run_rolling(w, params["labor_ratio"], params["stock_w"], params["bond_w"], params["thr_mult"], sim_years=h_syrs)
                    rb = run_rolling(w, 1.0, params["stock_w"], params["bond_w"], params["thr_mult"], sim_years=h_syrs)
                    wrs_list.append(f"{int(w*100)}%")
                    sr_hc_list.append(summarize(rh)["success_rate"] * 100)
                    sr_base_list.append(summarize(rb)["success_rate"] * 100)
            fig2 = go.Figure()
            fig2.add_trace(go.Scatter(x=wrs_list, y=sr_hc_list, mode="lines+markers",
                                       line=dict(color=C["complete"], width=2.5), marker=dict(size=8), name="人的資本あり"))
            fig2.add_trace(go.Scatter(x=wrs_list, y=sr_base_list, mode="lines+markers",
                                       line=dict(color=C["baseline"], width=2.0, dash="dash"), marker=dict(size=7), name="ベースライン"))
            fig2.add_hline(y=95, line_dash="dot", line_color=C["gray"], annotation_text="95%")
            fig2.update_layout(title=f"取り崩し率別成功率（{h_syrs}年間）",
                                xaxis_title="取り崩し率", yaxis_title="成功率（%）",
                                template="plotly_dark", height=340, yaxis=dict(range=[0,105]),
                                paper_bgcolor="#1a2635", plot_bgcolor="#1a2635")
            st.plotly_chart(fig2, use_container_width=True)

# ════════════════════════════════════════════════════════════
# TAB 3: 軌跡分析
# ════════════════════════════════════════════════════════════
with tab_traj:
    if not is_paid:
        show_lock()
    else:
        st.markdown('<div class="section-title">退職コホート別 軌跡分析</div>', unsafe_allow_html=True)

        st.markdown("**論文推奨シナリオをワンクリックで反映：**")
        tsc_cols = st.columns(4)
        for i, sc in enumerate(PAPER_SCENARIOS_DEF):
            if tsc_cols[i].button(sc["label"], key=f"sc_traj_{i}"):
                st.session_state["traj_preset"] = sc

        tpreset = st.session_state.get("traj_preset", {})

        t_col1, t_col2, t_col3 = st.columns(3)
        with t_col1:
            t_start_year = st.slider("退職開始年", 1926, 1992, 1928)
            t_wr_pct     = st.select_slider("取り崩し率（軌跡）",
                                             options=[4,5,6,7,8,9,10],
                                             value=tpreset.get("wr_pct", 6))
            t_initial    = st.number_input("初期資産（万円）", 100, 999999, 10000, step=500)
        with t_col2:
            t_portfolio  = st.selectbox("ポートフォリオ（軌跡）", ["100/0","75/25","50/50"],
                                         index=["100/0","75/25","50/50"].index(tpreset.get("port","100/0")))
            hc_default_t = tpreset.get("hc","complete")
            t_hc_model   = st.radio("人的資本モデル（軌跡）", ["complete","half","none"],
                                     index=["complete","half","none"].index(hc_default_t),
                                     format_func=lambda x: {"complete":"Complete","half":"Half","none":"Baseline"}[x])
        with t_col3:
            t_thr_mult = st.select_slider("閾値（軌跡）", options=[5,7,10],
                                           value=tpreset.get("thr", 10))
            t_sim_years = st.slider(
                "シミュレーション期間（年）",
                min_value=10, max_value=50, value=30, step=1,
                help="📌 30年推奨（論文準拠）",
                key="traj_sim_years"
            )
            if t_sim_years == 30:
                st.caption("✅ 30年（論文推奨）")
            else:
                st.caption(f"⚠️ {t_sim_years}年（論文基準は30年）")

        t_wr      = t_wr_pct / 100
        t_labor   = {"complete":0.0,"half":0.5,"none":1.0}[t_hc_model]
        t_stock_w, t_bond_w = {"100/0":(1.0,0.0),"75/25":(0.75,0.25),"50/50":(0.5,0.5)}[t_portfolio]

        from simulation import simulate_window, INITIAL_ASSET as SIM_INIT
        df_mkt    = MARKET_DF
        start_idx = df_mkt[df_mkt["year"] == t_start_year].index

        if len(start_idx) > 0 and start_idx[0] + t_sim_years <= len(df_mkt):
            seg = df_mkt.iloc[start_idx[0]:start_idx[0] + t_sim_years]
            seq = list(zip(seg["sp500"], seg["bond"], seg["cpi_inf"]))
            tr  = simulate_window(seq, t_wr, t_labor, t_stock_w, t_bond_w, t_thr_mult)

            traj       = tr["trajectory"]
            years_list = list(range(1, len(traj) + 1))
            asset_list = [d["asset"] / SIM_INIT * t_initial for d in traj]
            thr_list   = [d["threshold"] / SIM_INIT * t_initial for d in traj]
            labor_list = [d["labor_active"] for d in traj]

            k1, k2, k3, k4 = st.columns(4)
            final_val   = asset_list[-1]
            final_color = C["complete"] if final_val > t_initial else C["red"]
            n_yrs_label = f"{t_sim_years}年後資産"
            for col, label, val, color in [
                (k1, n_yrs_label,    f"{final_val:,.0f}万円",           final_color),
                (k2, "初期資産比",   f"×{final_val/t_initial:.2f}",     final_color),
                (k3, "就労復帰年数", f"{tr['labor_years']}年",           C["half"]),
                (k4, "最低資産",     f"{min(asset_list):,.0f}万円",      C["red"]),
            ]:
                col.markdown(f"""<div class="metric-card">
                    <div class="metric-label">{label}</div>
                    <div class="metric-value" style="color:{color}">{val}</div>
                </div>""", unsafe_allow_html=True)

            labor_bar = " ".join(["🟧" if l else "⬜" for l in labor_list])
            st.caption(f"就労復帰タイミング（橙＝就労復帰）：{labor_bar}")

            events = {1928:"⚠️ 大恐慌直前（論文最悪ケース）",
                      1969:"⚠️ スタグフレーション期",
                      1999:"⚠️ ドットコムバブル崩壊直前",
                      2000:"⚠️ ドットコムバブル崩壊",
                      2007:"⚠️ リーマンショック直前"}
            if t_start_year in events:
                st.warning(events[t_start_year])

            fig = go.Figure()
            in_ep, ep_start = False, None
            for yr, la in zip(years_list, labor_list):
                if la and not in_ep:
                    ep_start, in_ep = yr - 0.5, True
                elif not la and in_ep:
                    fig.add_vrect(x0=ep_start, x1=yr - 0.5,
                                  fillcolor="rgba(230,159,0,0.18)", layer="below", line_width=0)
                    in_ep = False
            if in_ep:
                fig.add_vrect(x0=ep_start, x1=years_list[-1] + 0.5,
                              fillcolor="rgba(230,159,0,0.18)", layer="below", line_width=0)

            fig.add_trace(go.Scatter(x=years_list, y=asset_list, mode="lines",
                                      line=dict(color=C["complete"], width=2.5), name="ポートフォリオ",
                                      hovertemplate="Year %{x}<br>%{y:,.0f}万円<extra></extra>"))
            fig.add_trace(go.Scatter(x=years_list, y=thr_list, mode="lines",
                                      line=dict(color=C["red"], width=1.5, dash="dash"), name="閾値（動的）",
                                      hovertemplate="Year %{x}<br>閾値 %{y:,.0f}万円<extra></extra>"))
            fig.add_hline(y=t_initial, line_dash="dot", line_color=C["gray"], annotation_text="初期資産")
            fig.update_layout(
                title=f"{t_start_year}年退職 — {t_sim_years}年軌跡（WR={t_wr_pct}%、{t_portfolio}、初期{t_initial:,}万円）",
                xaxis_title="退職後年数", yaxis_title="資産（万円）",
                template="plotly_dark", height=420,
                paper_bgcolor="#1a2635", plot_bgcolor="#1a2635",
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            max_start = int(MARKET_DF["year"].max()) - t_sim_years
            st.warning(f"{t_start_year}年から{t_sim_years}年分のデータがありません。{max_start}年以前を選択してください。")

# ════════════════════════════════════════════════════════════
# TAB 4: 論文推奨シナリオ
# ════════════════════════════════════════════════════════════
with tab_scenarios:
    if not is_paid:
        show_lock()
    else:
        st.markdown('<div class="section-title">論文 Table 11 — 推奨戦略シナリオ（著者提示）</div>',
                    unsafe_allow_html=True)

        scenarios_disp = [
            dict(label="Scenario A", subtitle="効率重視・フルタイム復帰",
                 wr="6%", port="100/0", model="Complete Cessation",
                 labor_yrs="2.10年", final="×6.4（中央値）",
                 note="4%ルールより早期退職できる可能性。高流動性職種向け推奨。",
                 mc_low="13.97年（要注意）", color=C["complete"], highlight=True, idx=0),
            dict(label="Scenario B", subtitle="部分復帰（パートタイム）",
                 wr="5%", port="100/0", model="Half Reduction",
                 labor_yrs="2.15年（半額収入）", final="×8.4（中央値）",
                 note="フルタイム復帰が難しい場合。パート・非常勤勤務を想定。",
                 mc_low="—", color=C["half"], highlight=False, idx=1),
            dict(label="Scenario C", subtitle="保守型",
                 wr="5%", port="75/25", model="Complete Cessation",
                 labor_yrs="1.03年", final="×4.8（中央値）",
                 note="全額株式は心理的に厳しい方向け。リスク抑制優先。",
                 mc_low="—", color=C["blue"], highlight=False, idx=2),
            dict(label="4%ルール（参考）", subtitle="Trinity Study基準",
                 wr="4%", port="75/25", model="Complete Cessation",
                 labor_yrs="0.10年", final="×6.7（中央値）",
                 note="従来の基準値。退職判断の出発点として。",
                 mc_low="—", color=C["gray"], highlight=False, idx=3),
        ]

        for sc in scenarios_disp:
            border = f"2px solid {sc['color']}" if sc["highlight"] else "1px solid rgba(255,255,255,0.1)"
            with st.container():
                st.markdown(f"""
                <div style="border:{border};border-radius:12px;padding:18px 22px;margin-bottom:10px;
                            background:{'rgba(0,158,115,0.06)' if sc['highlight'] else 'rgba(255,255,255,0.02)'}">
                    <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:10px">
                        <div>
                            <span style="font-size:17px;font-weight:800;color:{sc['color']}">{sc['label']}</span>
                            <span style="font-size:13px;color:#8a9bb0;margin-left:10px">{sc['subtitle']}</span>
                        </div>
                        <span style="background:rgba(255,255,255,0.06);border-radius:20px;padding:3px 12px;
                                     font-size:11px;color:#8a9bb0">{sc['model']}</span>
                    </div>
                    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:10px">
                        {"".join([f'<div style="background:rgba(255,255,255,0.04);border-radius:8px;padding:10px 12px"><div style="font-size:10px;color:#8a9bb0;margin-bottom:4px">{k}</div><div style="font-size:15px;font-weight:700">{v}</div></div>' for k,v in [("取り崩し率",sc["wr"]),("ポートフォリオ",sc["port"]),("平均就労復帰年数",sc["labor_yrs"]),("中央値最終資産",sc["final"])]])}
                    </div>
                    <div style="font-size:12px;color:#c8d6e0">{sc['note']}</div>
                    {f'<div style="font-size:12px;color:{C["red"]};margin-top:6px">⚠️ 低リターンMC: 平均就労復帰 {sc["mc_low"]}</div>' if sc["mc_low"] != "—" else ""}
                </div>
                """, unsafe_allow_html=True)

                btn_col1, btn_col2, _ = st.columns([1, 1, 4])
                if btn_col1.button(f"🛡 セーフティバルブに反映", key=f"apply_hcsv_{sc['idx']}"):
                    st.session_state["hcsv_preset"] = PAPER_SCENARIOS_DEF[sc["idx"]]
                    st.success(f"{sc['label']} をセーフティバルブタブに反映しました。タブを切り替えてください。")
                if btn_col2.button(f"📈 軌跡分析に反映", key=f"apply_traj_{sc['idx']}"):
                    st.session_state["traj_preset"] = PAPER_SCENARIOS_DEF[sc["idx"]]
                    st.success(f"{sc['label']} を軌跡分析タブに反映しました。タブを切り替えてください。")

        st.markdown("---")
        st.markdown("""<div class="warning-box">
        <strong>⚠️ 低リターン環境への注意（論文より）</strong><br>
        Scenario Aのモンテカルロ低リターンシナリオでは、平均就労復帰年数が<strong>13.97年</strong>に増加します。
        「資産が尽きない」ことと「短期間の就労復帰で済む」ことは別の問題です。
        </div>""", unsafe_allow_html=True)
        st.markdown("")
        st.caption("出典：Human Capital as a Contingent Labor-Income Buffer — Financial Services Review（掲載予定）")

# ── フッター ─────────────────────────────────────────────────
st.markdown("---")
st.caption("本ツールは学術論文のシミュレーションを再現したものです。投資助言ではありません。過去のデータは将来の成果を保証しません。  |  Medwealth Lab Tokyo")
st.markdown("""<div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);
    border-radius:10px;padding:14px 18px;font-size:12px;color:#8a9bb0;line-height:1.8;margin-top:4px">
⚠️ <strong style="color:#c8d6e0">免責事項・自己責任のご確認</strong><br>
本シミュレーターは教育・情報提供を目的としており、投資勧誘・個別投資助言ではありません。
表示される数値はあくまでシミュレーション結果であり、将来の資産額や退職時期を保証するものではありません。
実際の投資判断・退職計画・税務・保険に関する意思決定は、ご自身の責任において行ってください。
必要に応じてファイナンシャルプランナー・税理士・医師等の専門家にご相談ください。
本ツールの利用によって生じたいかなる損害についても、運営者は一切の責任を負いません。
</div>""", unsafe_allow_html=True)
st.markdown("")
