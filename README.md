# smart-workshop-intelligence
End-to-end data science pipeline for oil service reminders, cross-sell recommendation, demand forecasting, and customer prioritization.

# Smart Workshop Intelligence

## Overview

Smart Workshop Intelligence is an end-to-end data science project for a car workshop or automotive dealer. The project transforms service history data into an analytics engine for personalized oil service reminders, cross-sell recommendation, demand forecasting, customer segmentation, and customer value-risk prioritization.

The main idea is to move beyond a simple rule-based oil reminder. Instead of only sending a message when a vehicle reaches a fixed service threshold, this project builds a data-driven workflow that answers five business questions:

1. Which vehicles should receive a service reminder?
2. Which customers should be prioritized?
3. What additional service items can be offered?
4. How many workshop visits should be expected in the next 8 weeks?
5. Which customer segments generate the highest business value?

## Business Problem

Car workshops often rely on static service rules such as mileage or time-based reminders. This approach is useful, but it treats all customers and vehicles in the same way. In reality, each vehicle has different usage intensity, service behavior, and revenue potential.

This project proposes a smarter approach by combining service history, vehicle profile, transaction data, and customer behavior into a single analytics pipeline.

## Project Objectives

The objectives of this project are:

* Build a personalized oil service reminder system.
* Score customers and vehicles based on service urgency.
* Identify cross-sell opportunities using market basket analysis.
* Forecast weekly workshop demand for operational planning.
* Segment customers and vehicles based on usage and revenue behavior.
* Produce executive-ready outputs for business users.

## Dataset

The dataset is synthetic and created for demonstration purposes. It represents a Toyota workshop service history in Medan.

Main data tables:

| File                  | Description                                 |
| --------------------- | ------------------------------------------- |
| `pelanggan.csv`       | Customer-level information                  |
| `pelanggan_mobil.csv` | Vehicle and owner master data               |
| `riwayat_servis.csv`  | Transactional service history at item level |

The dataset contains:

* 533 unique customers
* 620 vehicles
* 8,354 service visits
* 29,023 service item rows
* Service history from 2022 to 2026

All names, phone numbers, addresses, and vehicle plate numbers are synthetic.

## Analytics Workflow

The pipeline follows this structure:

```text
Raw service data
→ Data quality audit
→ Feature engineering
→ Personalized service interval modeling
→ Due alert scoring
→ Market basket analysis
→ Weekly demand forecasting
→ Customer segmentation
→ Customer value-risk scoring
→ Executive outputs
```

## Methods Used

| Analytics Layer               | Method                                                                  |
| ----------------------------- | ----------------------------------------------------------------------- |
| Data quality audit            | Missing value check, duplicate check, foreign key check                 |
| Feature engineering           | Visit-level aggregation, service interval calculation, revenue features |
| Personalized service interval | Survival-style interval modeling / duration prediction                  |
| WA alert scoring              | Priority score based on time progress, km progress, and due probability |
| Market basket analysis        | Association rules using support, confidence, and lift                   |
| Demand forecasting            | Weekly forecast using lag features and calendar-based features          |
| Customer segmentation         | K-Means clustering                                                      |
| Customer value-risk           | Revenue scoring and recency-risk proxy                                  |

## Key Outputs

| Output                                      | Description                                                             |
| ------------------------------------------- | ----------------------------------------------------------------------- |
| `Smart_Workshop_Intelligence_Analysis.xlsx` | Executive workbook containing dashboard, KPI, model tables, and outputs |
| `07_due_alert_candidates.csv`               | List of vehicles/customers prioritized for WA reminders                 |
| `08_market_basket_rules.csv`                | Association rules for cross-sell recommendations                        |
| `10_weekly_demand_forecast.csv`             | 8-week workshop demand forecast                                         |
| `14_customer_value_risk.csv`                | Customer value and churn-risk proxy scoring                             |
| PNG plots                                   | Presentation-ready visualizations                                       |

## Key Business Findings

### 1. Revenue Structure

The total simulated revenue is approximately Rp 9.8 billion. Oil-related service is the main anchor, but non-oil and cross-sell services contribute around 63.3% of total revenue.

This means that oil service reminders should not only be treated as maintenance notifications, but also as an entry point for additional revenue.

### 2. Alert Prioritization

The alert scoring model classifies vehicles into four tiers:

| Alert Tier    | Number of Vehicles |
| ------------- | -----------------: |
| Monitor       |                533 |
| Warm Reminder |                 71 |
| High Priority |                 16 |
| Critical      |                  0 |

The actionable group consists of Warm Reminder and High Priority vehicles. This prevents unnecessary mass messaging and helps the workshop focus on customers with higher service urgency.

### 3. Personalized Service Interval

Average oil change interval differs across usage segments:

| Segment         | Average Oil Change Gap |
| --------------- | ---------------------: |
| Heavy Daily     |               ~67 days |
| Weekend Warrior |              ~110 days |
| Light Commuter  |              ~221 days |

This confirms that a single static oil service interval is not enough. Heavy usage vehicles require more frequent reminders, while light commuter vehicles can be handled with a longer reminder cycle.

### 4. Market Basket Opportunity

Market basket analysis shows several relevant cross-sell rules:

```text
Filter Udara → Busi (set)
Filter Udara → Tune Up
Filter Oli → Filter Udara
Oli → Filter Udara
Oli → Tune Up
Filter Oli → Tune Up
```

These rules can be translated into next-best-offer logic in WA reminders or service advisor recommendations.

### 5. Demand Forecast

The 8-week forecast estimates approximately 42–47 workshop visits per week. This helps the workshop plan mechanic capacity, booking slots, oil stock, filter stock, and campaign timing.

### 6. Customer Segmentation

The clustering model identifies a high-value Heavy Daily segment with higher monthly mileage and higher annualized revenue. This segment should receive more proactive reminders and service package offers.

## How to Run

Install dependencies:

```bash
pip install lifelines mlxtend statsmodels scikit-learn xlsxwriter openpyxl tabulate
```

Run the pipeline:

```bash
python src/smart_workshop_advanced_pipeline.py \
  --input_dir data/raw \
  --output_dir outputs
```

For Google Colab:

```python
!python -W ignore::DeprecationWarning /content/smart_workshop_advanced_pipeline.py \
  --input_dir /content \
  --output_dir /content/output_swi
```

## Repository Structure

```text
smart-workshop-intelligence/
├── README.md
├── requirements.txt
├── data/
├── src/
├── notebooks/
├── outputs/
└── docs/
```

## Business Impact

This project can support three business functions:

1. **Customer retention**
   Prioritize customers who are likely due for service.

2. **Revenue growth**
   Use oil service reminders as a trigger for cross-sell offers.

3. **Operational planning**
   Forecast weekly demand to prepare mechanics, service slots, and inventory.

## Limitations

This project uses synthetic data, so the results are suitable for portfolio demonstration, proof of concept, and pitch materials. For real implementation, the model should be retrained and validated using actual workshop data.

The WA reminder impact should also be tested using A/B testing or randomized campaign rollout to measure true incremental impact.

## Next Steps

Future improvements:

* Add real booking conversion data.
* Add actual WA campaign response data.
* Build an API endpoint for real-time alert scoring.
* Add dashboard deployment using Streamlit or Power BI.
* Run A/B testing to measure campaign uplift.
* Add inventory forecasting for oil, filters, brake pads, and batteries.

## Tech Stack

* Python
* Pandas
* NumPy
* Scikit-learn
* Lifelines
* Mlxtend
* Matplotlib
* XlsxWriter
* Google Colab

## Project Status

Completed as a portfolio-ready data science pipeline.

