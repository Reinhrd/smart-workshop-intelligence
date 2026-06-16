# ================================================================
# SMART WORKSHOP INTELLIGENCE — ADVANCED DATA SCIENCE PIPELINE
# Author role: Data Scientist
# Use case: Bengkel resmi / dealer mobil — personalized oil service reminder,
#           cross-sell engine, demand forecast, customer segmentation.
# ================================================================

from __future__ import annotations

import argparse
import json
import math
import os
import warnings
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
pd.set_option("display.max_columns", 200)
pd.set_option("display.width", 180)

# Optional advanced libraries. Script tetap jalan walau sebagian library belum terinstall.
try:
    from lifelines import WeibullAFTFitter
    HAS_LIFELINES = True
except Exception:
    HAS_LIFELINES = False

try:
    from mlxtend.preprocessing import TransactionEncoder
    from mlxtend.frequent_patterns import fpgrowth, association_rules
    HAS_MLXTEND = True
except Exception:
    HAS_MLXTEND = False

try:
    from statsmodels.tsa.statespace.sarimax import SARIMAX
    HAS_STATSMODELS = True
except Exception:
    HAS_STATSMODELS = False

from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_percentage_error, r2_score, silhouette_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.cluster import KMeans

import matplotlib.pyplot as plt


# ----------------------------------------------------------------
# 0. CONFIG
# ----------------------------------------------------------------
@dataclass
class Config:
    input_dir: Path
    output_dir: Path
    current_date: pd.Timestamp | None = None
    oil_item_name: str = "Ganti Oli Mesin"
    min_support: float = 0.03
    min_lift: float = 1.05
    forecast_horizon_weeks: int = 8
    random_state: int = 42


def parse_args() -> Config:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input_dir", type=str, default="/content")
    parser.add_argument("--output_dir", type=str, default="/content/smart_workshop_outputs")
    parser.add_argument("--current_date", type=str, default=None,
                        help="YYYY-MM-DD. Kalau kosong, dipakai max(tanggal)+1 hari.")
    args = parser.parse_args()
    current = pd.to_datetime(args.current_date) if args.current_date else None
    return Config(Path(args.input_dir), Path(args.output_dir), current_date=current)


def make_dirs(cfg: Config) -> None:
    cfg.output_dir.mkdir(parents=True, exist_ok=True)
    (cfg.output_dir / "plots").mkdir(parents=True, exist_ok=True)


# ----------------------------------------------------------------
# 1. LOAD DATA + BASIC CLEANING
# ----------------------------------------------------------------
def load_data(cfg: Config) -> Tuple[pd.DataFrame, pd.DataFrame, Optional[pd.DataFrame]]:
    master_path = cfg.input_dir / "pelanggan_mobil.csv"
    svc_path = cfg.input_dir / "riwayat_servis.csv"
    cust_path = cfg.input_dir / "pelanggan.csv"

    if not master_path.exists():
        raise FileNotFoundError(f"File tidak ditemukan: {master_path}")
    if not svc_path.exists():
        raise FileNotFoundError(f"File tidak ditemukan: {svc_path}")

    # no_telepon wajib string supaya leading zero tidak hilang.
    master = pd.read_csv(master_path, dtype={"customer_id": str, "car_id": str, "no_telepon": str, "kode_pos": str})
    svc = pd.read_csv(svc_path, dtype={"service_id": str, "visit_id": str, "car_id": str})
    cust = None
    if cust_path.exists():
        cust = pd.read_csv(cust_path, dtype={"customer_id": str, "no_telepon": str, "kode_pos": str})

    svc["tanggal"] = pd.to_datetime(svc["tanggal"], errors="coerce")
    svc["harga"] = pd.to_numeric(svc["harga"], errors="coerce")
    svc["qty"] = pd.to_numeric(svc["qty"], errors="coerce").fillna(1).astype(int)
    svc["km_saat_servis"] = pd.to_numeric(svc["km_saat_servis"], errors="coerce")

    master["tahun"] = pd.to_numeric(master["tahun"], errors="coerce")
    master["interval_oli_km"] = pd.to_numeric(master["interval_oli_km"], errors="coerce")
    master["km_per_bulan"] = pd.to_numeric(master["km_per_bulan"], errors="coerce")

    if cfg.current_date is None:
        cfg.current_date = svc["tanggal"].max() + pd.Timedelta(days=1)

    return master, svc, cust


# ----------------------------------------------------------------
# 2. DATA QUALITY AUDIT
# ----------------------------------------------------------------
def data_quality_audit(master: pd.DataFrame, svc: pd.DataFrame) -> pd.DataFrame:
    fk_missing = sorted(set(svc["car_id"].dropna()) - set(master["car_id"].dropna()))
    duplicate_service_id = int(svc["service_id"].duplicated().sum())
    duplicate_car_id = int(master["car_id"].duplicated().sum())

    checks = [
        ("master_rows", len(master), "Jumlah baris master kendaraan"),
        ("service_rows", len(svc), "Jumlah baris item servis"),
        ("unique_customers", master["customer_id"].nunique(), "Pelanggan unik di master"),
        ("unique_cars", master["car_id"].nunique(), "Mobil unik di master"),
        ("unique_visits", svc["visit_id"].nunique(), "Kunjungan unik di riwayat servis"),
        ("date_missing", int(svc["tanggal"].isna().sum()), "Tanggal gagal parse"),
        ("price_missing", int(svc["harga"].isna().sum()), "Harga kosong/gagal parse"),
        ("negative_price", int((svc["harga"] < 0).sum()), "Harga negatif"),
        ("duplicate_service_id", duplicate_service_id, "Duplikasi service_id"),
        ("duplicate_car_id", duplicate_car_id, "Duplikasi car_id di master"),
        ("fk_missing_car_id", len(fk_missing), "car_id di transaksi tidak ada di master"),
        ("phone_leading_zero_ok", int(master["no_telepon"].fillna("").str.startswith("0").mean() * 100), "% no_telepon diawali 0"),
        ("min_service_date", svc["tanggal"].min(), "Tanggal awal transaksi"),
        ("max_service_date", svc["tanggal"].max(), "Tanggal akhir transaksi"),
    ]
    return pd.DataFrame(checks, columns=["check", "value", "description"])


