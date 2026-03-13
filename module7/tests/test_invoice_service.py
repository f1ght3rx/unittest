import unittest
from unittest.mock import Mock, create_autospec
from invoice_service import InvoiceService, Invoice, ChargeResult


class TestInvoiceService(unittest.TestCase):
    def setUp(self):
        self.invoice_repo = Mock()
        self.payment_gateway = Mock()
        self.service = InvoiceService(self.invoice_repo, self.payment_gateway)

    def test_pay_success(self):
        invoice = Invoice(id=1, customer_id="cust_1", amount=100, status="pending")
        self.invoice_repo.get_by_id.return_value = invoice
        self.payment_gateway.charge.return_value = ChargeResult(ok=True, transaction_id="txn_123")

        result = self.service.pay(1)

        self.assertEqual(result, "paid")
        self.invoice_repo.get_by_id.assert_called_once_with(1)
        self.payment_gateway.charge.assert_called_once_with("cust_1", 100)
        self.invoice_repo.mark_paid.assert_called_once_with(1, "txn_123")
        self.invoice_repo.mark_failed.assert_not_called()
        self.invoice_repo.mark_retry.assert_not_called()

    def test_pay_failed(self):
        invoice = Invoice(id=2, customer_id="cust_2", amount=200, status="pending")
        self.invoice_repo.get_by_id.return_value = invoice
        self.payment_gateway.charge.return_value = ChargeResult(ok=False, reason="insufficient funds")

        result = self.service.pay(2)

        self.assertEqual(result, "failed")
        self.payment_gateway.charge.assert_called_once_with("cust_2", 200)
        self.invoice_repo.mark_failed.assert_called_once_with(2, "insufficient funds")
        self.invoice_repo.mark_paid.assert_not_called()
        self.invoice_repo.mark_retry.assert_not_called()

    def test_pay_already_paid(self):
        invoice = Invoice(id=3, customer_id="cust_3", amount=300, status="paid")
        self.invoice_repo.get_by_id.return_value = invoice

        result = self.service.pay(3)

        self.assertEqual(result, "already_paid")
        self.payment_gateway.charge.assert_not_called()
        self.invoice_repo.mark_paid.assert_not_called()
        self.invoice_repo.mark_failed.assert_not_called()
        self.invoice_repo.mark_retry.assert_not_called()

    def test_pay_invoice_not_found(self):
        self.invoice_repo.get_by_id.return_value = None

        with self.assertRaises(LookupError) as context:
            self.service.pay(999)
        self.assertEqual(str(context.exception), "invoice not found")

        self.payment_gateway.charge.assert_not_called()
        self.invoice_repo.mark_paid.assert_not_called()
        self.invoice_repo.mark_failed.assert_not_called()
        self.invoice_repo.mark_retry.assert_not_called()

    def test_pay_amount_not_positive(self):
        invoice = Invoice(id=4, customer_id="cust_4", amount=0, status="pending")
        self.invoice_repo.get_by_id.return_value = invoice

        with self.assertRaises(ValueError) as context:
            self.service.pay(4)
        self.assertEqual(str(context.exception), "amount must be positive")

        self.payment_gateway.charge.assert_not_called()
        self.invoice_repo.mark_paid.assert_not_called()
        self.invoice_repo.mark_failed.assert_not_called()
        self.invoice_repo.mark_retry.assert_not_called()

    def test_pay_timeout(self):
        invoice = Invoice(id=5, customer_id="cust_5", amount=500, status="pending")
        self.invoice_repo.get_by_id.return_value = invoice
        self.payment_gateway.charge.side_effect = TimeoutError("gateway timeout")

        result = self.service.pay(5)

        self.assertEqual(result, "retry")
        self.payment_gateway.charge.assert_called_once_with("cust_5", 500)
        self.invoice_repo.mark_retry.assert_called_once_with(5)
        self.invoice_repo.mark_paid.assert_not_called()
        self.invoice_repo.mark_failed.assert_not_called()


if __name__ == "__main__":
    unittest.main()