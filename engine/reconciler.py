"""Reconciliation engine for matching UPI merchant logs against NPCI settlements."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import pandas as pd

from engine.normalizer import (
    normalize_merchant_dataframe,
    normalize_npci_dataframe,
)


def reconcile_transactions(
    merchant_df: pd.DataFrame,
    npci_df: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Reconcile merchant transactions against NPCI settlement records.

    Assigns one of 4 required statuses to each merchant transaction:
    - 'Matched': UTR and amount match across both files.
    - 'Unsettled': Present in merchant log but absent in NPCI file.
    - 'Double-Settled': Appears more than once in NPCI file for a single UTR.
    - 'Refund': Negative settlement entry matched back to original merchant order.

    Returns:
        Tuple[pd.DataFrame, pd.DataFrame]:
            1. reconciled_df: Results mapped per merchant transaction.
            2. unmatched_npci_df: Any orphan NPCI settlements not found in merchant logs.
    """
    # 1. Normalize dataframes
    norm_merchant = normalize_merchant_dataframe(merchant_df)
    norm_npci = normalize_npci_dataframe(npci_df)

    # 2. Group NPCI records by normalized_utr
    npci_by_utr: Dict[str, List[Dict[str, Any]]] = {}
    for _, row in norm_npci.iterrows():
        utr = row["normalized_utr"]
        if not utr:
            continue
        if utr not in npci_by_utr:
            npci_by_utr[utr] = []
        npci_by_utr[utr].append(row.to_dict())

    # 3. Process each merchant transaction
    reconciled_rows: List[Dict[str, Any]] = []
    used_npci_utrs = set()

    for _, m_row in norm_merchant.iterrows():
        m_utr = m_row.get("normalized_utr")
        m_amt = float(m_row.get("normalized_amount", 0.0))
        m_order_id = m_row.get("order_id", "")
        m_mid = m_row.get("merchant_id", "")
        m_date = m_row.get("normalized_date", "")
        raw_m_utr = m_row.get("raw_utr", "")

        npci_entries = npci_by_utr.get(m_utr, []) if m_utr else []
        if m_utr:
            used_npci_utrs.add(m_utr)

        npci_count = len(npci_entries)
        settlement_ids = ", ".join([str(e.get("settlement_id", "")) for e in npci_entries])
        raw_npci_utrs = ", ".join([str(e.get("raw_utr", "")) for e in npci_entries])
        npci_dates = ", ".join(sorted(list({str(e.get("normalized_date", "")) for e in npci_entries if e.get("normalized_date")})))

        # Evaluate discrepancy status
        if npci_count == 0:
            # Present in merchant log but absent in NPCI file
            status = "Unsettled"
            npci_amt = 0.0
            remarks = "Present in merchant log but absent in NPCI settlement file (Unsettled)."

        else:
            negative_entries = [e for e in npci_entries if float(e.get("normalized_amount", 0.0)) < 0]
            positive_entries = [e for e in npci_entries if float(e.get("normalized_amount", 0.0)) >= 0]

            if negative_entries:
                # Negative settlement entry matched back to original merchant order
                status = "Refund"
                # If negative entry exists, record the refund amount
                refund_amt = sum(float(e.get("normalized_amount", 0.0)) for e in negative_entries)
                npci_amt = refund_amt
                remarks = f"Negative settlement entry ({refund_amt:,.2f}) matched back to original merchant order."

            elif len(positive_entries) > 1:
                # Appears more than once in NPCI file for a single UTR
                status = "Double-Settled"
                npci_amt = sum(float(e.get("normalized_amount", 0.0)) for e in positive_entries)
                remarks = f"Duplicate records found in NPCI ({len(positive_entries)} entries totaling ₹{npci_amt:,.2f})."

            else:
                # Single positive settlement record
                single_entry = positive_entries[0]
                single_amt = float(single_entry.get("normalized_amount", 0.0))
                npci_amt = single_amt

                if abs(single_amt - m_amt) < 0.01:
                    status = "Matched"
                    remarks = "UTR and amount match across merchant log and NPCI settlement (T+1)."
                else:
                    # Amount discrepancy with single NPCI record
                    status = "Unsettled"
                    remarks = f"Amount mismatch: Merchant expected ₹{m_amt:,.2f} but NPCI settled ₹{single_amt:,.2f}."

        reconciled_rows.append(
            {
                "order_id": m_order_id,
                "merchant_id": m_mid,
                "raw_merchant_utr": raw_m_utr,
                "normalized_utr": m_utr or "N/A",
                "merchant_amount": m_amt,
                "npci_amount": npci_amt,
                "amount_diff": round(npci_amt - m_amt, 2),
                "transaction_date": m_date,
                "settlement_date": npci_dates or "N/A",
                "npci_settlement_id": settlement_ids or "N/A",
                "npci_record_count": npci_count,
                "raw_npci_utr": raw_npci_utrs or "N/A",
                "status": status,
                "remarks": remarks,
            }
        )

    reconciled_df = pd.DataFrame(reconciled_rows)

    # 4. Check for orphan NPCI settlements (settlements with no merchant order)
    unmatched_npci_rows: List[Dict[str, Any]] = []
    for utr, entries in npci_by_utr.items():
        if utr not in used_npci_utrs:
            for entry in entries:
                unmatched_npci_rows.append(
                    {
                        "settlement_id": entry.get("settlement_id"),
                        "raw_utr": entry.get("raw_utr"),
                        "normalized_utr": utr,
                        "amount": entry.get("normalized_amount"),
                        "settlement_date": entry.get("normalized_date"),
                        "type": entry.get("type"),
                        "remarks": "Settlement present in NPCI file but missing in Merchant logs.",
                    }
                )

    unmatched_npci_df = pd.DataFrame(unmatched_npci_rows)

    return reconciled_df, unmatched_npci_df


def get_summary_metrics(reconciled_df: pd.DataFrame) -> Dict[str, Any]:
    """Calculate key summary metrics for dashboard display.

    Metrics:
    - Total Transactions
    - Matched Count
    - Unsettled Count
    - Double-Settled Count
    - Total Refund Amount
    """
    if reconciled_df.empty:
        return {
            "total_transactions": 0,
            "matched_count": 0,
            "unsettled_count": 0,
            "double_settled_count": 0,
            "refund_count": 0,
            "total_refund_amount": 0.0,
            "total_merchant_volume": 0.0,
            "total_settled_volume": 0.0,
            "match_rate": 0.0,
        }

    total_txns = len(reconciled_df)
    matched_count = int((reconciled_df["status"] == "Matched").sum())
    unsettled_count = int((reconciled_df["status"] == "Unsettled").sum())
    double_settled_count = int((reconciled_df["status"] == "Double-Settled").sum())
    refund_rows = reconciled_df[reconciled_df["status"] == "Refund"]
    refund_count = int(len(refund_rows))

    # Total refund amount as absolute sum
    total_refund_amount = float(refund_rows["merchant_amount"].sum())

    total_merchant_volume = float(reconciled_df["merchant_amount"].sum())
    total_settled_volume = float(reconciled_df[reconciled_df["status"] == "Matched"]["npci_amount"].sum())
    match_rate = round((matched_count / total_txns) * 100, 1) if total_txns > 0 else 0.0

    return {
        "total_transactions": total_txns,
        "matched_count": matched_count,
        "unsettled_count": unsettled_count,
        "double_settled_count": double_settled_count,
        "refund_count": refund_count,
        "total_refund_amount": total_refund_amount,
        "total_merchant_volume": total_merchant_volume,
        "total_settled_volume": total_settled_volume,
        "match_rate": match_rate,
    }
