"""Data normalization module for UPI transaction reconciliation.

Handles UTR string cleaning, amount normalization, and date standardization.
"""

from __future__ import annotations

import re
from typing import Any, Optional
import pandas as pd


def normalize_utr(val: Any) -> Optional[str]:
    """Clean and extract a standard 12-digit UPI UTR (Unique Transaction Reference).

    Handles formats such as:
    - Standard 12-digit: '987654321012'
    - Prefixed/Suffixed: 'UTR-987654321012', 'utr: 987654321012', 'UPI/987654321012/PAY'
    - Spaces or hyphens: '9876 5432 1012', '9876-5432-1012'
    - Floats or scientific notation: 987654321012.0, 9.87654321012e+11
    """
    if val is None or pd.isna(val):
        return None

    # Handle numeric float/int representations
    if isinstance(val, (int, float)):
        try:
            val_int = int(val)
            s_val = str(val_int)
            if len(s_val) == 12:
                return s_val
        except (ValueError, OverflowError):
            pass

    s = str(val).strip()
    if not s or s.lower() in ("nan", "none", "null"):
        return None

    # First check: consecutive 12 digits anywhere in string
    match = re.search(r"(\d{12})", s)
    if match:
        return match.group(1)

    # Second check: strip all non-digit characters and check if exactly 12 digits remain
    digits_only = re.sub(r"\D", "", s)
    if len(digits_only) == 12:
        return digits_only

    # If scientific notation in string format e.g. '9.87654321012E+11'
    try:
        f_val = float(s)
        i_val = int(f_val)
        if len(str(i_val)) == 12:
            return str(i_val)
    except (ValueError, OverflowError):
        pass

    return digits_only if digits_only else s


def normalize_amount(val: Any) -> float:
    """Normalize amount value into a standard float.

    Handles currency symbols (₹, INR, Rs), commas, and negative signs:
    - '₹ 1,500.50' -> 1500.50
    - '-750.00' -> -750.00
    - '(850.00)' -> -850.00
    - 'INR 2500' -> 2500.00
    """
    if val is None or pd.isna(val):
        return 0.0

    if isinstance(val, (int, float)):
        return round(float(val), 2)

    s = str(val).strip()
    if not s or s.lower() in ("nan", "none", "null"):
        return 0.0

    is_negative = False
    # Check accounting parentheses e.g. (500.00)
    if s.startswith("(") and s.endswith(")"):
        is_negative = True
        s = s[1:-1].strip()

    # Clean currency labels and symbols
    s = re.sub(r"(?i)(inr|rs\.?|₹|\$)", "", s)
    s = s.replace(",", "").strip()

    if s.startswith("-"):
        is_negative = True
        s = s[1:].strip()
    elif s.endswith("-"):
        is_negative = True
        s = s[:-1].strip()

    try:
        amt = float(s)
        if is_negative and amt > 0:
            amt = -amt
        return round(amt, 2)
    except ValueError:
        return 0.0


def normalize_date(val: Any) -> Optional[str]:
    """Standardize dates into 'YYYY-MM-DD' ISO format.

    Parses various date and datetime formats.
    """
    if val is None or pd.isna(val):
        return None

    try:
        dt = pd.to_datetime(val, errors="coerce")
        if pd.isna(dt):
            return str(val).strip()
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return str(val).strip()


def normalize_merchant_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Standardize column names and normalize fields in the merchant log DataFrame."""
    df_clean = df.copy()

    # Column name mapping (case-insensitive)
    col_map = {}
    for col in df_clean.columns:
        c_lower = col.strip().lower().replace(" ", "_")
        if c_lower in ("order_id", "merchant_txn_id", "transaction_id", "txn_id"):
            col_map[col] = "order_id"
        elif c_lower in ("merchant_id", "mid", "merchant"):
            col_map[col] = "merchant_id"
        elif c_lower in ("utr", "rrn", "upi_ref", "upi_rrn", "bank_ref"):
            col_map[col] = "utr"
        elif c_lower in ("amount", "order_amount", "txn_amount", "transaction_amount"):
            col_map[col] = "amount"
        elif c_lower in ("transaction_date", "timestamp", "date", "txn_time", "transaction_time", "created_at"):
            col_map[col] = "transaction_date"
        elif c_lower in ("status", "txn_status", "payment_status"):
            col_map[col] = "status"

    df_clean.rename(columns=col_map, inplace=True)

    # Ensure required columns exist with defaults if missing
    if "order_id" not in df_clean.columns:
        df_clean["order_id"] = [f"ORD_{i+1001}" for i in range(len(df_clean))]
    if "merchant_id" not in df_clean.columns:
        df_clean["merchant_id"] = "MID_DEFAULT"
    if "status" not in df_clean.columns:
        df_clean["status"] = "SUCCESS"

    # Store raw and normalized fields
    df_clean["raw_utr"] = df_clean["utr"].astype(str) if "utr" in df_clean.columns else ""
    df_clean["normalized_utr"] = df_clean["raw_utr"].apply(normalize_utr)
    df_clean["normalized_amount"] = df_clean["amount"].apply(normalize_amount) if "amount" in df_clean.columns else 0.0
    
    if "transaction_date" in df_clean.columns:
        df_clean["normalized_date"] = df_clean["transaction_date"].apply(normalize_date)
    else:
        df_clean["normalized_date"] = None

    return df_clean


def normalize_npci_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Standardize column names and normalize fields in the NPCI settlement DataFrame."""
    df_clean = df.copy()

    col_map = {}
    for col in df_clean.columns:
        c_lower = col.strip().lower().replace(" ", "_")
        if c_lower in ("settlement_id", "npci_txn_id", "npci_ref", "record_id"):
            col_map[col] = "settlement_id"
        elif c_lower in ("utr", "rrn", "upi_rrn", "bank_ref"):
            col_map[col] = "utr"
        elif c_lower in ("amount", "settled_amount", "settlement_amount", "net_amount"):
            col_map[col] = "amount"
        elif c_lower in ("settlement_date", "date", "settle_date", "value_date"):
            col_map[col] = "settlement_date"
        elif c_lower in ("type", "status", "txn_type", "action", "response_code"):
            col_map[col] = "type"

    df_clean.rename(columns=col_map, inplace=True)

    if "settlement_id" not in df_clean.columns:
        df_clean["settlement_id"] = [f"SETTL_{i+5001}" for i in range(len(df_clean))]
    if "type" not in df_clean.columns:
        df_clean["type"] = "SETTLED"

    df_clean["raw_utr"] = df_clean["utr"].astype(str) if "utr" in df_clean.columns else ""
    df_clean["normalized_utr"] = df_clean["raw_utr"].apply(normalize_utr)
    df_clean["normalized_amount"] = df_clean["amount"].apply(normalize_amount) if "amount" in df_clean.columns else 0.0

    if "settlement_date" in df_clean.columns:
        df_clean["normalized_date"] = df_clean["settlement_date"].apply(normalize_date)
    else:
        df_clean["normalized_date"] = None

    return df_clean
