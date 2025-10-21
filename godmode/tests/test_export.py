"""
Tests for the data export functionality.
"""

import csv
import io
import json
from unittest.mock import MagicMock, patch

from django.http import HttpResponse
from django.test import TestCase
from django.utils import timezone

from accounts.models import CustomUser as User
from godmode.export_utils import DataExporter
from godmode.models import DataExport, DataExportConfig
from payment.models import Payment


class DataExporterTestCase(TestCase):
    """Test case for data exporter."""

    def setUp(self):
        """Set up test data."""
        # Create test user
        self.user = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="adminpassword",
        )

        # Create test payments
        self.payment1 = Payment.objects.create(
            payer=self.user,
            original_amount=100.00,
            service_fee=10.00,
            final_amount=90.00,
            pay_code="test-payment-123",
            payment_method="paystack",
            status="Completed",
        )

        self.payment2 = Payment.objects.create(
            payer=self.user,
            original_amount=200.00,
            service_fee=20.00,
            final_amount=180.00,
            pay_code="test-payment-456",
            payment_method="flutterwave",
            status="Pending",
        )

        # Create test export config
        self.export_config = DataExportConfig.objects.create(
            name="Test Export",
            description="Test export configuration",
            model_name="payment.Payment",
            fields=["id", "pay_code", "original_amount", "status", "created_at"],
            filters={},
            created_by=self.user,
        )

    def test_data_exporter_init(self):
        """Test data exporter initialization."""
        # Test with config ID
        exporter = DataExporter(config_id=self.export_config.id)
        self.assertEqual(exporter.config, self.export_config)
        self.assertEqual(exporter.model, Payment)
        self.assertEqual(len(exporter.fields), 5)
        self.assertEqual(exporter.export_format, "xlsx")

        # Test with config object
        exporter = DataExporter(config=self.export_config)
        self.assertEqual(exporter.config, self.export_config)
        self.assertEqual(exporter.model, Payment)
        self.assertEqual(len(exporter.fields), 5)
        self.assertEqual(exporter.export_format, "xlsx")

        # Test with invalid config ID
        with self.assertRaises(ValueError):
            DataExporter(config_id=999)

    def test_set_fields(self):
        """Test setting fields."""
        exporter = DataExporter(config=self.export_config)

        # Test setting valid fields
        exporter.set_fields(["id", "pay_code", "status"])
        self.assertEqual(len(exporter.fields), 3)
        self.assertIn("id", exporter.fields)
        self.assertIn("pay_code", exporter.fields)
        self.assertIn("status", exporter.fields)

        # Test setting invalid fields
        exporter.set_fields(["id", "invalid_field"])
        self.assertEqual(len(exporter.fields), 1)
        self.assertIn("id", exporter.fields)
        self.assertNotIn("invalid_field", exporter.fields)

    def test_set_filters(self):
        """Test setting filters."""
        exporter = DataExporter(config=self.export_config)

        # Test setting filters
        filters = {"status": "Completed"}
        exporter.set_filters(filters)
        self.assertEqual(exporter.filters, filters)

        # Test setting None filters
        exporter.set_filters(None)
        self.assertEqual(exporter.filters, {})

    def test_set_order_by(self):
        """Test setting order by."""
        exporter = DataExporter(config=self.export_config)

        # Test setting order by
        order_by = ["created_at", "-id"]
        exporter.set_order_by(order_by)
        self.assertEqual(exporter.order_by, order_by)

        # Test setting None order by
        exporter.set_order_by(None)
        self.assertEqual(exporter.order_by, [])

    def test_set_export_format(self):
        """Test setting export format."""
        exporter = DataExporter(config=self.export_config)

        # Test setting valid format
        exporter.set_export_format("csv")
        self.assertEqual(exporter.export_format, "csv")

        # Test setting invalid format
        with self.assertRaises(ValueError):
            exporter.set_export_format("invalid")

    def test_set_file_name(self):
        """Test setting file name."""
        exporter = DataExporter(config=self.export_config)

        # Test setting file name
        exporter.set_file_name("test_export")
        self.assertEqual(exporter.file_name, "test_export")

    def test_set_user(self):
        """Test setting user."""
        exporter = DataExporter(config=self.export_config)

        # Test setting user
        exporter.set_user(self.user)
        self.assertEqual(exporter.user, self.user)

    def test_apply_filters(self):
        """Test applying filters."""
        exporter = DataExporter(config=self.export_config)

        # Test with no filters
        exporter.apply_filters()
        self.assertEqual(exporter.queryset.count(), 2)

        # Test with status filter
        exporter.set_filters({"status": "Completed"})
        exporter.apply_filters()
        self.assertEqual(exporter.queryset.count(), 1)
        self.assertEqual(exporter.queryset.first().pay_code, "test-payment-123")

        # Test with search filter
        exporter.set_filters({
            "search": "456",
            "search_fields": ["pay_code"],
        })
        exporter.apply_filters()
        self.assertEqual(exporter.queryset.count(), 1)
        self.assertEqual(exporter.queryset.first().pay_code, "test-payment-456")

        # Test with date range filter
        today = timezone.now().date()
        exporter.set_filters({
            "date_range": {
                "start": today.strftime("%Y-%m-%d"),
                "end": today.strftime("%Y-%m-%d"),
            },
            "date_field": "created_at",
        })
        exporter.apply_filters()
        self.assertEqual(exporter.queryset.count(), 2)

    def test_apply_ordering(self):
        """Test applying ordering."""
        exporter = DataExporter(config=self.export_config)

        # Test with no ordering
        exporter.apply_ordering()
        self.assertEqual(exporter.queryset.count(), 2)

        # Test with ordering by original_amount
        exporter.set_order_by(["original_amount"])
        exporter.apply_ordering()
        self.assertEqual(exporter.queryset.count(), 2)
        self.assertEqual(exporter.queryset.first().pay_code, "test-payment-123")

        # Test with ordering by -original_amount
        exporter.set_order_by(["-original_amount"])
        exporter.apply_ordering()
        self.assertEqual(exporter.queryset.count(), 2)
        self.assertEqual(exporter.queryset.first().pay_code, "test-payment-456")

    def test_get_data(self):
        """Test getting data."""
        exporter = DataExporter(config=self.export_config)

        # Test getting all data
        data = exporter.get_data()
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["pay_code"], "test-payment-123")
        self.assertEqual(data[1]["pay_code"], "test-payment-456")

        # Test getting filtered data
        exporter.set_filters({"status": "Completed"})
        data = exporter.get_data()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["pay_code"], "test-payment-123")

        # Test getting ordered data
        exporter.set_filters({})
        exporter.set_order_by(["-original_amount"])
        data = exporter.get_data()
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["pay_code"], "test-payment-456")
        self.assertEqual(data[1]["pay_code"], "test-payment-123")

    def test_export_csv(self):
        """Test exporting as CSV."""
        exporter = DataExporter(config=self.export_config)
        exporter.set_file_name("test_export")

        # Test export
        response = exporter.export_csv()
        self.assertIsInstance(response, HttpResponse)
        self.assertEqual(response["Content-Type"], "text/csv")
        self.assertEqual(
            response["Content-Disposition"],
            'attachment; filename="test_export.csv"',
        )

        # Parse CSV content
        content = response.content.decode("utf-8")
        reader = csv.reader(io.StringIO(content))
        rows = list(reader)

        # Verify header row
        self.assertEqual(len(rows), 3)  # Header + 2 data rows
        self.assertEqual(len(rows[0]), 5)  # 5 columns
        self.assertIn("pay_code", rows[0])
        self.assertIn("original_amount", rows[0])
        self.assertIn("status", rows[0])

        # Verify data rows
        self.assertIn("test-payment-123", rows[1])
        self.assertIn("test-payment-456", rows[2])

    def test_export_json(self):
        """Test exporting as JSON."""
        exporter = DataExporter(config=self.export_config)
        exporter.set_file_name("test_export")

        # Test export
        response = exporter.export_json()
        self.assertIsInstance(response, HttpResponse)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertEqual(
            response["Content-Disposition"],
            'attachment; filename="test_export.json"',
        )

        # Parse JSON content
        content = response.content.decode("utf-8")
        data = json.loads(content)

        # Verify data
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["pay_code"], "test-payment-123")
        self.assertEqual(data[1]["pay_code"], "test-payment-456")

    def test_get_file_name(self):
        """Test getting file name."""
        exporter = DataExporter(config=self.export_config)

        # Test with no file name set
        file_name = exporter.get_file_name()
        self.assertIn("Payment_", file_name)

        # Test with file name set
        exporter.set_file_name("test_export")
        file_name = exporter.get_file_name()
        self.assertEqual(file_name, "test_export")

    def test_create_export_record(self):
        """Test creating export record."""
        exporter = DataExporter(config=self.export_config)
        exporter.set_file_name("test_export")
        exporter.set_user(self.user)

        # Test creating export record
        export = exporter.create_export_record()
        self.assertIsInstance(export, DataExport)
        self.assertEqual(export.config, self.export_config)
        self.assertEqual(export.file_name, "test_export.xlsx")
        self.assertEqual(export.status, "processing")
        self.assertEqual(export.created_by, self.user)

        # Test with no config
        exporter.config = None
        export = exporter.create_export_record()
        self.assertIsNone(export)

        # Test with no user
        exporter.config = self.export_config
        exporter.user = None
        export = exporter.create_export_record()
        self.assertIsNone(export)

    def test_update_export_record(self):
        """Test updating export record."""
        exporter = DataExporter(config=self.export_config)
        exporter.set_file_name("test_export")
        exporter.set_user(self.user)

        # Create export record
        export = exporter.create_export_record()

        # Test updating export record
        exporter.update_export_record(export, 10, "completed")
        self.assertEqual(export.row_count, 10)
        self.assertEqual(export.status, "completed")
        self.assertIsNotNone(export.completed_at)

        # Test updating with error
        exporter.update_export_record(export, 0, "failed", "Test error")
        self.assertEqual(export.row_count, 0)
        self.assertEqual(export.status, "failed")
        self.assertEqual(export.error_message, "Test error")

        # Test with no export
        result = exporter.update_export_record(None, 10)
        self.assertIsNone(result)

    @patch("godmode.export_utils.DataExporter.export_xlsx")
    def test_export(self, mock_export_xlsx):
        """Test export method."""
        exporter = DataExporter(config=self.export_config)
        exporter.set_file_name("test_export")
        exporter.set_user(self.user)

        # Mock export_xlsx
        mock_response = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        mock_response["Content-Disposition"] = 'attachment; filename="test_export.xlsx"'
        mock_export_xlsx.return_value = mock_response

        # Test export
        response = exporter.export()
        self.assertEqual(response, mock_response)
        mock_export_xlsx.assert_called_once()

        # Test with different format
        exporter.set_export_format("csv")
        with patch("godmode.export_utils.DataExporter.export_csv") as mock_export_csv:
            mock_export_csv.return_value = HttpResponse(content_type="text/csv")
            exporter.export()
            mock_export_csv.assert_called_once()

        # Test with exception
        mock_export_xlsx.side_effect = Exception("Test exception")
        exporter.set_export_format("xlsx")
        with self.assertRaises(Exception):
            exporter.export()


