# Smart Workshop Intelligence — Advanced Data Scientist Execution

## 1. Executive Summary

Dataset ini sudah cukup kuat untuk dijadikan portfolio/pitch data scientist karena tidak berhenti pada **threshold 96% ganti oli**. Dari data yang tersedia, workflow analytics yang paling bernilai adalah:

1. **Personalized Service Interval** — memprediksi kapan tiap mobil perlu servis berdasarkan pola aktual, bukan interval statis.
2. **Market Basket / Cross-sell** — mengubah reminder oli menjadi rekomendasi paket servis bernilai lebih tinggi.
3. **Demand Forecasting** — membantu bengkel mengatur stok, mekanik, dan booking mingguan.
4. **Customer Segmentation & Retention** — memprioritaskan pelanggan bernilai tinggi dan yang mulai berisiko hilang.

## 2. KPI Utama

| Metric | Value |
|---|---:|
| Pelanggan unik | 533 |
| Mobil unik | 620 |
| Kunjungan unik | 8,354 |
| Baris item servis | 29,023 |
| Total revenue | Rp 9,800,823,000 |
| Revenue ganti oli | Rp 3,593,580,000 |
| Revenue non-oli / cross-sell | Rp 6,207,243,000 |
| Share cross-sell | 63.3% |
| AOV per visit | Rp 1,173,189 |

Insight bisnis utama: **ganti oli hanya menyumbang 36.7% revenue**, sedangkan item non-oli/cross-sell menyumbang **63.3%**. Maka reminder WA tidak boleh dilihat sebagai notifikasi biasa, tetapi sebagai entry point ke revenue tambahan.

## 3. Personalized Service Interval

Model yang dipakai: **log-normal AFT proxy** dengan target `log(gap_days)` antar event `Ganti Oli Mesin`. Kovariat meliputi `km_per_bulan`, `interval_oli_km`, `tahun`, `bahan_bakar`, `penggerak`, `jenis_oli`, dan `segmen_pemakaian_asli`.

Model summary:
| metric                    |       value |
|:--------------------------|------------:|
| N episodes                | 6455        |
| R2                        |    0.880526 |
| Adj R2                    |    0.88034  |
| Residual sigma log-days   |    0.208144 |
| Median actual gap days    |   78        |
| Median predicted gap days |   75.1098   |

Rata-rata interval aktual per segmen:

| segmen_pemakaian_asli   |    n |   avg_gap_days |   median_gap_days | avg_gap_km   | median_gap_km   |
|:------------------------|-----:|---------------:|------------------:|:-------------|:----------------|
| Heavy Daily             | 3990 |           67.3 |                62 | 6,147.0      | 5,892.5         |
| Weekend Warrior         | 1195 |          110.1 |                99 | 5,679.8      | 5,366.0         |
| Light Commuter          | 1270 |          221.1 |               207 | 6,858.0      | 6,588.5         |

Interpretasi:
- Heavy Daily memang jauh lebih cepat kembali servis.
- Light Commuter punya interval kalender lebih panjang.
- Ini membuktikan bahwa rule tunggal 10.000 km / 6 bulan terlalu kasar untuk CRM modern.

Alert output:
- Monitor: 533 mobil
- Warm Reminder: 71 mobil
- High Priority: 16 mobil
- Critical: 0 mobil

File `07_due_alert_candidates.csv` sudah berisi nomor WA, score prioritas, status rekomendasi, next-best-offer, dan draft pesan WA.

## 4. Market Basket / Cross-sell

Top association rules:

| antecedent      | consequent               | support   | confidence   |   lift | estimated_rule_revenue_if_targeted   |
|:----------------|:-------------------------|:----------|:-------------|-------:|:-------------------------------------|
| Ganti Oli Mesin | Tune Up / Servis Berkala | 17.9%     | 21.2%        |   1.18 | Rp 629,207,300                       |
| Filter Oli      | Tune Up / Servis Berkala | 15.1%     | 21.0%        |   1.17 | Rp 531,606,907                       |
| Filter Udara    | Tune Up / Servis Berkala | 14.6%     | 21.5%        |   1.2  | Rp 510,539,527                       |
| Filter Udara    | Busi (set)               | 12.4%     | 18.2%        |   1.24 | Rp 278,692,673                       |
| Ganti Oli Mesin | Filter Udara             | 67.9%     | 80.1%        |   1.18 | Rp 214,219,526                       |
| Ganti Oli Mesin | Filter Kabin/AC          | 25.6%     | 30.2%        |   1.13 | Rp 208,865,377                       |
| Filter Kabin/AC | Tune Up / Servis Berkala | 5.2%      | 19.5%        |   1.09 | Rp 186,368,727                       |
| Filter Oli      | Filter Udara             | 57.8%     | 80.3%        |   1.18 | Rp 180,453,957                       |

