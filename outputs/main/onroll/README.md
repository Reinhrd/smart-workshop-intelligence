## Output Concept and Business Interpretation

This project does not only produce model files. Each output is designed to answer a specific business decision inside a workshop operation.

The core idea is:

```text
Service history data
→ vehicle service urgency
→ customer prioritization
→ cross-sell recommendation
→ weekly demand planning
→ revenue and retention strategy
```

In other words, the output is not just descriptive reporting. It is a decision layer for workshop intelligence.

---

## Output Architecture

The project outputs are divided into four groups:

| Output group         | Folder                | Purpose                                                           |
| -------------------- | --------------------- | ----------------------------------------------------------------- |
| Executive output     | `outputs/executive/`  | Business-facing workbook and narrative report                     |
| Main research output | `outputs/main/`       | Core analytical outputs used for decision-making                  |
| Supporting output    | `outputs/supporting/` | Technical validation, audit, model summary, and supporting tables |
| Visualization output | `outputs/plots/`      | Presentation-ready charts for README, report, or slides           |

The most important files for business interpretation are:

| File                                        | Business meaning                                                                          |
| ------------------------------------------- | ----------------------------------------------------------------------------------------- |
| `Smart_Workshop_Intelligence_Analysis.xlsx` | Executive workbook containing the full dashboard, KPI, model tables, and business outputs |
| `07_due_alert_candidates.csv`               | List of vehicles and customers prioritized for WA service reminders                       |
| `08_market_basket_rules.csv`                | Cross-sell rules showing which service items tend to occur together                       |
| `10_weekly_demand_forecast.csv`             | 8-week workshop visit forecast for operational planning                                   |
| `14_customer_value_risk.csv`                | Customer value and churn-risk proxy table for retention prioritization                    |

---

## 1. Due Alert Candidates — From Reminder Blast to Service Prioritization

The file `07_due_alert_candidates.csv` is the operational output for WA reminder targeting.

Instead of sending the same reminder to every customer, the model creates a prioritized list based on:

* days since last oil service,
* estimated kilometer progress since last oil service,
* personalized predicted oil interval,
* conditional due probability within the next 14 days,
* alert tier,
* and next-best-offer recommendation.

The model classifies 620 vehicles into three actionable tiers:

| Alert tier    | Number of vehicles | Interpretation                                                |
| ------------- | -----------------: | ------------------------------------------------------------- |
| Monitor       |                533 | Not urgent yet; keep in monitoring pool                       |
| Warm Reminder |                 71 | Getting close to due condition; suitable for soft WA reminder |
| High Priority |                 16 | Already close to or beyond estimated service due threshold    |
| Critical      |                  0 | No vehicle currently requires emergency-level escalation      |

The practical business insight is that only 87 vehicles should be treated as the immediate campaign target. This prevents the workshop from blasting all customers and allows the service team to focus on customers with higher service urgency.

The output also includes a `wa_message` column. This makes the file deployment-ready because the result is not only a score, but also a direct message template that can be used by a CRM, service advisor, or WA automation tool.

The deeper idea is that oil reminders become a prioritization system, not just a notification system.

---

## 2. Market Basket Rules — Turning Oil Service into Cross-sell Opportunity

The file `08_market_basket_rules.csv` contains association rules between service items.

The purpose is to answer this question:

```text
When a customer comes for one service item, what other service item is likely to be relevant?
```

The most valuable rules are not only selected by lift. They are interpreted using a combination of:

* support,
* confidence,
* lift,
* potential visits without the consequent item,
* average price of the consequent item,
* and estimated targeted revenue.

The highest estimated revenue opportunities include:

| Rule                                         | Business interpretation                                                  |
| -------------------------------------------- | ------------------------------------------------------------------------ |
| `Ganti Oli Mesin → Tune Up / Servis Berkala` | Oil service can become an entry point for periodic maintenance offers    |
| `Filter Oli → Tune Up / Servis Berkala`      | Customers replacing oil filters are likely in a maintenance mindset      |
| `Filter Udara → Tune Up / Servis Berkala`    | Air filter replacement can trigger engine performance service offers     |
| `Filter Udara → Busi (set)`                  | Air intake maintenance can be bundled with ignition system checks        |
| `Ganti Oli Mesin → Filter Udara`             | Oil reminders can be expanded into light preventive maintenance packages |

