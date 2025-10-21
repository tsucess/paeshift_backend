"""
Data export utilities for God Mode.

This module provides utilities for exporting data in various formats with customizable
columns, filters, and sorting.
"""

import csv
import io
import json
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Union

import openpyxl
import xlsxwriter
from django.apps import apps
from django.conf import settings
from django.db.models import Q
from django.http import HttpResponse
from django.utils import timezone

from godmode.models import DataExport, DataExportConfig

logger = logging.getLogger(__name__)


class DataExporter:
    """
    Utility class for exporting data in various formats.
    """
    
    def __init__(self, config_id=None, config=None):
        """
        Initialize the data exporter.
        
        Args:
            config_id: ID of the export configuration
            config: Export configuration object
        """
        self.config = None
        self.model = None
        self.queryset = None
        self.fields = []
        self.field_labels = {}
        self.filters = {}
        self.order_by = []
        self.export_format = "xlsx"
        self.file_name = None
        self.user = None
        
        # Load configuration if provided
        if config_id:
            self.load_config(config_id)
        elif config:
            self.config = config
            self.load_model()
            self.load_fields()
            self.load_filters()
    
    def load_config(self, config_id):
        """
        Load export configuration from database.
        
        Args:
            config_id: ID of the export configuration
        """
        try:
            self.config = DataExportConfig.objects.get(id=config_id)
            self.load_model()
            self.load_fields()
            self.load_filters()
        except DataExportConfig.DoesNotExist:
            logger.error(f"Export configuration {config_id} not found")
            raise ValueError(f"Export configuration {config_id} not found")
    
    def load_model(self):
        """
        Load the model class from the configuration.
        """
        if not self.config:
            raise ValueError("No configuration loaded")
            
        try:
            app_label, model_name = self.config.model_name.split(".")
            self.model = apps.get_model(app_label, model_name)
            self.queryset = self.model.objects.all()
        except (ValueError, LookupError) as e:
            logger.error(f"Error loading model {self.config.model_name}: {str(e)}")
            raise ValueError(f"Invalid model: {self.config.model_name}")
    
    def load_fields(self):
        """
        Load fields from the configuration.
        """
        if not self.config or not self.model:
            raise ValueError("No configuration or model loaded")
            
        self.fields = []
        self.field_labels = {}
        
        for field in self.config.fields:
            try:
                model_field = self.model._meta.get_field(field)
                self.fields.append(field)
                self.field_labels[field] = model_field.verbose_name
            except Exception as e:
                logger.warning(f"Field {field} not found in model {self.model.__name__}: {str(e)}")
    
    def load_filters(self):
        """
        Load filters from the configuration.
        """
        if not self.config:
            raise ValueError("No configuration loaded")
            
        self.filters = self.config.filters or {}
    
    def set_fields(self, fields):
        """
        Set the fields to export.
        
        Args:
            fields: List of field names
        """
        if not self.model:
            raise ValueError("No model loaded")
            
        self.fields = []
        self.field_labels = {}
        
        for field in fields:
            try:
                model_field = self.model._meta.get_field(field)
                self.fields.append(field)
                self.field_labels[field] = model_field.verbose_name
            except Exception as e:
                logger.warning(f"Field {field} not found in model {self.model.__name__}: {str(e)}")
    
    def set_filters(self, filters):
        """
        Set the filters for the export.
        
        Args:
            filters: Dictionary of filters
        """
        self.filters = filters or {}
    
    def set_order_by(self, order_by):
        """
        Set the ordering for the export.
        
        Args:
            order_by: List of field names to order by
        """
        self.order_by = order_by or []
    
    def set_export_format(self, export_format):
        """
        Set the export format.
        
        Args:
            export_format: Export format (csv, xlsx, json)
        """
        if export_format not in ["csv", "xlsx", "json"]:
            raise ValueError(f"Unsupported export format: {export_format}")
            
        self.export_format = export_format
    
    def set_file_name(self, file_name):
        """
        Set the export file name.
        
        Args:
            file_name: File name without extension
        """
        self.file_name = file_name
    
    def set_user(self, user):
        """
        Set the user performing the export.
        
        Args:
            user: User object
        """
        self.user = user
    
    def apply_filters(self):
        """
        Apply filters to the queryset.
        """
        if not self.queryset:
            raise ValueError("No queryset available")
            
        if not self.filters:
            return
            
        # Build Q objects for complex filters
        q_objects = Q()
        
        for field, value in self.filters.items():
            # Handle special filters
            if field == "search":
                # Search across multiple fields
                search_fields = self.filters.get("search_fields", [])
                if search_fields and value:
                    search_q = Q()
                    for search_field in search_fields:
                        search_q |= Q(**{f"{search_field}__icontains": value})
                    q_objects &= search_q
            elif field == "search_fields":
                # Skip this field, it's handled with "search"
                continue
            elif field == "date_range":
                # Date range filter
                date_field = self.filters.get("date_field", "created_at")
                start_date = value.get("start")
                end_date = value.get("end")
                
                if start_date:
                    q_objects &= Q(**{f"{date_field}__gte": start_date})
                if end_date:
                    q_objects &= Q(**{f"{date_field}__lte": end_date})
            elif field == "date_field":
                # Skip this field, it's handled with "date_range"
                continue
            else:
                # Regular field filter
                q_objects &= Q(**{field: value})
                
        # Apply the filters
        self.queryset = self.queryset.filter(q_objects)
    
    def apply_ordering(self):
        """
        Apply ordering to the queryset.
        """
        if not self.queryset:
            raise ValueError("No queryset available")
            
        if self.order_by:
            self.queryset = self.queryset.order_by(*self.order_by)
    
    def get_data(self):
        """
        Get the data for export.
        
        Returns:
            List of dictionaries with field values
        """
        if not self.queryset:
            raise ValueError("No queryset available")
            
        # Apply filters and ordering
        self.apply_filters()
        self.apply_ordering()
        
        # Get the data
        data = []
        
        for obj in self.queryset:
            row = {}
            
            for field in self.fields:
                # Get the field value
                value = getattr(obj, field)
                
                # Handle callable values
                if callable(value):
                    value = value()
                    
                # Handle special types
                if isinstance(value, datetime):
                    value = value.isoformat()
                    
                row[field] = value
                
            data.append(row)
            
        return data
    
    def export_csv(self):
        """
        Export data as CSV.
        
        Returns:
            HttpResponse with CSV file
        """
        # Get the data
        data = self.get_data()
        
        # Create response
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{self.get_file_name()}.csv"'
        
        # Create CSV writer
        writer = csv.writer(response)
        
        # Write header row
        header = [self.field_labels.get(field, field) for field in self.fields]
        writer.writerow(header)
        
        # Write data rows
        for row in data:
            writer.writerow([row.get(field, "") for field in self.fields])
            
        return response
    
    def export_xlsx(self):
        """
        Export data as XLSX.
        
        Returns:
            HttpResponse with XLSX file
        """
        # Get the data
        data = self.get_data()
        
        # Create response
        output = io.BytesIO()
        
        # Create workbook
        workbook = xlsxwriter.Workbook(output)
        worksheet = workbook.add_worksheet()
        
        # Add header row with formatting
        header_format = workbook.add_format({
            "bold": True,
            "bg_color": "#f0f0f0",
            "border": 1,
        })
        
        for col, field in enumerate(self.fields):
            worksheet.write(0, col, self.field_labels.get(field, field), header_format)
            
        # Write data rows
        for row_idx, row in enumerate(data, start=1):
            for col_idx, field in enumerate(self.fields):
                value = row.get(field, "")
                worksheet.write(row_idx, col_idx, value)
                
        # Auto-fit columns
        for col_idx, field in enumerate(self.fields):
            max_len = len(self.field_labels.get(field, field))
            
            for row_idx, row in enumerate(data, start=1):
                value = str(row.get(field, ""))
                max_len = max(max_len, len(value))
                
            worksheet.set_column(col_idx, col_idx, max_len + 2)
            
        # Close workbook
        workbook.close()
        
        # Prepare response
        output.seek(0)
        response = HttpResponse(
            output.read(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f'attachment; filename="{self.get_file_name()}.xlsx"'
        
        return response
    
    def export_json(self):
        """
        Export data as JSON.
        
        Returns:
            HttpResponse with JSON file
        """
        # Get the data
        data = self.get_data()
        
        # Create response
        response = HttpResponse(content_type="application/json")
        response["Content-Disposition"] = f'attachment; filename="{self.get_file_name()}.json"'
        
        # Write JSON data
        json.dump(data, response, indent=2, default=str)
        
        return response
    
    def get_file_name(self):
        """
        Get the export file name.
        
        Returns:
            File name without extension
        """
        if self.file_name:
            return self.file_name
            
        # Generate file name based on model and timestamp
        model_name = self.model.__name__ if self.model else "export"
        timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
        
        return f"{model_name}_{timestamp}"
    
    def create_export_record(self):
        """
        Create an export record in the database.
        
        Returns:
            DataExport instance
        """
        if not self.config or not self.user:
            return None
            
        # Create file name
        file_name = f"{self.get_file_name()}.{self.export_format}"
        
        # Create export record
        export = DataExport.objects.create(
            config=self.config,
            file_name=file_name,
            status="processing",
            created_by=self.user,
        )
        
        return export
    
    def update_export_record(self, export, row_count, status="completed", error_message=None):
        """
        Update an export record in the database.
        
        Args:
            export: DataExport instance
            row_count: Number of rows exported
            status: Export status
            error_message: Error message (if any)
        """
        if not export:
            return
            
        export.row_count = row_count
        export.status = status
        export.completed_at = timezone.now()
        
        if error_message:
            export.error_message = error_message
            
        export.save()
        
        # Update config last used timestamp
        if export.config:
            export.config.last_used = timezone.now()
            export.config.save()
    
    def export(self):
        """
        Export data in the specified format.
        
        Returns:
            HttpResponse with exported file
        """
        # Create export record
        export = self.create_export_record()
        
        try:
            # Get export function
            export_func = getattr(self, f"export_{self.export_format}")
            
            # Export data
            response = export_func()
            
            # Update export record
            if export:
                self.update_export_record(export, len(self.get_data()))
                
            return response
        except Exception as e:
            logger.exception(f"Error exporting data: {str(e)}")
            
            # Update export record
            if export:
                self.update_export_record(export, 0, "failed", str(e))
                
            raise
