# UPI Transaction Reconciliation Engine for Payment Aggregators

A modular, production-ready Python application designed for Payment Aggregators (PAs) to reconcile internal merchant transaction logs against National Payments Corporation of India (NPCI) / Sponsor Bank settlement files on a $T+1$ cycle.

---

## 📁 Project Structure

```text
.
├── data/
│   ├── merchant_logs.csv         # Synthetic merchant transaction logs (~20 rows)
│   └── npci_settlements.csv      # Synthetic NPCI settlement files (~20 rows)
├── engine/
│   ├── __init__.py               # Engine package initializer
│   ├── normalizer.py             # Regex UTR extraction, amount & date cleaning
│   └── reconciler.py             # Matching logic, discrepancy categorization, & KPI metrics
├── tests/
│   └── test_reconciliation.py    # Unit tests for normalizer and reconciliation engine
├── app.py                        # Interactive Streamlit dashboard
├── requirements.txt              # Core dependencies (pandas, streamlit)
└── README.md                     # Project documentation
```

---

## ⚡ Core Features & Business Logic

### 1. Robust Data Normalization (`engine/normalizer.py`)
- **UTR Cleaning via Regex**: Extracts standard 12-digit numeric RRN/UTR regardless of formats:
  - Prefixed strings: `UTR-424510012303`, `utr:424510012304`
  - URL / Path strings: `UPI/424510012305/PAY`
  - Hyphenated or spaced formats: `4245-1001-2308`, ` 424510012306 `
  - Scientific notation / floats: `424510012301.0`
- **Amount Standardization**: Strips currency identifiers (`₹`, `INR`, `Rs.`), commas, and formats negative accounting amounts (`(500.00)` $\rightarrow$ `-500.00`).
- **Date Alignment**: Standardizes timestamps into ISO `YYYY-MM-DD` format to verify $T+1$ settlement cycles.

### 2. Reconciliation Engine (`engine/reconciler.py`)
Classifies every transaction into one of four core statuses:

| Status | Business Condition | Payment Aggregator Impact |
| :--- | :--- | :--- |
| **`Matched`** | Standard match on normalized 12-digit UTR and amount settled on $T+1$. | Funds settled smoothly; ready for merchant nodal payout. |
| **`Unsettled`** | Order is marked successful in merchant log but absent from NPCI settlement file. | PA has credited merchant or debited customer without receiving sponsor bank funds. |
| **`Double-Settled`** | Single UTR appears multiple times in NPCI settlement file. | Duplicate settlement; risk of over-crediting and operational leakage. |
| **`Refund`** | Negative settlement entry in NPCI mapped back to the original parent merchant order. | Auto-mapped refund to debit merchant nodal ledger. |

### 3. Streamlit Dashboard (`app.py`)
- **Top KPI Cards**: Total Transactions, Matched Count, Unsettled Count, Double-Settled Count, and Total Refund Amount.
- **File Ingestion**: Upload custom Merchant and NPCI CSV files, or automatically fall back to sample CSVs.
- **Multi-Tab Views**:
  - *Reconciled Records*: Full tabular view with status filtering.
  - *Discrepancy Queue*: Filtered to flagged exceptions with recommended operational next steps.
  - *UTR Normalization Audit*: Side-by-side comparison of raw strings vs cleaned 12-digit UTRs.
  - *Merchant Breakdown*: Aggregated statistics per merchant partner.
- **CSV Export**: One-click download button for the reconciled audit report.

---

## 🚀 Quick Start Guide

### 1. Set Up Environment & Install Dependencies

```bash
# Clone or navigate to the project directory
cd /Users/pragnya/Desktop/hackathon

# (Optional) Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

### 2. Run the Dashboard

```bash
streamlit run app.py
```

Open your browser at `http://localhost:8501`.

### 3. Run Test Suite

```bash
python3 -m unittest discover tests
```