The strongest business story is that oil service is not the final product. It is the entry point into a broader maintenance basket.

This supports a better WA reminder strategy:

```text
Weak reminder:
"Your vehicle is due for oil change."

Better reminder:
"Your vehicle is approaching oil service due. Based on similar service patterns, we also recommend checking filter udara and tune up package."
```

However, the estimated rule revenue should not be interpreted as guaranteed incremental revenue. It is a targeting opportunity, not causal proof. To measure actual uplift, the campaign should be validated through A/B testing or randomized rollout.

---

## 3. Weekly Demand Forecast — Connecting Marketing with Workshop Capacity

The file `10_weekly_demand_forecast.csv` estimates workshop demand for the next 8 weeks.

The forecast shows a relatively stable weekly demand pattern:

| Metric                           |                                 Value |
| -------------------------------- | ------------------------------------: |
| Forecast horizon                 |                               8 weeks |
| Forecast visit range             |             ~42 to 47 visits per week |
| Total forecast visits            |                           ~353 visits |
| Estimated total forecast revenue |                       ~Rp 414 million |
| Forecast oil visits              | ~36 to 40 oil-related visits per week |

This output is important because reminder campaigns should not be separated from workshop capacity.

If the workshop sends too many reminders in the same week, demand may exceed available mechanics, service slots, or inventory. The forecast helps the workshop control campaign timing.

The operational use cases are:

* estimate mechanic workload,
* prepare oil and filter inventory,
* plan booking slots,
* avoid campaign overload,
* and align WA reminder volume with service capacity.

This makes the project more complete. It does not only predict who should be contacted, but also helps decide when the workshop is ready to absorb the demand.

---

## 4. Customer Value and Churn-risk Proxy — Prioritizing Customers, Not Just Vehicles

The file `14_customer_value_risk.csv` is a customer-level prioritization table.

It summarizes customer behavior using:

* total visits,
* number of vehicles owned,
* total revenue,
* last visit date,
* average visit revenue,
* days since last visit,
* value segment,
* and churn-risk proxy.

The customer value segmentation divides 533 customers into four balanced groups:

| Value segment | Number of customers | Interpretation             |
| ------------- | ------------------: | -------------------------- |
| VIP           |                 133 | Highest revenue customers  |
| High          |                 133 | Strong revenue potential   |
| Medium        |                 133 | Stable mid-value customers |
| Low           |                 134 | Lower historical revenue   |

The churn-risk proxy is based on recency behavior. Customers who have not returned for a longer period are treated as higher reactivation targets.

This is not a true churn model yet because there is no campaign response label or confirmed churn event. It is a practical proxy for prioritizing retention action.

The business logic is:

```text
High value + high recency risk
→ prioritize for reactivation campaign

High value + active
→ maintain with premium service reminders

Low value + high risk
→ low-cost automated reminder only
```

This helps the workshop avoid treating all customers equally. A VIP customer with multiple vehicles and high historical revenue should not receive the same treatment as a low-value customer with low service frequency.

---

## 5. How the Outputs Work Together

The strength of this project is not in one model. The value comes from how each output connects to a business decision.

| Business question                      | Output used                                 | Decision produced                            |
| -------------------------------------- | ------------------------------------------- | -------------------------------------------- |
| Who should receive a service reminder? | `07_due_alert_candidates.csv`               | Target customer and vehicle list             |
| What should be offered?                | `08_market_basket_rules.csv`                | Cross-sell or next-best-offer                |
| When should the campaign be sent?      | `10_weekly_demand_forecast.csv`             | Campaign timing and weekly capacity planning |
| Which customers matter most?           | `14_customer_value_risk.csv`                | Retention and prioritization strategy        |
| How should executives read the result? | `Smart_Workshop_Intelligence_Analysis.xlsx` | KPI dashboard and model summary              |

The complete decision flow is:

