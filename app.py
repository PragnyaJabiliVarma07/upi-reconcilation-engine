"""UPI Transaction Reconciliation Engine - Payment Aggregator Dashboard.

Built with Streamlit and Pandas.
"""

from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path
import pandas as pd
import streamlit as st

from engine.normalizer import (
    normalize_amount,
    normalize_date,
    normalize_utr,
)
from engine.reconciler import (
    get_summary_metrics,
    reconcile_transactions,
)

# Set page configuration
st.set_page_config(
    page_title="UPI Reconciliation Engine | Payment Aggregator",
    page_icon="💳",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for polished finance/fintech theme
st.markdown(
    """
    <style>
        .main-header {
            font-size: 2.1rem;
            font-weight: 700;
            color: #1e293b;
            margin-bottom: 0.2rem;
        }
        .sub-header {
            font-size: 1.05rem;
            color: #64748b;
            margin-bottom: 1.5rem;
        }
        .metric-card {
            background: #ffffff;
            border-radius: 10px;
            padding: 16px 20px;
            border: 1px solid #e2e8f0;
            box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.05);
            margin-bottom: 10px;
        }
        .metric-title {
            font-size: 0.85rem;
            font-weight: 600;
            color: #64748b;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .metric-value {
            font-size: 1.85rem;
            font-weight: 700;
            color: #0f172a;
            margin-top: 4px;
        }
        .badge-matched {
            background-color: #dcfce7;
            color: #15803d;
            padding: 4px 8px;
            border-radius: 6px;
            font-weight: 600;
        }
        .badge-unsettled {
            background-color: #fee2e2;
            color: #b91c1c;
            padding: 4px 8px;
            border-radius: 6px;
            font-weight: 600;
        }
        .badge-double {
            background-color: #f3e8ff;
            color: #7e22ce;
            padding: 4px 8px;
            border-radius: 6px;
            font-weight: 600;
        }
        .badge-refund {
            background-color: #e0f2fe;
            color: #0369a1;
            padding: 4px 8px;
            border-radius: 6px;
            font-weight: 600;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# Paths for sample data
DATA_DIR = Path(__file__).parent / "data"
DEFAULT_MERCHANT_PATH = DATA_DIR / "merchant_logs.csv"
DEFAULT_NPCI_PATH = DATA_DIR / "npci_settlements.csv"


def load_data(
    merchant_file,
    npci_file,
) -> tuple[pd.DataFrame, pd.DataFrame, bool]:
    """Load merchant and NPCI datasets either from upload or default samples."""
    is_default = False

    if merchant_file is not None:
        merchant_df = pd.read_csv(merchant_file)
    elif DEFAULT_MERCHANT_PATH.exists():
        merchant_df = pd.read_csv(DEFAULT_MERCHANT_PATH)
        is_default = True
    else:
        merchant_df = pd.DataFrame()

    if npci_file is not None:
        npci_df = pd.read_csv(npci_file)
    elif DEFAULT_NPCI_PATH.exists():
        npci_df = pd.read_csv(DEFAULT_NPCI_PATH)
        is_default = True
    else:
        npci_df = pd.DataFrame()

    return merchant_df, npci_df, is_default


# ---------------- SIDEBAR ----------------
with st.sidebar:
    st.image(
        "https://img.icons8.com/color/96/bank-cards.png",
        width=56,
    )
    st.markdown("## **Aggregator Control**")
    st.caption("Reconciliation Gateway • NPCI T+1 Settlement")

    st.markdown("---")
    st.markdown("### 📁 Data Ingestion")
    
    uploaded_merchant = st.file_uploader(
        "Upload Merchant Logs (.csv)",
        type=["csv"],
        help="Upload CSV containing order_id, merchant_id, utr, amount, transaction_date",
    )

    uploaded_npci = st.file_uploader(
        "Upload NPCI Settlements (.csv)",
        type=["csv"],
        help="Upload CSV containing settlement_id, utr, amount, settlement_date, type",
    )

    st.markdown("---")
    st.markdown("### ⚙️ Engine Parameters")
    st.info("Tolerance: ₹0.00 (Exact)\nDate Alignment: T+1\nUTR Pattern: 12-Digit RRN")

    st.markdown("---")
    st.caption("UPI Transaction Reconciliation Engine v1.0")


# ---------------- MAIN CONTENT ----------------
st.markdown('<div class="main-header">UPI Transaction Reconciliation Engine</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-header">Automated ingestion, regex UTR normalization, and discrepancy detection for Payment Aggregators</div>',
    unsafe_allow_html=True,
)

# Load data
merchant_df, npci_df, using_defaults = load_data(uploaded_merchant, uploaded_npci)

if merchant_df.empty or npci_df.empty:
    st.error("Missing input files. Please ensure both Merchant Logs and NPCI Settlement CSVs are available.")
    st.stop()

if using_defaults and uploaded_merchant is None and uploaded_npci is None:
    st.info(
        "ℹ️ **Default Sample Data Loaded**: Using synthetic datasets from `data/merchant_logs.csv` and "
        "`data/npci_settlements.csv` simulating standard matches, format differences, unsettled orders, duplicate settlements, and refunds."
    )

# Execute reconciliation
reconciled_df, unmatched_npci_df = reconcile_transactions(merchant_df, npci_df)
metrics = get_summary_metrics(reconciled_df)

# ---------------- METRIC CARDS ----------------
col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric(
        label="Total Transactions",
        value=f"{metrics['total_transactions']:,}",
        help="Total merchant order volume ingested for reconciliation",
    )

with col2:
    st.metric(
        label="Matched Count",
        value=f"{metrics['matched_count']:,}",
        delta=f"{metrics['match_rate']}% Match Rate",
        delta_color="normal",
        help="Transactions with identical 12-digit UTR and amount settled on T+1",
    )

with col3:
    st.metric(
        label="Unsettled Count",
        value=f"{metrics['unsettled_count']:,}",
        delta=f"-{metrics['unsettled_count']} Missing in NPCI" if metrics['unsettled_count'] > 0 else "0",
        delta_color="inverse",
        help="Orders present in merchant log but missing from NPCI settlement file",
    )

with col4:
    st.metric(
        label="Double-Settled Count",
        value=f"{metrics['double_settled_count']:,}",
        delta=f"{metrics['double_settled_count']} Duplicates" if metrics['double_settled_count'] > 0 else "0",
        delta_color="inverse",
        help="Multiple positive settlement records in NPCI for a single UTR",
    )

with col5:
    st.metric(
        label="Total Refund Amount",
        value=f"₹{metrics['total_refund_amount']:,.2f}",
        delta=f"{metrics['refund_count']} orders refunded",
        delta_color="off",
        help="Total sum of negative settlement entries mapped back to original merchant orders",
    )

st.markdown("---")

# ---------------- DOWNLOAD & ACTION BAR ----------------
action_col1, action_col2 = st.columns([3, 1])

with action_col1:
    # Filter selection
    status_options = ["All", "Matched", "Unsettled", "Double-Settled", "Refund"]
    selected_status = st.segmented_control(
        "Filter by Status",
        options=status_options,
        default="All",
    ) if hasattr(st, "segmented_control") else st.radio("Filter by Status", status_options, horizontal=True)

with action_col2:
    # Export CSV button
    csv_buffer = io.StringIO()
    reconciled_df.to_csv(csv_buffer, index=False)
    csv_bytes = csv_buffer.getvalue().encode("utf-8")
    
    st.download_button(
        label="📥 Export Reconciled Report (CSV)",
        data=csv_bytes,
        file_name=f"upi_reconciliation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
        use_container_width=True,
    )

# Filter dataframe based on user choice
filtered_df = reconciled_df if selected_status == "All" else reconciled_df[reconciled_df["status"] == selected_status]

# ---------------- TABS VIEW ----------------
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Reconciled Records",
    "⚠️ Discrepancy Queue",
    "🔍 UTR Normalization Audit",
    "🏢 Merchant Summary",
])

# Format helper for display
def format_display_table(df_to_show: pd.DataFrame) -> pd.DataFrame:
    df_display = df_to_show.copy()
    if "merchant_amount" in df_display.columns:
        df_display["merchant_amount"] = df_display["merchant_amount"].map(lambda x: f"₹{x:,.2f}")
    if "npci_amount" in df_display.columns:
        df_display["npci_amount"] = df_display["npci_amount"].map(lambda x: f"₹{x:,.2f}")
    if "amount_diff" in df_display.columns:
        df_display["amount_diff"] = df_display["amount_diff"].map(lambda x: f"₹{x:,.2f}")
    return df_display


with tab1:
    st.markdown(f"### Showing **{len(filtered_df)}** records for status: `{selected_status}`")
    
    display_cols = [
        "order_id",
        "merchant_id",
        "normalized_utr",
        "merchant_amount",
        "npci_amount",
        "transaction_date",
        "settlement_date",
        "status",
        "remarks",
    ]
    
    st.dataframe(
        format_display_table(filtered_df[display_cols]),
        use_container_width=True,
        hide_index=True,
    )

with tab2:
    st.markdown("### Discrepancy Analysis & Action Required")
    discrepancy_df = reconciled_df[reconciled_df["status"] != "Matched"]
    
    if discrepancy_df.empty:
        st.success("🎉 No discrepancies found! All transactions match perfectly.")
    else:
        st.warning(
            f"Found **{len(discrepancy_df)} flagged items** requiring aggregator intervention "
            f"({metrics['unsettled_count']} Unsettled, {metrics['double_settled_count']} Double-Settled, {metrics['refund_count']} Refund)."
        )

        disc_cols = [
            "order_id",
            "merchant_id",
            "normalized_utr",
            "merchant_amount",
            "npci_amount",
            "status",
            "npci_settlement_id",
            "remarks",
        ]

        st.dataframe(
            format_display_table(discrepancy_df[disc_cols]),
            use_container_width=True,
            hide_index=True,
        )

        st.markdown("#### Recommended Operational Actions:")
        col_act1, col_act2, col_act3 = st.columns(3)
        with col_act1:
            st.error("**Unsettled Transactions**")
            st.caption("Transactions missing from NPCI file. Trigger automatic inquiry to Sponsor Bank and hold merchant payout if pending verification.")
        with col_act2:
            st.warning("**Double-Settled Transactions**")
            st.caption("Duplicate settlements received. Auto-freeze duplicate credits and raise clawback / reversal request with NPCI.")
        with col_act3:
            st.info("**Refund Transactions**")
            st.caption("Negative settlements mapped to original orders. Adjust merchant nodal account balance and issue refund receipts.")

with tab3:
    st.markdown("### UTR Regex Cleaning & Format Difference Audit")
    st.caption("Demonstrating extraction of standard 12-digit UTRs despite prefixes, special characters, and formatting differences.")
    
    audit_cols = [
        "order_id",
        "raw_merchant_utr",
        "raw_npci_utr",
        "normalized_utr",
        "status",
    ]
    
    st.dataframe(
        reconciled_df[audit_cols],
        use_container_width=True,
        hide_index=True,
    )

with tab4:
    st.markdown("### Merchant-Level Reconciliation Breakdown")
    merchant_summary = reconciled_df.groupby("merchant_id").agg(
        total_txns=("order_id", "count"),
        total_volume=("merchant_amount", "sum"),
        matched=("status", lambda s: (s == "Matched").sum()),
        unsettled=("status", lambda s: (s == "Unsettled").sum()),
        double_settled=("status", lambda s: (s == "Double-Settled").sum()),
        refunds=("status", lambda s: (s == "Refund").sum()),
    ).reset_index()

    merchant_summary["match_rate"] = (
        (merchant_summary["matched"] / merchant_summary["total_txns"]) * 100
    ).round(1).astype(str) + "%"

    merchant_summary["total_volume"] = merchant_summary["total_volume"].map(lambda x: f"₹{x:,.2f}")

    st.dataframe(
        merchant_summary,
        use_container_width=True,
        hide_index=True,
    )

# Footer
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #94a3b8; font-size: 0.85rem;'>"
    "UPI Transaction Reconciliation Engine • Compliant with NPCI Procedural Guidelines • Built for Payment Aggregators"
    "</div>",
    unsafe_allow_html=True,
)
