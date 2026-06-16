# Data Documentation

This folder contains the synthetic dataset used in the Smart Workshop Intelligence project.

## Important Disclaimer

All data in this project is synthetic and generated for demonstration, portfolio, and proof-of-concept purposes. The dataset does not contain real customer data, real phone numbers, real addresses, or real vehicle registration numbers.

The raw dataset was generated using:

```text
scripts/data_gen.py
```

## Data Generation Logic

The synthetic data generation process was designed to support three main analytics tasks:

1. **Personalized service interval modeling**
   Oil change intervals are influenced by vehicle usage segment, monthly mileage, engine type, fuel type, and oil type.

2. **Market basket analysis**
   Service items were generated with intentional association structures, such as oil service being commonly followed by filter replacement, tune-up, or other related service items.

3. **Demand forecasting**
   Service dates were generated with calendar patterns such as weekdays, weekends, post-payday periods, pre-Lebaran demand increase, and holiday effects.

## Raw Data Files

| File                      | Description                                                 |
| ------------------------- | ----------------------------------------------------------- |
| `raw/pelanggan.csv`       | Synthetic customer list                                     |
| `raw/pelanggan_mobil.csv` | Synthetic customer-vehicle master data                      |
| `raw/riwayat_servis.csv`  | Synthetic service transaction history at service-item level |

## Dataset Scope

The dataset represents a simulated Toyota workshop in Medan, Indonesia. It includes customer profiles, vehicle profiles, service history, service categories, service items, service dates, mileage, and transaction values.

## Privacy Note

Although the dataset contains columns such as customer names, phone numbers, addresses, and vehicle registration numbers, all values are randomly generated and fictitious. They are included only to make the business workflow realistic, especially for WA reminder simulation and customer prioritization.