```text
1. Identify vehicles approaching service due.
2. Rank customers by alert tier and priority score.
3. Attach relevant next-best-offer from market basket rules.
4. Check weekly demand forecast before launching campaign.
5. Prioritize high-value or at-risk customers.
6. Use the executive workbook to monitor KPI and business impact.
```

---

## 6. Deep Business Interpretation

The main finding is that service reminder should not be viewed as a small operational feature. In a workshop business, reminder logic can become a revenue engine.

A simple rule-based system only says:

```text
This car has reached the oil change threshold.
```

The Smart Workshop Intelligence system says:

```text
This customer owns this vehicle.
This vehicle is approaching service due.
This customer has this value profile.
This service item is likely to be relevant.
This week has this expected workshop demand.
Therefore, this customer should receive this message with this offer at this timing.
```

That is the difference between a notification system and an analytics engine.

From the output, the strongest business conclusion is:

> Oil service is the anchor, but cross-sell is the growth opportunity.

Oil change creates recurring customer contact. Market basket rules turn that contact into a service package opportunity. Forecasting ensures the campaign does not overload operations. Customer value-risk scoring ensures that the most important customers receive priority.

This makes the project relevant for three business functions:

| Function        | How this project helps                             |
| --------------- | -------------------------------------------------- |
| Marketing       | Sends targeted reminders instead of mass messages  |
| Service advisor | Recommends relevant cross-sell items               |
| Operations      | Plans weekly capacity and inventory                |
| Management      | Monitors revenue opportunity and customer priority |

---

## 7. Why Supporting Outputs Are Still Included

The supporting files are not the main story, but they are important for transparency.

| Supporting file                      | Why it matters                                                  |
| ------------------------------------ | --------------------------------------------------------------- |
| `01_kpi_summary.csv`                 | Validates the overall business scale                            |
| `02_data_quality_audit.csv`          | Shows data quality checks before modeling                       |
| `03_revenue_by_category.csv`         | Explains revenue composition                                    |
| `04_revenue_by_item.csv`             | Shows item-level revenue contribution                           |
| `05_oil_interval_by_segment.csv`     | Supports the personalized interval logic                        |
| `06_interval_model_coefficients.csv` | Provides model interpretability                                 |
| `09_oil_attach_rates.csv`            | Supports cross-sell attach-rate analysis                        |
| `11_forecast_backtest.csv`           | Evaluates forecast performance                                  |
| `12_cluster_profile.csv`             | Explains customer/vehicle cluster characteristics               |
| `13_cluster_confusion.csv`           | Compares clustering output with synthetic ground-truth segments |
| `15_uplift_scenarios.csv`            | Estimates potential business impact under different assumptions |
| `16_model_summary.csv`               | Summarizes model configuration and performance                  |

These files are included so that the project is reproducible and auditable. The README focuses on business interpretation, while the supporting outputs provide technical evidence.

---

## 8. Limitations

This project uses synthetic data. The dataset was generated to simulate a realistic workshop environment, including vehicle types, service items, usage segments, mileage behavior, service seasonality, and transaction patterns.

Because the data is synthetic, the output should be interpreted as a proof of concept, not as real business performance.

Several limitations must be noted:

1. The WA reminder impact is not causal yet.
2. The churn-risk score is a recency-based proxy, not a trained churn classifier.
3. Market basket rules show association, not causation.
4. Forecasting is based on historical visit patterns and synthetic calendar effects.
5. Real implementation requires actual booking, campaign, and conversion data.

---

## 9. Next Steps

The next development phase should focus on deployment and validation.

Recommended next steps:

1. Connect the alert candidates table to a real CRM or WA API.
2. Add campaign response data such as delivered, opened, replied, booked, and converted.
3. Build a true conversion model using historical campaign data.
4. Run A/B testing to measure incremental visit uplift.
5. Add inventory forecasting for oil, filters, brake pads, batteries, and tires.
6. Deploy the dashboard using Streamlit, Power BI, or Looker Studio.
7. Convert the scoring pipeline into a scheduled batch job.

The ideal production version would run weekly:

```text
New service data
→ refresh vehicle status
→ score service due probability
→ generate WA target list
→ attach next-best-offer
→ check capacity forecast
→ send campaign
→ track conversion
→ update model
```

This closes the loop from analytics to action.