# ----------------------------------------------------------------
# 3. FEATURE ENGINEERING
# ----------------------------------------------------------------
def build_visit_table(master: pd.DataFrame, svc: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    item_set = svc.groupby("visit_id")["item_servis"].apply(lambda x: sorted(set(x))).rename("items")
    visit_base = svc.groupby("visit_id").agg(
        car_id=("car_id", "first"),
        tanggal=("tanggal", "min"),
        km_saat_servis=("km_saat_servis", "max"),
        cabang=("cabang", "first"),
        mekanik=("mekanik", "first"),
        visit_revenue=("harga", "sum"),
        n_items=("item_servis", "nunique"),
    ).reset_index()
    visit_base = visit_base.merge(item_set.reset_index(), on="visit_id", how="left")
    visit_base["has_oil"] = visit_base["items"].apply(lambda xs: cfg.oil_item_name in xs)
    visit_base = visit_base.merge(master, on="car_id", how="left")
    visit_base["year_month"] = visit_base["tanggal"].dt.to_period("M").astype(str)
    visit_base["week"] = visit_base["tanggal"].dt.to_period("W-MON").apply(lambda p: p.start_time)
    return visit_base


def build_oil_episodes(master: pd.DataFrame, svc: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    oil = svc[svc["item_servis"].eq(cfg.oil_item_name)].copy()
    oil = oil[["visit_id", "car_id", "tanggal", "km_saat_servis", "harga"]].drop_duplicates("visit_id")
    oil = oil.merge(master, on="car_id", how="left")
    oil = oil.sort_values(["car_id", "tanggal", "km_saat_servis"])
    oil["prev_tanggal"] = oil.groupby("car_id")["tanggal"].shift(1)
    oil["prev_km"] = oil.groupby("car_id")["km_saat_servis"].shift(1)
    oil["gap_days"] = (oil["tanggal"] - oil["prev_tanggal"]).dt.days
    oil["gap_km"] = oil["km_saat_servis"] - oil["prev_km"]
    oil["event"] = 1

    # Episode valid: gap positif dan tidak ekstrem.
    ep = oil[(oil["gap_days"] > 0) & (oil["gap_days"] <= 500) & (oil["gap_km"] > 0)].copy()
    ep["car_age_at_service"] = ep["tanggal"].dt.year - ep["tahun"]
    ep["log_gap_days"] = np.log(ep["gap_days"])
    ep["utilization_ratio_km"] = ep["gap_km"] / ep["interval_oli_km"]
    return ep


# ----------------------------------------------------------------
# 4. KPI + REVENUE ANALYTICS
# ----------------------------------------------------------------
def compute_kpis(master: pd.DataFrame, svc: pd.DataFrame, visits: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    total_revenue = svc["harga"].sum()
    oil_revenue = svc.loc[svc["item_servis"].eq(cfg.oil_item_name), "harga"].sum()
    non_oil_revenue = total_revenue - oil_revenue
    kpis = {
        "customers": master["customer_id"].nunique(),
        "cars": master["car_id"].nunique(),
        "visits": visits["visit_id"].nunique(),
        "service_item_rows": len(svc),
        "date_min": svc["tanggal"].min().date(),
        "date_max": svc["tanggal"].max().date(),
        "total_revenue": total_revenue,
        "oil_revenue": oil_revenue,
        "non_oil_cross_sell_revenue": non_oil_revenue,
        "cross_sell_share": non_oil_revenue / total_revenue,
        "avg_order_value_per_visit": total_revenue / visits["visit_id"].nunique(),
        "oil_visits": int(visits["has_oil"].sum()),
    }
    return pd.DataFrame([kpis])


def revenue_tables(svc: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    rev_cat = svc.groupby("kategori_servis").agg(
        revenue=("harga", "sum"),
        rows=("service_id", "count"),
        visits=("visit_id", "nunique"),
    ).reset_index().sort_values("revenue", ascending=False)
    rev_cat["revenue_share"] = rev_cat["revenue"] / rev_cat["revenue"].sum()

    rev_item = svc.groupby("item_servis").agg(
        revenue=("harga", "sum"),
        rows=("service_id", "count"),
        visits=("visit_id", "nunique"),
        avg_price=("harga", "mean"),
    ).reset_index().sort_values("revenue", ascending=False)
    rev_item["revenue_share"] = rev_item["revenue"] / rev_item["revenue"].sum()
    return rev_cat, rev_item


# ----------------------------------------------------------------
# 5. SURVIVAL / INTERVAL MODELING
# ----------------------------------------------------------------
def fit_interval_model(episodes: pd.DataFrame, cfg: Config) -> Tuple[pd.DataFrame, pd.DataFrame, object, Dict]:
    model_cols_num = ["km_per_bulan", "interval_oli_km", "car_age_at_service", "gap_km"]
    model_cols_cat = ["bahan_bakar", "penggerak", "jenis_oli", "segmen_pemakaian_asli"]

    train = episodes.dropna(subset=["gap_days"] + model_cols_num + model_cols_cat).copy()
    summary = {"n_episodes": len(train), "method": None, "r2_log_duration": None}

    if HAS_LIFELINES and len(train) > 50:
        aft_cols = ["gap_days", "event"] + model_cols_num + model_cols_cat
        aft_df = train[aft_cols].copy()
        # lifelines support formula; categorical covariates via C(...)
        formula = "km_per_bulan + interval_oli_km + car_age_at_service + gap_km + C(bahan_bakar) + C(penggerak) + C(jenis_oli) + C(segmen_pemakaian_asli)"
        aft = WeibullAFTFitter(penalizer=0.01)
        aft.fit(aft_df, duration_col="gap_days", event_col="event", formula=formula)
        pred_median = aft.predict_median(aft_df).astype(float).values
        train["pred_gap_days"] = np.clip(pred_median, 10, 500)
        summary.update({"method": "Weibull AFT lifelines", "r2_log_duration": r2_score(np.log(train["gap_days"]), np.log(train["pred_gap_days"]))})
        coef = aft.summary.reset_index()
        return train, coef, aft, summary

    # Fallback machine learning model jika lifelines belum terinstall.
    pre = ColumnTransformer([
        ("num", Pipeline([("imputer", SimpleImputer(strategy="median")), ("scaler", StandardScaler())]), model_cols_num),
        ("cat", Pipeline([("imputer", SimpleImputer(strategy="most_frequent")), ("onehot", OneHotEncoder(handle_unknown="ignore"))]), model_cols_cat),
    ])
    gbr = GradientBoostingRegressor(random_state=cfg.random_state, n_estimators=250, learning_rate=0.04, max_depth=3)
    pipe = Pipeline([("preprocess", pre), ("model", gbr)])
    X = train[model_cols_num + model_cols_cat]
    y = np.log(train["gap_days"])
    pipe.fit(X, y)
    train["pred_gap_days"] = np.exp(pipe.predict(X))
    summary.update({"method": "GradientBoosting log-duration fallback", "r2_log_duration": r2_score(y, np.log(train["pred_gap_days"]))})

    # pseudo coefficient table dari feature importance
    feature_names = []
    try:
        ohe = pipe.named_steps["preprocess"].named_transformers_["cat"].named_steps["onehot"]
        feature_names = model_cols_num + list(ohe.get_feature_names_out(model_cols_cat))
    except Exception:
        feature_names = [f"feature_{i}" for i in range(len(pipe.named_steps["model"].feature_importances_))]
    coef = pd.DataFrame({"feature": feature_names, "importance": pipe.named_steps["model"].feature_importances_}).sort_values("importance", ascending=False)
    return train, coef, pipe, summary


def oil_interval_by_segment(episodes_scored: pd.DataFrame) -> pd.DataFrame:
    return episodes_scored.groupby("segmen_pemakaian_asli").agg(
        n_episodes=("gap_days", "count"),
        avg_gap_days=("gap_days", "mean"),
        median_gap_days=("gap_days", "median"),
        avg_gap_km=("gap_km", "mean"),
        avg_pred_gap_days=("pred_gap_days", "mean"),
        avg_utilization_ratio_km=("utilization_ratio_km", "mean"),
    ).reset_index().sort_values("avg_gap_days")


def score_due_alerts(master: pd.DataFrame, svc: pd.DataFrame, interval_model, episodes_scored: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    oil = svc[svc["item_servis"].eq(cfg.oil_item_name)].copy()
    last_oil = oil.sort_values("tanggal").groupby("car_id").tail(1)[["car_id", "tanggal", "km_saat_servis", "visit_id"]]
    last_oil = last_oil.rename(columns={"tanggal": "last_oil_date", "km_saat_servis": "last_oil_km", "visit_id": "last_oil_visit_id"})
    base = master.merge(last_oil, on="car_id", how="left")
    base["days_since_last_oil"] = (cfg.current_date - base["last_oil_date"]).dt.days
    base["estimated_km_since_last_oil"] = base["days_since_last_oil"] * base["km_per_bulan"] / 30.0

    # Prediksi median interval. Untuk data master tanpa episode, pakai model fallback berbasis rata-rata segmen.
    seg_pred = episodes_scored.groupby("segmen_pemakaian_asli")["pred_gap_days"].median().to_dict()
    base["predicted_interval_days"] = base["segmen_pemakaian_asli"].map(seg_pred)
    base["predicted_interval_days"] = base["predicted_interval_days"].fillna(episodes_scored["pred_gap_days"].median())

    # Business scoring: gabungan progress waktu, progress km, dan estimasi probabilitas due 14 hari.
    base["progress_day_model"] = base["days_since_last_oil"] / base["predicted_interval_days"]
    base["progress_km_rule"] = base["estimated_km_since_last_oil"] / base["interval_oli_km"]
    # Smooth probability proxy: naik tajam ketika progress > 0.85
    combined_progress = 0.55 * base["progress_day_model"] + 0.45 * base["progress_km_rule"]
    base["prob_due_14d_conditional"] = 1 / (1 + np.exp(-10 * (combined_progress - 0.90)))
    base["priority_score"] = (100 * (0.45 * base["prob_due_14d_conditional"] + 0.35 * combined_progress + 0.20 * base["progress_km_rule"])).clip(0, 100)

    conditions = [
        base["priority_score"] >= 85,
        base["priority_score"] >= 70,
        base["priority_score"] >= 55,
    ]
    choices = ["Critical", "High Priority", "Warm Reminder"]
    base["alert_tier"] = np.select(conditions, choices, default="Monitor")

    def build_wa(row):
        sapaan = "Bapak/Ibu"
        nama = str(row.get("nama_pemilik", "Pelanggan Toyota")).split()[0]
        progress_pct = max(row.get("progress_day_model", 0), row.get("progress_km_rule", 0)) * 100
        return (
            f"Halo {sapaan} {nama}, kami dari Bengkel Toyota Medan. "
            f"Kendaraan {row.get('model')} {row.get('nopol')} terpantau sudah mencapai sekitar {progress_pct:.0f}% "
            f"dari batas ideal pergantian oli. Untuk menjaga performa mesin, kami sarankan jadwalkan servis dalam waktu dekat. "
            f"Balas pesan ini untuk booking slot servis."
        )

    base["wa_message"] = base.apply(build_wa, axis=1)
    cols = [
        "customer_id", "nama_pemilik", "no_telepon", "car_id", "nopol", "model", "varian",
        "bahan_bakar", "penggerak", "jenis_oli", "interval_oli_km", "segmen_pemakaian_asli",
        "last_oil_date", "last_oil_km", "days_since_last_oil", "estimated_km_since_last_oil",
        "predicted_interval_days", "progress_day_model", "progress_km_rule", "prob_due_14d_conditional",
        "priority_score", "alert_tier", "wa_message"
    ]
    return base[cols].sort_values(["priority_score", "progress_km_rule"], ascending=False)


# ----------------------------------------------------------------
# 6. MARKET BASKET ANALYSIS
# ----------------------------------------------------------------
def run_market_basket(svc: pd.DataFrame, cfg: Config) -> Tuple[pd.DataFrame, pd.DataFrame]:
    transactions = svc.groupby("visit_id")["item_servis"].apply(lambda x: sorted(set(x))).tolist()
    item_avg_price = svc.groupby("item_servis")["harga"].mean().to_dict()
    item_total_rev = svc.groupby("item_servis")["harga"].sum().to_dict()
    n_tx = len(transactions)

    if HAS_MLXTEND:
        te = TransactionEncoder()
        mat = te.fit(transactions).transform(transactions)
        basket = pd.DataFrame(mat, columns=te.columns_)
        freq = fpgrowth(basket, min_support=cfg.min_support, use_colnames=True)
        rules = association_rules(freq, metric="lift", min_threshold=cfg.min_lift)
        rules = rules.copy()
        rules["antecedents_txt"] = rules["antecedents"].apply(lambda s: " + ".join(sorted(list(s))))
        rules["consequents_txt"] = rules["consequents"].apply(lambda s: " + ".join(sorted(list(s))))
        rules["support_count"] = (rules["support"] * n_tx).round().astype(int)
        rules["consequent_avg_price"] = rules["consequents"].apply(lambda s: np.mean([item_avg_price.get(i, 0) for i in s]))
        rules["estimated_rule_revenue"] = rules["support_count"] * rules["confidence"] * rules["consequent_avg_price"]
        rules = rules.sort_values(["estimated_rule_revenue", "lift", "confidence"], ascending=False)
        keep = ["antecedents_txt", "consequents_txt", "support", "support_count", "confidence", "lift", "leverage", "conviction", "consequent_avg_price", "estimated_rule_revenue"]
        rules_out = rules[keep].reset_index(drop=True)
    else:
        # Fallback sederhana: pairwise confidence/lift manual.
        tx_sets = [set(t) for t in transactions]
        all_items = sorted(set().union(*tx_sets))
        rows = []
        for a in all_items:
            tx_a = [t for t in tx_sets if a in t]
            if len(tx_a) / n_tx < cfg.min_support:
                continue
            for b in all_items:
                if a == b:
                    continue
                support_ab = sum((a in t and b in t) for t in tx_sets) / n_tx
                support_a = len(tx_a) / n_tx
                support_b = sum(b in t for t in tx_sets) / n_tx
                if support_ab >= cfg.min_support and support_b > 0:
                    conf = support_ab / support_a
                    lift = conf / support_b
                    if lift >= cfg.min_lift:
                        rows.append({
                            "antecedents_txt": a, "consequents_txt": b,
                            "support": support_ab, "support_count": round(support_ab * n_tx),
                            "confidence": conf, "lift": lift,
                            "leverage": support_ab - support_a * support_b,
                            "conviction": np.nan,
                            "consequent_avg_price": item_avg_price.get(b, 0),
                            "estimated_rule_revenue": round(support_ab * n_tx) * conf * item_avg_price.get(b, 0),
                        })
        rules_out = pd.DataFrame(rows).sort_values(["estimated_rule_revenue", "lift", "confidence"], ascending=False)

    oil_visits = set(svc.loc[svc["item_servis"].eq(cfg.oil_item_name), "visit_id"])
    sub = svc[svc["visit_id"].isin(oil_visits)]
    attach = []
    for item, g in sub.groupby("item_servis"):
        if item == cfg.oil_item_name:
            continue
        attach.append({
            "item_servis": item,
            "attach_rate_given_oil": g["visit_id"].nunique() / len(oil_visits),
            "visits_with_item_and_oil": g["visit_id"].nunique(),
            "revenue_in_oil_visits": g["harga"].sum(),
            "avg_price": g["harga"].mean(),
        })
    attach_df = pd.DataFrame(attach).sort_values(["revenue_in_oil_visits", "attach_rate_given_oil"], ascending=False)
    return rules_out, attach_df


# ----------------------------------------------------------------
# 7. DEMAND FORECASTING
# ----------------------------------------------------------------
def add_calendar_features(index: pd.DatetimeIndex) -> pd.DataFrame:
    # Tanggal Lebaran 2022-2026 approximate, untuk demo seasonal feature.
    lebaran = pd.to_datetime(["2022-05-02", "2023-04-22", "2024-04-10", "2025-03-31", "2026-03-20", "2027-03-10"])
    df = pd.DataFrame(index=index)
    df["week_of_year"] = index.isocalendar().week.astype(int).values
    df["month"] = index.month
    df["is_year_end"] = index.month.isin([11, 12]).astype(int)

    # Week contains payday window proxy: minggu setelah tgl 25 / awal bulan.
    df["payday_week"] = [1 if (d.day <= 7 or d.day >= 25) else 0 for d in index]

    pre_lebaran = []
    lebaran_week = []
    for d in index:
        days_to = np.min([(ld - d).days for ld in lebaran])
        pre_lebaran.append(1 if 0 < days_to <= 28 else 0)
        lebaran_week.append(1 if -3 <= days_to <= 7 else 0)
    df["pre_lebaran_4w"] = pre_lebaran
    df["lebaran_week"] = lebaran_week
    return df


def make_lag_frame(weekly: pd.DataFrame) -> pd.DataFrame:
    df = weekly.copy()
    for lag in [1, 2, 3, 4, 8, 12]:
        df[f"lag_{lag}"] = df["visits"].shift(lag)
    df["roll4_mean"] = df["visits"].shift(1).rolling(4).mean()
    df["roll8_mean"] = df["visits"].shift(1).rolling(8).mean()
    df["y"] = df["visits"]
    return df


def run_demand_forecast(visits: pd.DataFrame, svc: pd.DataFrame, cfg: Config) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Fast, production-friendly forecasting.

    Kenapa bukan SARIMAX default? Untuk demo/Colab 3-4 hari, tree-based model dengan lag + calendar exog
    jauh lebih stabil dan cepat. SARIMAX tetap bisa dipakai sebagai challenger model, tetapi pipeline ini
    mengutamakan reproducibility dan runtime cepat.
    """
    weekly = visits.groupby(pd.Grouper(key="tanggal", freq="W-MON")).agg(
        visits=("visit_id", "nunique"),
        oil_visits=("has_oil", "sum"),
        revenue=("visit_revenue", "sum"),
    ).reset_index().rename(columns={"tanggal": "week_start"})
    weekly = weekly.sort_values("week_start")
    weekly = weekly.set_index("week_start").asfreq("W-MON").fillna(0)

    exog = add_calendar_features(weekly.index)
    lag_df = make_lag_frame(weekly).join(exog).dropna()
    feature_cols = [c for c in lag_df.columns if c not in ["y", "visits", "oil_visits", "revenue"]]

    # Backtest last 12 weeks
    test_size = min(12, max(4, len(lag_df) // 6))
    train = lag_df.iloc[:-test_size]
    test = lag_df.iloc[-test_size:]

    model = GradientBoostingRegressor(
        random_state=cfg.random_state,
        n_estimators=250,
        learning_rate=0.04,
        max_depth=3,
        loss="squared_error",
    )
    model.fit(train[feature_cols], train["y"])
    pred_test = pd.Series(model.predict(test[feature_cols]), index=test.index).clip(lower=0)
    naive_test = pd.Series(train["y"].rolling(4).mean().iloc[-1], index=test.index)

    mape_model = mean_absolute_percentage_error(test["y"].replace(0, np.nan).dropna(), pred_test.loc[test["y"].replace(0, np.nan).dropna().index])
    mape_naive = mean_absolute_percentage_error(test["y"].replace(0, np.nan).dropna(), naive_test.loc[test["y"].replace(0, np.nan).dropna().index])

    backtest = pd.DataFrame({
        "week_start": test.index,
        "actual_visits": test["y"].values,
        "pred_visits_model": np.round(pred_test.values).astype(int),
        "pred_visits_naive": np.round(naive_test.values).astype(int),
        "method": "GradientBoosting + lag features + calendar exog",
        "mape_model": mape_model,
        "mape_naive": mape_naive,
    })

    # Refit full and forecast recursively
    full = lag_df.copy()
    model.fit(full[feature_cols], full["y"])
    future_rows = []
    history = weekly["visits"].copy()
    future_idx = pd.date_range(weekly.index.max() + pd.Timedelta(days=7), periods=cfg.forecast_horizon_weeks, freq="W-MON")

    for d in future_idx:
        row = {}
        for lag in [1, 2, 3, 4, 8, 12]:
            row[f"lag_{lag}"] = history.iloc[-lag] if len(history) >= lag else history.mean()
        row["roll4_mean"] = history.iloc[-4:].mean()
        row["roll8_mean"] = history.iloc[-8:].mean()
        cal = add_calendar_features(pd.DatetimeIndex([d])).iloc[0].to_dict()
        row.update(cal)
        x = pd.DataFrame([row], index=[d])[feature_cols]
        pred = max(0, float(model.predict(x)[0]))
        history.loc[d] = pred
        future_rows.append({"week_start": d, "forecast_visits": int(round(pred))})

    forecast = pd.DataFrame(future_rows)
    aov = weekly["revenue"].sum() / max(weekly["visits"].sum(), 1)
    oil_rate = weekly["oil_visits"].sum() / max(weekly["visits"].sum(), 1)
    forecast["forecast_oil_visits"] = np.round(forecast["forecast_visits"] * oil_rate).astype(int)
    forecast["forecast_revenue"] = np.round(forecast["forecast_visits"] * aov).astype(int)
    forecast["method"] = "GradientBoosting + lag features + calendar exog"
    return forecast, backtest

# ----------------------------------------------------------------
# 8. CLUSTERING + CUSTOMER VALUE/RISK
# ----------------------------------------------------------------
def run_clustering(master: pd.DataFrame, visits: pd.DataFrame, episodes: pd.DataFrame, cfg: Config) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    car_agg = visits.groupby("car_id").agg(
        visits=("visit_id", "nunique"),
        oil_visits=("has_oil", "sum"),
        revenue=("visit_revenue", "sum"),
        avg_items=("n_items", "mean"),
        first_visit=("tanggal", "min"),
        last_visit=("tanggal", "max"),
    ).reset_index()
    car_agg["active_days"] = (car_agg["last_visit"] - car_agg["first_visit"]).dt.days.clip(lower=30)
    car_agg["visits_per_year"] = car_agg["visits"] / car_agg["active_days"] * 365
    car_agg["revenue_per_year"] = car_agg["revenue"] / car_agg["active_days"] * 365

    ep_agg = episodes.groupby("car_id").agg(avg_gap_days=("gap_days", "mean"), avg_gap_km=("gap_km", "mean")).reset_index()
    feat = master.merge(car_agg, on="car_id", how="left").merge(ep_agg, on="car_id", how="left")
    for c in ["visits", "oil_visits", "revenue", "avg_items", "visits_per_year", "revenue_per_year", "avg_gap_days", "avg_gap_km"]:
        feat[c] = feat[c].fillna(0)

    x_cols = ["km_per_bulan", "interval_oli_km", "tahun", "visits_per_year", "revenue_per_year", "avg_items", "avg_gap_days"]
    X = feat[x_cols].replace([np.inf, -np.inf], np.nan).fillna(0)
    Xs = StandardScaler().fit_transform(X)

    best_k, best_score = 3, -1
    for k in [3, 4, 5]:
        labels = KMeans(n_clusters=k, random_state=cfg.random_state, n_init=20).fit_predict(Xs)
        score = silhouette_score(Xs, labels)
        if score > best_score:
            best_k, best_score = k, score

    km = KMeans(n_clusters=best_k, random_state=cfg.random_state, n_init=30)
    feat["cluster"] = km.fit_predict(Xs)

    profile = feat.groupby("cluster").agg(
        cars=("car_id", "nunique"),
        avg_km_per_month=("km_per_bulan", "mean"),
        avg_visits_per_year=("visits_per_year", "mean"),
        avg_revenue_per_year=("revenue_per_year", "mean"),
        avg_gap_days=("avg_gap_days", "mean"),
        oil_visit_rate=("oil_visits", "mean"),
    ).reset_index().sort_values("avg_revenue_per_year", ascending=False)
    profile["silhouette_score_global"] = best_score

    if "segmen_pemakaian_asli" in feat.columns:
        confusion = pd.crosstab(feat["cluster"], feat["segmen_pemakaian_asli"], normalize="index").reset_index()
    else:
        confusion = pd.DataFrame()
    return feat, profile, confusion


def customer_value_risk(master: pd.DataFrame, visits: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    cust = visits.groupby("customer_id").agg(
        customer_name=("nama_pemilik", "first"),
        phone=("no_telepon", "first"),
        cars=("car_id", "nunique"),
        visits=("visit_id", "nunique"),
        revenue=("visit_revenue", "sum"),
        first_visit=("tanggal", "min"),
        last_visit=("tanggal", "max"),
        oil_visits=("has_oil", "sum"),
    ).reset_index()
    cust["days_since_last_visit"] = (cfg.current_date - cust["last_visit"]).dt.days
    cust["tenure_days"] = (cust["last_visit"] - cust["first_visit"]).dt.days.clip(lower=30)
    cust["annualized_revenue"] = cust["revenue"] / cust["tenure_days"] * 365
    cust["recency_risk"] = (cust["days_since_last_visit"] / 240).clip(0, 1)
    cust["value_score"] = 100 * cust["annualized_revenue"].rank(pct=True)
    cust["risk_score"] = 100 * cust["recency_risk"]
    cust["priority_reactivation_score"] = 0.6 * cust["value_score"] + 0.4 * cust["risk_score"]
    return cust.sort_values("priority_reactivation_score", ascending=False)


# ----------------------------------------------------------------
# 9. UPLIFT SCENARIO
# ----------------------------------------------------------------
def build_uplift_scenarios(kpi: pd.DataFrame, alerts: pd.DataFrame) -> pd.DataFrame:
    aov = float(kpi.loc[0, "avg_order_value_per_visit"])
    targetable = int((alerts["alert_tier"].isin(["Warm Reminder", "High Priority", "Critical"])).sum())
    scenarios = []
    for name, conv, cross_sell_uplift in [
        ("Conservative", 0.08, 0.03),
        ("Base Case", 0.14, 0.06),
        ("Aggressive", 0.22, 0.10),
    ]:
        incremental_visits = targetable * conv
        incremental_service_rev = incremental_visits * aov
        incremental_cross_sell_rev = incremental_service_rev * cross_sell_uplift
        scenarios.append({
            "scenario": name,
            "targetable_cars": targetable,
            "assumed_conversion_rate": conv,
            "incremental_visits": incremental_visits,
            "incremental_service_revenue": incremental_service_rev,
            "assumed_cross_sell_uplift": cross_sell_uplift,
            "incremental_cross_sell_revenue": incremental_cross_sell_rev,
            "total_incremental_revenue": incremental_service_rev + incremental_cross_sell_rev,
        })
    return pd.DataFrame(scenarios)


# ----------------------------------------------------------------
# 10. PLOTS
# ----------------------------------------------------------------
def save_plots(out: Path, rev_cat: pd.DataFrame, interval_seg: pd.DataFrame, rules: pd.DataFrame,
               forecast: pd.DataFrame, cluster_profile: pd.DataFrame, alerts: pd.DataFrame) -> None:
    plot_dir = out / "plots"

    plt.figure(figsize=(9, 5))
    rev_cat.sort_values("revenue").plot(kind="barh", x="kategori_servis", y="revenue", legend=False)
    plt.title("Revenue by Service Category")
    plt.xlabel("Revenue (Rp)")
    plt.ylabel("")
    plt.tight_layout()
    plt.savefig(plot_dir / "plot_revenue_by_category.png", dpi=160)
    plt.close()

    plt.figure(figsize=(9, 5))
    interval_seg.sort_values("avg_gap_days").plot(kind="bar", x="segmen_pemakaian_asli", y="avg_gap_days", legend=False)
    plt.title("Average Oil Change Interval by Usage Segment")
    plt.xlabel("Segment")
    plt.ylabel("Average gap days")
    plt.tight_layout()
    plt.savefig(plot_dir / "plot_oil_interval_by_segment.png", dpi=160)
    plt.close()

    if not rules.empty:
        top_rules = rules.head(10).copy()
        top_rules["rule"] = top_rules["antecedents_txt"] + " → " + top_rules["consequents_txt"]
        plt.figure(figsize=(10, 6))
        top_rules.sort_values("estimated_rule_revenue").plot(kind="barh", x="rule", y="estimated_rule_revenue", legend=False)
        plt.title("Top Market Basket Rules by Estimated Revenue")
        plt.xlabel("Estimated rule revenue (Rp)")
        plt.ylabel("")
        plt.tight_layout()
        plt.savefig(plot_dir / "plot_top_basket_rules.png", dpi=160)
        plt.close()

    plt.figure(figsize=(9, 5))
    plt.plot(forecast["week_start"], forecast["forecast_visits"], marker="o")
    plt.title("8-Week Workshop Visit Forecast")
    plt.xlabel("Week")
    plt.ylabel("Forecast visits")
    plt.xticks(rotation=30)
    plt.tight_layout()
    plt.savefig(plot_dir / "plot_weekly_forecast.png", dpi=160)
    plt.close()

    plt.figure(figsize=(9, 5))
    cluster_profile.sort_values("avg_revenue_per_year").plot(kind="barh", x="cluster", y="avg_revenue_per_year", legend=False)
    plt.title("Cluster Profile: Annualized Revenue")
    plt.xlabel("Average annualized revenue (Rp)")
    plt.ylabel("Cluster")
    plt.tight_layout()
    plt.savefig(plot_dir / "plot_cluster_profile.png", dpi=160)
    plt.close()

    plt.figure(figsize=(7, 5))
    alerts["alert_tier"].value_counts().reindex(["Critical", "High Priority", "Warm Reminder", "Monitor"]).fillna(0).plot(kind="bar")
    plt.title("WA Alert Tier Distribution")
    plt.xlabel("Tier")
    plt.ylabel("Cars")
    plt.tight_layout()
    plt.savefig(plot_dir / "plot_alert_tiers.png", dpi=160)
    plt.close()


# ----------------------------------------------------------------
# 11. EXPORT EXCEL + REPORT
# ----------------------------------------------------------------
def write_excel(output_xlsx: Path, tables: Dict[str, pd.DataFrame]) -> None:
    with pd.ExcelWriter(output_xlsx, engine="xlsxwriter", datetime_format="yyyy-mm-dd", date_format="yyyy-mm-dd") as writer:
        workbook = writer.book
        fmt_title = workbook.add_format({"bold": True, "font_size": 16})
        fmt_header = workbook.add_format({"bold": True, "bg_color": "#D9EAF7", "border": 1})
        fmt_money = workbook.add_format({"num_format": "Rp #,##0"})
        fmt_pct = workbook.add_format({"num_format": "0.0%"})
        fmt_int = workbook.add_format({"num_format": "#,##0"})
        fmt_float = workbook.add_format({"num_format": "#,##0.00"})

        for sheet, df in tables.items():
            safe_sheet = sheet[:31]
            df.to_excel(writer, sheet_name=safe_sheet, index=False, startrow=1)
            ws = writer.sheets[safe_sheet]
            ws.write(0, 0, sheet, fmt_title)
            ws.freeze_panes(2, 0)
            for col_num, value in enumerate(df.columns.values):
                ws.write(1, col_num, value, fmt_header)
                width = max(12, min(40, int(max(df[value].astype(str).str.len().quantile(0.9) if len(df) else 12, len(str(value))) + 2)))
                ws.set_column(col_num, col_num, width)
                lname = value.lower()
                if any(k in lname for k in ["revenue", "harga", "price"]):
                    ws.set_column(col_num, col_num, max(width, 16), fmt_money)
                elif any(k in lname for k in ["share", "rate", "mape", "confidence", "lift", "support", "ratio", "prob", "progress"]):
                    ws.set_column(col_num, col_num, max(width, 12), fmt_pct if "lift" not in lname else fmt_float)
                elif any(k in lname for k in ["count", "visits", "cars", "rows"]):
                    ws.set_column(col_num, col_num, max(width, 12), fmt_int)


def write_markdown_report(path: Path, model_summary: Dict, kpi: pd.DataFrame, interval_seg: pd.DataFrame,
                          rules: pd.DataFrame, forecast: pd.DataFrame, uplift: pd.DataFrame) -> None:
    row = kpi.iloc[0]
    best_rule = rules.iloc[0].to_dict() if not rules.empty else {}
    text = f"""# Smart Workshop Intelligence — Executive Data Science Report

## 1. Business Framing
Sistem ini bukan sekadar alarm ganti oli. Pipeline ini mengubah data servis menjadi intelligence layer untuk:
1. personalized oil service interval,
2. WA reminder prioritization,
3. cross-sell recommendation,
4. demand forecasting,
5. customer value-risk scoring.

## 2. KPI Utama
- Pelanggan unik: **{int(row['customers']):,}**
- Mobil unik: **{int(row['cars']):,}**
- Kunjungan servis: **{int(row['visits']):,}**
- Baris item servis: **{int(row['service_item_rows']):,}**
- Total revenue: **Rp {row['total_revenue']:,.0f}**
- Revenue ganti oli: **Rp {row['oil_revenue']:,.0f}**
- Revenue non-oli / cross-sell: **Rp {row['non_oil_cross_sell_revenue']:,.0f}**
- Share cross-sell: **{row['cross_sell_share']:.1%}**

## 3. Interval Model
Metode: **{model_summary.get('interval_model_method')}**  
Jumlah episode interval oli: **{model_summary.get('n_oil_episodes')}**  
R2 log-duration: **{model_summary.get('interval_r2_log_duration'):.3f}**

Rata-rata interval ganti oli per segmen:

{interval_seg[['segmen_pemakaian_asli','n_episodes','avg_gap_days','avg_gap_km']].to_markdown(index=False)}

## 4. Market Basket / Cross-sell
Best rule by estimated revenue:
- Rule: **{best_rule.get('antecedents_txt','-')} → {best_rule.get('consequents_txt','-')}**
- Confidence: **{best_rule.get('confidence',0):.1%}**
- Lift: **{best_rule.get('lift',0):.2f}**
- Estimated rule revenue: **Rp {best_rule.get('estimated_rule_revenue',0):,.0f}**

## 5. Forecast
Forecast 8 minggu berikutnya menunjukkan estimasi kunjungan mingguan sebagai berikut:

{forecast[['week_start','forecast_visits','forecast_oil_visits','forecast_revenue']].to_markdown(index=False)}

## 6. Uplift Scenario

{uplift.to_markdown(index=False)}

## 7. Recommendation
Prioritas implementasi:
1. Kirim WA hanya untuk tier Warm Reminder ke atas, bukan blast semua pelanggan.
2. Tambahkan paket cross-sell berbasis market basket: oli + filter udara + tune-up.
3. Gunakan forecast mingguan untuk stok oli, filter, dan manpower cabang.
4. Jalankan A/B test agar uplift reminder bisa dibuktikan secara kausal.
"""
    path.write_text(text, encoding="utf-8")


# ----------------------------------------------------------------
# 12. MAIN ORCHESTRATION
# ----------------------------------------------------------------
def main() -> None:
    cfg = parse_args()
    make_dirs(cfg)

    print("[1/9] Load data...")
    master, svc, cust = load_data(cfg)

    print("[2/9] Data quality audit + feature engineering...")
    dq = data_quality_audit(master, svc)
    visits = build_visit_table(master, svc, cfg)
    episodes = build_oil_episodes(master, svc, cfg)

    print("[3/9] KPI + revenue analytics...")
    kpi = compute_kpis(master, svc, visits, cfg)
    rev_cat, rev_item = revenue_tables(svc)

    print("[4/9] Survival / personalized interval model...")
    episodes_scored, model_coef, interval_model, interval_summary = fit_interval_model(episodes, cfg)
    interval_seg = oil_interval_by_segment(episodes_scored)
    alerts = score_due_alerts(master, svc, interval_model, episodes_scored, cfg)

    print("[5/9] Market basket analysis...")
    rules, attach = run_market_basket(svc, cfg)

    print("[6/9] Demand forecasting...")
    forecast, backtest = run_demand_forecast(visits, svc, cfg)

    print("[7/9] Clustering + customer value/risk...")
    car_cluster, cluster_profile, cluster_confusion = run_clustering(master, visits, episodes_scored, cfg)
    cust_risk = customer_value_risk(master, visits, cfg)

    print("[8/9] Business uplift scenarios + plots...")
    uplift = build_uplift_scenarios(kpi, alerts)
    save_plots(cfg.output_dir, rev_cat, interval_seg, rules, forecast, cluster_profile, alerts)

    model_summary = {
        "current_date": str(cfg.current_date.date()),
        "has_lifelines": HAS_LIFELINES,
        "has_mlxtend": HAS_MLXTEND,
        "has_statsmodels": HAS_STATSMODELS,
        "interval_model_method": interval_summary.get("method"),
        "n_oil_episodes": interval_summary.get("n_episodes"),
        "interval_r2_log_duration": interval_summary.get("r2_log_duration"),
        "forecast_mape_model": float(backtest["mape_model"].iloc[0]) if len(backtest) else None,
        "forecast_mape_naive": float(backtest["mape_naive"].iloc[0]) if len(backtest) else None,
    }
    model_summary_df = pd.DataFrame([model_summary])

    print("[9/9] Export CSV, Excel, and Markdown report...")
    outputs = {
        "01_kpi_summary": kpi,
        "02_data_quality_audit": dq,
        "03_revenue_by_category": rev_cat,
        "04_revenue_by_item": rev_item,
        "05_oil_interval_by_segment": interval_seg,
        "06_interval_model_coefficients": model_coef,
        "07_due_alert_candidates": alerts,
        "08_market_basket_rules": rules,
        "09_oil_attach_rates": attach,
        "10_weekly_demand_forecast": forecast,
        "11_forecast_backtest": backtest,
        "12_cluster_profile": cluster_profile,
        "13_cluster_confusion": cluster_confusion,
        "14_customer_value_risk": cust_risk,
        "15_uplift_scenarios": uplift,
        "16_model_summary": model_summary_df,
    }

    for name, df in outputs.items():
        df.to_csv(cfg.output_dir / f"{name}.csv", index=False)

    write_excel(cfg.output_dir / "Smart_Workshop_Intelligence_Analysis.xlsx", outputs)
    write_markdown_report(cfg.output_dir / "Smart_Workshop_Intelligence_Report.md", model_summary, kpi, interval_seg, rules, forecast, uplift)

    print("\n=== DONE ===")
    print(f"Output folder: {cfg.output_dir}")
    print("Key files:")
    print(f"- {cfg.output_dir / 'Smart_Workshop_Intelligence_Analysis.xlsx'}")
    print(f"- {cfg.output_dir / 'Smart_Workshop_Intelligence_Report.md'}")
    print(f"- {cfg.output_dir / '07_due_alert_candidates.csv'}")
    print(f"- {cfg.output_dir / '08_market_basket_rules.csv'}")
    print(f"- {cfg.output_dir / '10_weekly_demand_forecast.csv'}")


if __name__ == "__main__":
    main()
