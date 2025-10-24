import os
import sqlite3
from datetime import datetime, date
import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px

DB_PATH = os.path.join("data", "signals.db")
BERLIN = "Europe/Berlin"

@st.cache_data(ttl=120)
def load_tables(db_path: str):
    if not os.path.exists(db_path):
        return pd.DataFrame(), pd.DataFrame()
    con = sqlite3.connect(db_path)
    try:
        sig = pd.read_sql_query("SELECT * FROM signals ORDER BY ts", con)
        res = pd.read_sql_query("SELECT * FROM results ORDER BY ts", con)
    finally:
        con.close()

    # Parse timestamps and normalize: Europe/Berlin then drop tz (naive) to avoid compare errors
    for df in (sig, res):
        if "ts" in df.columns:
            ts = pd.to_datetime(df["ts"], errors="coerce", utc=True)
            ts = ts.dt.tz_convert(BERLIN).dt.tz_localize(None)
            df["ts"] = ts

    return sig, res

def equity_curve(results: pd.DataFrame, use_risk_pct: float | None = None):
    if results.empty:
        return pd.DataFrame(columns=["ts","cum_R","cum_pct"])
    df = results.sort_values("ts").reset_index(drop=True).copy()
    if "r_realized" not in df.columns:
        df["r_realized"] = np.where(df["outcome"]=="target", 1.5,
                             np.where(df["outcome"]=="stop",-1.0, 0.0))
    df["cum_R"] = df["r_realized"].cumsum()
    if use_risk_pct is not None:
        df["cum_pct"] = (df["r_realized"] * (use_risk_pct/100.0)).cumsum()*100.0
    else:
        df["cum_pct"] = np.nan
    return df[["ts","cum_R","cum_pct"]]

def kpi_block(results: pd.DataFrame):
    if results.empty:
        c1,c2,c3,c4 = st.columns(4)
        for c in (c1,c2,c3,c4): c.metric("-", "-")
        return
    tot = len(results)
    wins = (results["outcome"]=="target").sum()
    stops= (results["outcome"]=="stop").sum()
    hit = (wins/tot*100.0) if tot else 0.0
    avg_R = results["r_realized"].mean() if "r_realized" in results.columns else np.nan
    by_out = results.groupby("outcome")["r_realized"].mean().reindex(["target","stop"]).fillna(0.0)
    exp_R = by_out.get("target",0.0)*(wins/tot) + by_out.get("stop",0.0)*((tot-wins)/tot) if tot else 0.0
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Trades", f"{tot}")
    c2.metric("Hit rate", f"{hit:.1f} %")
    c3.metric("Avg R", f"{avg_R:.2f}")
    c4.metric("Expected R", f"{exp_R:.2f}")

def main():
    st.set_page_config(page_title="Crypto Predictor Dashboard", layout="wide")
    st.title("📊 Crypto Predictor — Performance Dashboard")

    sig, res = load_tables(DB_PATH)

    left, right = st.columns([3,1])
    with left: st.caption(f"Database: `{DB_PATH}`")
    with right:
        risk_pct = st.number_input("Assumed risk per trade (%)", min_value=0.1, max_value=5.0, value=1.0, step=0.1)

    # Merge minimal fields from signals if needed
    if not res.empty and ("signal" not in res.columns or res["signal"].isna().all()) and not sig.empty:
        res = res.merge(sig[["ts","coin_id","signal"]], on=["ts","coin_id"], how="left")

    st.sidebar.header("Filters")
    if not res.empty:
        coins = sorted(res["coin_id"].dropna().unique().tolist())
        sides = ["LONG","SHORT"]
        coins_sel = st.sidebar.multiselect("Coins", coins, default=coins[:10])
        sides_sel = st.sidebar.multiselect("Side", sides, default=sides)

        # Default dates from data
        d_min = res["ts"].min().date()
        d_max = res["ts"].max().date()
        date_from: date = st.sidebar.date_input("From", value=d_min)
        date_to:   date = st.sidebar.date_input("To",   value=d_max)

        # Build naive datetime bounds in same form as res['ts']
        start = pd.to_datetime(datetime.combine(date_from, datetime.min.time()))
        end   = pd.to_datetime(datetime.combine(date_to,   datetime.max.time()))

        mask = (
            res["coin_id"].isin(coins_sel) &
            res["signal"].isin(sides_sel) &
            res["ts"].between(start, end)
        )
        res_f = res.loc[mask].copy()
    else:
        res_f = res.copy()

    st.subheader("Overview")
    kpi_block(res_f)

    st.subheader("Equity Curve (R units)")
    eq = equity_curve(res_f, use_risk_pct=risk_pct)
    if not eq.empty:
        st.plotly_chart(px.line(eq, x="ts", y="cum_R", title="Cumulative R"), use_container_width=True)
        if eq["cum_pct"].notna().any():
            st.plotly_chart(px.line(eq.dropna(subset=["cum_pct"]), x="ts", y="cum_pct",
                                    title="Estimated Equity Growth (%)"),
                            use_container_width=True)
    else:
        st.info("No evaluated trades in the selected range.")

    st.subheader("Hit Rate by Coin and Side")
    if not res_f.empty:
        tmp = res_f.copy()
        tmp["win"] = (tmp["outcome"]=="target").astype(int)
        agg = tmp.groupby(["coin_id","signal"])["win"].mean().reset_index()
        agg["hit_rate_%"] = (agg["win"]*100.0).round(1)
        st.dataframe(agg.drop(columns=["win"]).sort_values("hit_rate_%", ascending=False),
                     use_container_width=True)
    else:
        st.info("No data to display.")

    st.subheader("Recent Trades")
    if not res_f.empty:
        cols = [c for c in ["ts","coin_id","signal","outcome","r_realized","pnl_pct","bars_to_outcome"] if c in res_f.columns]
        st.dataframe(res_f.sort_values("ts", ascending=False)[cols].head(50), use_container_width=True)
    else:
        st.info("No results yet. Let the evaluator run.")

    st.caption("Timestamps normalized to Europe/Berlin. Use sidebar to filter.")

if __name__ == "__main__":
    main()