class ExportAPITestCase(TestCase):
    """Test case for export API endpoints."""

    def setUp(self):
        """Set up test data."""
        # Create test user
        self.user = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="adminpassword",
        )

        # Create test payments
        self.payment1 = Payment.objects.create(
            payer=self.user,
            original_amount=100.00,
            service_fee=10.00,
            final_amount=90.00,
            pay_code="test-payment-123",
            payment_method="paystack",
            status="Completed",
        )

        self.payment2 = Payment.objects.create(
            payer=self.user,
            original_amount=200.00,
            service_fee=20.00,
            final_amount=180.00,
            pay_code="test-payment-456",
            payment_method="flutterwave",
            status="Pending",
        )

        # Create test export config
        self.export_config = DataExportConfig.objects.create(
            name="Test Export",
            description="Test export configuration",
            model_name="payment.Payment",
            fields=["id", "pay_code", "original_amount", "status", "created_at"],
            filters={},
            created_by=self.user,
        )

        # Login
        self.client.login(username="admin", password="adminpassword")

    def test_list_export_configs(self):
        """Test listing export configurations."""
        from godmode.api import list_export_configs

        # Create request mock
        request = MagicMock()
        request.user = self.user

        # Test without filters
        configs = list_export_configs(request)
        self.assertEqual(len(configs), 1)
        self.assertEqual(configs[0]["name"], "Test Export")

        # Test with model_name filter
        configs = list_export_configs(request, model_name="payment.Payment")
        self.assertEqual(len(configs), 1)
        self.assertEqual(configs[0]["name"], "Test Export")

        # Test with non-matching model_name filter
        configs = list_export_configs(request, model_name="accounts.User")
        self.assertEqual(len(configs), 0)

        # Test with non-superuser
        regular_user = User.objects.create_user(
            username="regular",
            email="regular@example.com",
            password="regularpassword",
        )
        request.user = regular_user
        configs = list_export_configs(request)
        self.assertEqual(len(configs), 0)

    def test_create_export_config(self):
        """Test creating export configuration."""
        from godmode.api import create_export_config, ExportConfigSchema

        # Create request mock
        request = MagicMock()
        request.user = self.user

        # Test with valid data
        payload = ExportConfigSchema(
            name="New Export",
            description="New export configuration",
            model_name="payment.Payment",
            fields=["id", "pay_code", "status"],
        )
        response = create_export_config(request, payload)
        self.assertEqual(response["status"], "success")
        self.assertIn("config_id", response)

        # Verify config was created
        config = DataExportConfig.objects.get(name="New Export")
        self.assertEqual(config.description, "New export configuration")
        self.assertEqual(config.model_name, "payment.Payment")
        self.assertEqual(config.fields, ["id", "pay_code", "status"])
        self.assertEqual(config.created_by, self.user)

        # Test with invalid model
        payload = ExportConfigSchema(
            name="Invalid Model",
            model_name="invalid.Model",
            fields=["id"],
        )
        response = create_export_config(request, payload)
        self.assertEqual(response["status"], "error")
        self.assertIn("Invalid model", response["message"])

        # Test with invalid fields
        payload = ExportConfigSchema(
            name="Invalid Fields",
            model_name="payment.Payment",
            fields=["invalid_field"],
        )
        response = create_export_config(request, payload)
        self.assertEqual(response["status"], "error")
        self.assertEqual(response["message"], "No valid fields selected")

    @patch("godmode.api.DataExporter.export")
    def test_run_export(self, mock_export):
        """Test running an export."""
        from godmode.api import run_export, RunExportSchema

        # Create request mock
        request = MagicMock()
        request.user = self.user

        # Mock export
        mock_response = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        mock_response["Content-Disposition"] = 'attachment; filename="test_export.xlsx"'
        mock_export.return_value = mock_response

        # Test with valid data
        payload = RunExportSchema(
            config_id=self.export_config.id,
            export_format="xlsx",
        )
        response = run_export(request, payload)
        self.assertEqual(response, mock_response)
        mock_export.assert_called_once()

        # Test with non-existent config
        payload = RunExportSchema(
            config_id=999,
            export_format="xlsx",
        )
        response = run_export(request, payload)
        self.assertEqual(response["status"], "error")
        self.assertIn("not found", response["message"])

        # Test with unauthorized user
        regular_user = User.objects.create_user(
            username="regular",
            email="regular@example.com",
            password="regularpassword",
        )
        request.user = regular_user
        payload = RunExportSchema(
            config_id=self.export_config.id,
            export_format="xlsx",
        )
        response = run_export(request, payload)
        self.assertEqual(response["status"], "error")
        self.assertIn("permission", response["message"])

        # Test with exception
        request.user = self.user
        mock_export.side_effect = Exception("Test exception")
        response = run_export(request, payload)
        self.assertEqual(response["status"], "error")
        self.assertEqual(response["message"], "Test exception")

    def test_list_exportable_models(self):
        """Test listing exportable models."""
        from godmode.api import list_exportable_models

        # Create request mock
        request = MagicMock()
        request.user = self.user

        # Test listing models
        models = list_exportable_models(request)
        self.assertIsInstance(models, list)
        self.assertTrue(len(models) > 0)

        # Verify payment model is included
        payment_model = next(
            (m for m in models if m["name"] == "payment.payment"), None
        )
        self.assertIsNotNone(payment_model)
        self.assertEqual(payment_model["verbose_name"], "Payment")
        self.assertTrue(len(payment_model["fields"]) > 0)