Makna data scientist-nya:
- `confidence` menjawab: dari pelanggan yang punya antecedent, berapa peluang mereka juga membeli consequent.
- `lift` menjawab: apakah relasi itu benar-benar lebih kuat daripada kebetulan.
- `estimated_rule_revenue_if_targeted` memberi ranking bisnis, bukan cuma ranking statistik.

Rule paling penting secara revenue adalah **Ganti Oli Mesin → Tune Up / Servis Berkala**, bukan sekadar `oli → filter oli`, karena nilainya lebih tinggi untuk upsell.

## 5. Demand Forecasting

Model: weekly SARIMAX dengan variabel eksogen:
- payday window,
- pra-Lebaran,
- libur Lebaran.

Backtest 12 minggu terakhir:

| model                     |   test_mape_last_12_weeks | notes                                                                              |
|:--------------------------|--------------------------:|:-----------------------------------------------------------------------------------|
| Naive rolling 4-week mean |                  0.105659 | baseline                                                                           |
| SARIMAX exogenous         |                  0.101623 | features: payday, pre-Lebaran, Lebaran holiday; order=(1,1,1), seasonal=(1,0,0,52) |

Forecast 8 minggu berikutnya:

| week_start   |   forecast_visits |   lower_95 |   upper_95 |   forecast_oil_visits | forecast_revenue   |
|:-------------|------------------:|-----------:|-----------:|----------------------:|:-------------------|
| 2026-06-22   |              45.2 |    31.1815 |    59.2781 |                  38.3 | Rp 53,063,107      |
| 2026-06-29   |              45.6 |    31.5495 |    59.7101 |                  38.7 | Rp 53,532,366      |
| 2026-07-06   |              42   |    27.9345 |    56.096  |                  35.6 | Rp 49,291,864      |
| 2026-07-13   |              42   |    27.9678 |    56.1293 |                  35.6 | Rp 49,330,887      |
| 2026-07-20   |              43.6 |    29.5229 |    57.6845 |                  37   | Rp 51,155,389      |
| 2026-07-27   |              46.8 |    32.7172 |    60.8787 |                  39.7 | Rp 54,902,848      |
| 2026-08-03   |              45.5 |    31.3924 |    59.5539 |                  38.5 | Rp 53,348,620      |
| 2026-08-10   |              42.1 |    28.0397 |    56.2012 |                  35.7 | Rp 49,415,238      |

Implikasi operasional:
- forecast kunjungan dapat diterjemahkan ke kebutuhan oli, filter, stok fast-moving parts, dan jumlah slot mekanik.
- forecast revenue memberi batas bawah estimasi cash-inflow bengkel.

## 6. Clustering & Segmentation

Cluster profile:

|   cluster_id |   cars |   avg_km_per_month |   avg_oil_gap_days |   avg_visits_per_year |   avg_revenue_per_year | top_hidden_segment   |
|-------------:|-------:|-------------------:|-------------------:|----------------------:|-----------------------:|:---------------------|
|            1 |    242 |             983.66 |           212.983  |               2.766   |            3.25713e+06 | Light Commuter       |
|            0 |    196 |            1537.71 |           217.274  |               2.98051 |            3.72956e+06 | Light Commuter       |
|            2 |    182 |            2675.93 |            64.7775 |               6.61339 |            7.59323e+06 | Heavy Daily          |

Clustering tidak dipakai sebagai gimmick. Ia digunakan untuk menentukan:
- interval reminder yang berbeda per segment,
- paket servis yang berbeda,
- prioritas campaign,
- cara komunikasi WA yang berbeda.

## 7. Revenue Uplift Scenario

| scenario                          |   target_count | assumed_conversion   | avg_oil_plus_crosssell_value   | estimated_incremental_revenue   |
|:----------------------------------|---------------:|:---------------------|:-------------------------------|:--------------------------------|
| Top 100 due-reminder WA           |            100 | 18%                  | Rp 1,263,893                   | Rp 22,750,069                   |
| Top 250 due-reminder WA           |            250 | 18%                  | Rp 1,263,893                   | Rp 56,875,171                   |
| All High/Critical due-reminder WA |             16 | 18%                  | Rp 1,263,893                   | Rp 3,640,011                    |

Catatan metodologis: uplift di atas masih skenario, bukan klaim kausal. Untuk membuktikan dampak campaign, perlu randomized rollout atau A/B test.

## 8. Output yang Dihasilkan

- `Smart_Workshop_Intelligence_Analysis.xlsx`: workbook eksekutif berisi dashboard dan semua tabel model.
- `07_due_alert_candidates.csv`: daftar target WA berbasis probabilitas due dan next-best-offer.
- `08_market_basket_rules.csv`: hasil association rules.
- `10_weekly_demand_forecast.csv`: forecast 8 minggu.
- `14_customer_value_risk.csv`: scoring customer value & churn-risk proxy.
- PNG plots untuk presentasi.
