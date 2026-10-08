"""Unit tests for UPI Transaction Reconciliation Engine."""

import unittest
import pandas as pd
from engine.normalizer import (
    normalize_amount,
    normalize_date,
    normalize_utr,
    normalize_merchant_dataframe,
    normalize_npci_dataframe,
)
from engine.reconciler import (
    reconcile_transactions,
    get_summary_metrics,
)


class TestNormalizer(unittest.TestCase):
    def test_normalize_utr_formats(self):
        # Standard 12-digit
        self.assertEqual(normalize_utr("424510012301"), "424510012301")
        # Prefix UTR-
        self.assertEqual(normalize_utr("UTR-424510012303"), "424510012303")
        # Prefix utr:
        self.assertEqual(normalize_utr("utr:424510012304"), "424510012304")
        # Path format
        self.assertEqual(normalize_utr("UPI/424510012305/PAY"), "424510012305")
        # Whitespace
        self.assertEqual(normalize_utr("  424510012306  "), "424510012306")
        # Hyphens
        self.assertEqual(normalize_utr("4245-1001-2308"), "424510012308")
        # Numeric / Float representation
        self.assertEqual(normalize_utr(424510012301), "424510012301")
        # Null / None
        self.assertIsNone(normalize_utr(None))
        self.assertIsNone(normalize_utr(""))
        self.assertIsNone(normalize_utr("nan"))

    def test_normalize_amount(self):
        self.assertEqual(normalize_amount(1500.5), 1500.50)
        self.assertEqual(normalize_amount("₹ 2,450.00"), 2450.00)
        self.assertEqual(normalize_amount("-₹850.00"), -850.00)
        self.assertEqual(normalize_amount("(500.00)"), -500.00)
        self.assertEqual(normalize_amount("INR 1200"), 1200.00)
        self.assertEqual(normalize_amount(None), 0.0)

    def test_normalize_date(self):
        self.assertEqual(normalize_date("2024-09-01 10:15:30"), "2024-09-01")
        self.assertEqual(normalize_date("2024-09-02"), "2024-09-02")
        self.assertIsNone(normalize_date(None))


class TestReconciliationEngine(unittest.TestCase):
    def setUp(self):
        self.merchant_df = pd.read_csv("data/merchant_logs.csv")
        self.npci_df = pd.read_csv("data/npci_settlements.csv")

    def test_reconciliation_categories(self):
        recon_df, unmatched = reconcile_transactions(self.merchant_df, self.npci_df)
        self.assertEqual(len(recon_df), 20)

        # Matched count check
        matched = recon_df[recon_df["status"] == "Matched"]
        self.assertEqual(len(matched), 12)

        # Unsettled count check
        unsettled = recon_df[recon_df["status"] == "Unsettled"]
        self.assertEqual(len(unsettled), 3)
        self.assertSetEqual(set(unsettled["order_id"]), {"ORD_1013", "ORD_1014", "ORD_1015"})

        # Double-Settled count check
        double_settled = recon_df[recon_df["status"] == "Double-Settled"]
        self.assertEqual(len(double_settled), 2)
        self.assertSetEqual(set(double_settled["order_id"]), {"ORD_1016", "ORD_1017"})

        # Refund count check
        refunds = recon_df[recon_df["status"] == "Refund"]
        self.assertEqual(len(refunds), 3)
        self.assertSetEqual(set(refunds["order_id"]), {"ORD_1018", "ORD_1019", "ORD_1020"})

    def test_summary_metrics(self):
        recon_df, _ = reconcile_transactions(self.merchant_df, self.npci_df)
        metrics = get_summary_metrics(recon_df)

        self.assertEqual(metrics["total_transactions"], 20)
        self.assertEqual(metrics["matched_count"], 12)
        self.assertEqual(metrics["unsettled_count"], 3)
        self.assertEqual(metrics["double_settled_count"], 2)
        self.assertEqual(metrics["refund_count"], 3)
        self.assertEqual(metrics["total_refund_amount"], 850.00 + 1500.00 + 499.00)
        self.assertEqual(metrics["match_rate"], 60.0)


if __name__ == "__main__":
    unittest.main()
