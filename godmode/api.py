"""
God Mode API for admin operations.

This module provides API endpoints for God Mode operations, including:
- User management (delete users/admins)
- Payment webhook logging
- Data export
- Cache-to-DB synchronization
- User rankings and leaderboards
- Simulation metrics
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union

from django.contrib.auth import get_user_model
from django.apps import apps
from django.db import transaction
from django.db.models import Avg, Count, F, Q, Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from ninja import Router, Schema
from ninja.pagination import paginate
from pydantic import BaseModel, Field

from accounts.models import Profile
from core.cache import redis_client
from core.redis_settings import CACHE_ENABLED
from godmode.cache_sync import cache_sync_manager
from godmode.export_utils import DataExporter
from godmode.models import (DataExport, DataExportConfig, LocationVerification,
                           SimulationRun, UserActivityLog, UserRanking,
                           WebhookLog, WorkAssignment)
from godmode.webhook_utils import capture_webhook, reprocess_webhook, get_webhook_stats
from jobs.models import Application, Job
from payment.models import Payment

User = get_user_model()
logger = logging.getLogger(__name__)

godmode_router = Router(tags=["God Mode"])


# ===
# Schemas
# ===

class UserDeleteSchema(BaseModel):
    user_id: int
    confirmation: str
    reason: str


class WebhookReprocessSchema(BaseModel):
    webhook_id: int


class CacheSyncSchema(BaseModel):
    model_name: Optional[str] = None
    force: bool = False


class ExportConfigSchema(BaseModel):
    name: str
    description: Optional[str] = None
    model_name: str
    fields: List[str]
    filters: Optional[Dict] = None


class RunExportSchema(BaseModel):
    config_id: int
    export_format: str = "xlsx"
    filters: Optional[Dict] = None
    order_by: Optional[List[str]] = None


class WebhookLogSchema(BaseModel):
    id: int
    reference: Optional[str] = None
    gateway: Optional[str] = None
    status: Optional[str] = None
    ip_address: Optional[str] = None
    created_at: datetime

class SimulationRunSchema(BaseModel):
    id: int
    simulation_type: str
    status: str
    created_at: datetime

class SimulationSchema(BaseModel):
    simulation_type: str
    parameters: Dict


# ===
# User Management Endpoints
# ===

@godmode_router.post("/users/delete")
def delete_user(request, payload: UserDeleteSchema):
    """
    Delete a user account with audit logging.

    Only superusers can delete users. The confirmation must match the username.
    """
    # Check if user is a superuser
    if not request.user.is_superuser:
        return {"status": "error", "message": "You do not have permission to delete users"}

    try:
        # Get the user to delete
        user = get_object_or_404(User, id=payload.user_id)

        # Check confirmation
        if payload.confirmation != user.username:
            return {"status": "error", "message": "Confirmation text does not match the username"}

        # Log the deletion
        UserActivityLog.objects.create(
            user=request.user,
            action_type="admin_action",
            details={
                "action": "delete_user",
                "deleted_user_id": user.id,
                "deleted_username": user.username,
                "deleted_email": user.email,
                "deleted_role": getattr(user, "role", "user"),
                "reason": payload.reason,
                "deleted_at": timezone.now().isoformat(),
            },
        )

        # Delete the user
        username = user.username
        user.delete()

        return {
            "status": "success",
            "message": f"User {username} has been deleted",
            "deleted_at": timezone.now().isoformat(),
        }
    except Exception as e:
        logger.exception(f"Error deleting user: {str(e)}")
        return {"status": "error", "message": str(e)}


# ===
# Payment Webhook Endpoints
# ===

@godmode_router.get("/webhooks", response=List[WebhookLogSchema])
@paginate
def list_webhooks(request, gateway: Optional[str] = None, status: Optional[str] = None,
                 reference: Optional[str] = None, date_from: Optional[str] = None,
                 date_to: Optional[str] = None):
    """
    List payment webhooks with filtering options.
    """
    # Base queryset
    webhooks = WebhookLog.objects.all()

    # Apply filters
    if gateway:
        webhooks = webhooks.filter(gateway=gateway)

    if status:
        webhooks = webhooks.filter(status=status)

    if reference:
        webhooks = webhooks.filter(reference__icontains=reference)

    if date_from:
        try:
            date_from = datetime.strptime(date_from, "%Y-%m-%d")
            webhooks = webhooks.filter(created_at__gte=date_from)
        except ValueError:
            pass

    if date_to:
        try:
            date_to = datetime.strptime(date_to, "%Y-%m-%d")
            # Add one day to include the entire end date
            date_to = date_to + timedelta(days=1)
            webhooks = webhooks.filter(created_at__lt=date_to)
        except ValueError:
            pass

    # Order by created_at (newest first)
    webhooks = webhooks.order_by("-created_at")

    return webhooks


@godmode_router.get("/webhooks/{webhook_id}")
def get_webhook(request, webhook_id: int):
    """
    Get details of a specific webhook.
    """
    try:
        webhook = get_object_or_404(WebhookLog, id=webhook_id)

        # Get related payment if available
        payment = None
        try:
            payment = Payment.objects.get(pay_code=webhook.reference)
            payment_data = {
                "id": payment.id,
                "payer": payment.payer.username if payment.payer else None,
                "recipient": payment.recipient.username if payment.recipient else None,
                "original_amount": str(payment.original_amount),
                "service_fee": str(payment.service_fee),
                "final_amount": str(payment.final_amount),
                "status": payment.status,
                "created_at": payment.created_at.isoformat(),
            }
        except Payment.DoesNotExist:
            payment_data = None

        return {
            "id": webhook.id,
            "reference": webhook.reference,
            "gateway": webhook.gateway,
            "status": webhook.status,
            "request_data": webhook.request_data,
            "response_data": webhook.response_data,
            "error_message": webhook.error_message,
            "ip_address": webhook.ip_address,
            "created_at": webhook.created_at.isoformat(),
            "payment": payment_data,
        }
    except Exception as e:
        logger.exception(f"Error getting webhook: {str(e)}")
        return {"status": "error", "message": str(e)}


@godmode_router.post("/webhooks/reprocess")
def reprocess_webhook_endpoint(request, payload: WebhookReprocessSchema):
    """
    Reprocess a failed webhook.
    """
    try:
        success, message, webhook = reprocess_webhook(payload.webhook_id)

        if success:
            return {
                "status": "success",
                "message": message,
                "webhook_id": webhook.id,
                "reference": webhook.reference,
                "new_status": webhook.status,
            }
        else:
            return {
                "status": "error",
                "message": message,
                "webhook_id": webhook.id if webhook else None,
            }
    except Exception as e:
        logger.exception(f"Error reprocessing webhook: {str(e)}")
        return {"status": "error", "message": str(e)}


@godmode_router.get("/webhooks/stats")
def webhook_stats(request):
    """
    Get statistics about webhooks.
    """
    try:
        stats = get_webhook_stats()
        return stats
    except Exception as e:
        logger.exception(f"Error getting webhook stats: {str(e)}")
        return {"status": "error", "message": str(e)}


# ===
# Cache Sync Endpoints
# ===

@godmode_router.post("/cache/sync")
def sync_cache_to_db(request, payload: CacheSyncSchema):
    """
    Synchronize Redis cache with the database.

    If model_name is provided, only sync that model.
    Otherwise, sync all models.
    """
    if not CACHE_ENABLED or not redis_client:
        return {"status": "error", "message": "Redis cache is not enabled"}

    try:
        # Log the sync operation
        UserActivityLog.objects.create(
            user=request.user,
            action_type="admin_action",
            details={
                "action": "sync_cache_to_db",
                "model_name": payload.model_name,
                "force": payload.force,
                "initiated_at": timezone.now().isoformat(),
            },
        )

        # Perform the sync
        if payload.model_name:
            result = cache_sync_manager.sync_model_to_db(payload.model_name, payload.force)
        else:
            result = cache_sync_manager.sync_all_to_db(payload.force)

        return {
            "status": "success",
            "message": "Cache sync completed",
            "result": result,
        }
    except Exception as e:
        logger.exception(f"Error syncing cache to DB: {str(e)}")
        return {"status": "error", "message": str(e)}


@godmode_router.get("/cache/stats")
def cache_stats(request):
    """
    Get Redis cache statistics.
    """
    if not CACHE_ENABLED or not redis_client:
        return {"status": "error", "message": "Redis cache is not enabled"}

    try:
        # Get Redis info
        info = redis_client.info()

        # Get memory usage
        used_memory = info.get("used_memory", 0)
        used_memory_peak = info.get("used_memory_peak", 0)
        maxmemory = info.get("maxmemory", 0)

        # Calculate percentages
        memory_usage_percent = (used_memory / maxmemory * 100) if maxmemory > 0 else 0

        # Get hit rate
        hits = info.get("keyspace_hits", 0)
        misses = info.get("keyspace_misses", 0)
        total_ops = hits + misses
        hit_rate = (hits / total_ops * 100) if total_ops > 0 else 0

        # Get key count
        db = info.get(f"db{redis_client.connection_pool.connection_kwargs.get('db', 0)}", {})
        keys = db.get("keys", 0)

        return {
            "memory": {
                "used_memory": used_memory,
                "used_memory_human": f"{used_memory / (1024 * 1024):.2f} MB",
                "used_memory_peak": used_memory_peak,
                "used_memory_peak_human": f"{used_memory_peak / (1024 * 1024):.2f} MB",
                "maxmemory": maxmemory,
                "maxmemory_human": f"{maxmemory / (1024 * 1024):.2f} MB" if maxmemory > 0 else "Unlimited",
                "memory_usage_percent": f"{memory_usage_percent:.2f}%",
            },
            "hit_rate": {
                "hits": hits,
                "misses": misses,
                "total_operations": total_ops,
                "hit_rate": f"{hit_rate:.2f}%",
            },
            "keys": {
                "total": keys,
            },
            "uptime": {
                "seconds": info.get("uptime_in_seconds", 0),
                "days": f"{info.get('uptime_in_seconds', 0) / (24 * 60 * 60):.2f}",
            },
        }
    except Exception as e:
        logger.exception(f"Error getting cache stats: {str(e)}")
        return {"status": "error", "message": str(e)}


# ===
# Data Export Endpoints
# ===

@godmode_router.get("/exports/configs")
def list_export_configs(request, model_name: Optional[str] = None):
    """
    List data export configurations.
    """
    # Base queryset
    configs = DataExportConfig.objects.all()

    # Apply filters
    if model_name:
        configs = configs.filter(model_name=model_name)

    # Non-superusers can only see their own configs
    if not request.user.is_superuser:
        configs = configs.filter(created_by=request.user)

    # Order by created_at (newest first)
    configs = configs.order_by("-created_at")

    return [
        {
            "id": config.id,
            "name": config.name,
            "description": config.description,
            "model_name": config.model_name,
            "fields": config.fields,
            "filters": config.filters,
            "created_by": config.created_by.username if config.created_by else None,
            "created_at": config.created_at.isoformat(),
            "last_used": config.last_used.isoformat() if config.last_used else None,
        }
        for config in configs
    ]


@godmode_router.post("/exports/configs")
def create_export_config(request, payload: ExportConfigSchema):
    """
    Create a new data export configuration.
    """
    try:
        # Validate model
        try:
            app_label, model_name = payload.model_name.split(".")
            model = apps.get_model(app_label, model_name)
        except (ValueError, LookupError):
            return {"status": "error", "message": f"Invalid model: {payload.model_name}"}

        # Validate fields
        valid_fields = []
        for field in payload.fields:
            try:
                model._meta.get_field(field)
                valid_fields.append(field)
            except:
                pass

        if not valid_fields:
            return {"status": "error", "message": "No valid fields selected"}

        # Create the config
        config = DataExportConfig.objects.create(
            name=payload.name,
            description=payload.description,
            model_name=payload.model_name,
            fields=valid_fields,
            filters=payload.filters or {},
            created_by=request.user,
        )

        return {
            "status": "success",
            "message": f"Export configuration '{payload.name}' created successfully",
            "config_id": config.id,
        }
    except Exception as e:
        logger.exception(f"Error creating export config: {str(e)}")
        return {"status": "error", "message": str(e)}


@godmode_router.post("/exports/run")
def run_export(request, payload: RunExportSchema):
    """
    Run a data export using a configuration.
    """
    try:
        # Get the config
        config = get_object_or_404(DataExportConfig, id=payload.config_id)

        # Non-superusers can only use their own configs
        if not request.user.is_superuser and config.created_by != request.user:
            return {
                "status": "error",
                "message": "You do not have permission to use this export configuration",
            }

        # Create exporter
        exporter = DataExporter(config=config)
        exporter.set_export_format(payload.export_format)
        exporter.set_user(request.user)

        # Apply custom filters and ordering if provided
        if payload.filters:
            exporter.set_filters(payload.filters)

        if payload.order_by:
            exporter.set_order_by(payload.order_by)

        # Generate timestamp for file name
        timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
        model_name = config.model_name.split(".")[-1]
        exporter.set_file_name(f"{model_name}_{timestamp}")

        # Create export record
        export = exporter.create_export_record()

        # Export data
        response = exporter.export()

        # Update export record
        if export:
            exporter.update_export_record(export, len(exporter.get_data()))

        return response
    except Exception as e:
        logger.exception(f"Error running export: {str(e)}")
        return {"status": "error", "message": str(e)}


@godmode_router.get("/exports/models")
def list_exportable_models(request):
    """
    List models available for export.
    """
    try:
        # Get available models for export
        available_models = []
        for app_config in apps.get_app_configs():
            if app_config.name in [
                "accounts",
                "jobs",
                "payment",
                "disputes",
                "gamification",
                "userlocation",
                "godmode",
            ]:
                for model in app_config.get_models():
                    model_info = {
                        "name": f"{model._meta.app_label}.{model._meta.model_name}",
                        "verbose_name": model._meta.verbose_name,
                        "fields": [
                            {
                                "name": field.name,
                                "verbose_name": field.verbose_name,
                                "type": field.get_internal_type(),
                            }
                            for field in model._meta.fields
                        ],
                    }
                    available_models.append(model_info)

        return sorted(available_models, key=lambda x: x["name"])
    except Exception as e:
        logger.exception(f"Error listing exportable models: {str(e)}")
        return {"status": "error", "message": str(e)}


# ===
# User Rankings Endpoints
# ===

@godmode_router.get("/rankings")
def get_rankings(request, ranking_type: str = "points", limit: int = 10):
    """
    Get user rankings for a specific type.
    """
    try:
        # Validate ranking type
        valid_types = [choice[0] for choice in UserRanking.RANKING_TYPE_CHOICES]
        if ranking_type not in valid_types:
            return {"status": "error", "message": f"Invalid ranking type: {ranking_type}"}

        # Get rankings
        rankings = UserRanking.objects.filter(ranking_type=ranking_type).order_by("rank")[:limit]

        # If no rankings exist, generate them
        if not rankings.exists():
            from godmode.views import generate_rankings
            generate_rankings(request, ranking_type)
            rankings = UserRanking.objects.filter(ranking_type=ranking_type).order_by("rank")[:limit]

        return {
            "ranking_type": ranking_type,
            "ranking_type_display": dict(UserRanking.RANKING_TYPE_CHOICES)[ranking_type],
            "rankings": [
                {
                    "rank": ranking.rank,
                    "user_id": ranking.user_id,
                    "username": ranking.user.username,
                    "score": ranking.score,
                    "percentile": ranking.percentile,
                    "previous_rank": ranking.previous_rank,
                    "previous_score": ranking.previous_score,
                    "updated_at": ranking.updated_at.isoformat(),
                }
                for ranking in rankings
            ],
        }
    except Exception as e:
        logger.exception(f"Error getting rankings: {str(e)}")
        return {"status": "error", "message": str(e)}


@godmode_router.post("/rankings/generate")
def generate_rankings_endpoint(request, ranking_type: str = "points"):
    """
    Generate or update user rankings for a specific type.
    """
    try:
        # Validate ranking type
        valid_types = [choice[0] for choice in UserRanking.RANKING_TYPE_CHOICES]
        if ranking_type not in valid_types:
            return {"status": "error", "message": f"Invalid ranking type: {ranking_type}"}

        # Generate rankings
        from godmode.views import generate_rankings
        generate_rankings(request, ranking_type)

        return {
            "status": "success",
            "message": f"Rankings for {dict(UserRanking.RANKING_TYPE_CHOICES)[ranking_type]} updated successfully",
        }
    except Exception as e:
        logger.exception(f"Error generating rankings: {str(e)}")
        return {"status": "error", "message": str(e)}


# ===
# Simulation Endpoints
# ===

@godmode_router.post("/simulations/run")
def run_simulation_endpoint(request, payload: SimulationSchema):
    """
    Run a simulation.
    """
    try:
        # Validate simulation type
        if payload.simulation_type not in [s[0] for s in SimulationRun.SIMULATION_TYPES]:
            return {"status": "error", "message": "Invalid simulation type"}

        # Create simulation run record
        simulation = SimulationRun.objects.create(
            simulation_type=payload.simulation_type,
            parameters=payload.parameters,
            status="running",
            initiated_by=request.user,
        )

        # Log the activity
        UserActivityLog.objects.create(
            user=request.user,
            action_type="simulation",
            details={
                "simulation_id": simulation.id,
                "simulation_type": payload.simulation_type,
                "parameters": payload.parameters,
            },
        )

        # Run the simulation asynchronously
        try:
            # Build command
            import subprocess

            cmd = [
                "python",
                "manage.py",
                "run_simulations",
                f"--simulations={payload.simulation_type}",
            ]

            # Add parameters
            for key, value in payload.parameters.items():
                if isinstance(value, bool):
                    if value:
                        cmd.append(f"--{key}")
                else:
                    cmd.append(f"--{key}={value}")

            # Add --save-results flag
            cmd.append("--save-results")

            # Run the command
            process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )

            return {
                "status": "success",
                "message": f"{simulation.get_simulation_type_display()} simulation started successfully",
                "simulation_id": simulation.id,
            }
        except Exception as e:
            simulation.status = "failed"
            simulation.result = {"error": str(e)}
            simulation.completed_at = timezone.now()
            simulation.save()

            return {"status": "error", "message": f"Error starting simulation: {str(e)}"}
    except Exception as e:
        logger.exception(f"Error running simulation: {str(e)}")
        return {"status": "error", "message": str(e)}


@godmode_router.get("/simulations/{simulation_id}")
def get_simulation(request, simulation_id: int):
    """
    Get details of a specific simulation.
    """
    try:
        simulation = get_object_or_404(SimulationRun, id=simulation_id)

        return {
            "id": simulation.id,
            "simulation_type": simulation.simulation_type,
            "simulation_type_display": simulation.get_simulation_type_display(),
            "parameters": simulation.parameters,
            "status": simulation.status,
            "result": simulation.result,
            "started_at": simulation.started_at.isoformat(),
            "completed_at": simulation.completed_at.isoformat() if simulation.completed_at else None,
            "initiated_by": simulation.initiated_by.username if simulation.initiated_by else None,
        }
    except Exception as e:
        logger.exception(f"Error getting simulation: {str(e)}")
        return {"status": "error", "message": str(e)}


@godmode_router.get("/simulations", response=List[SimulationRunSchema])
@paginate
def list_simulations(request, simulation_type: Optional[str] = None, status: Optional[str] = None):
    """
    List simulations with filtering options.
    """
    # Base queryset
    simulations = SimulationRun.objects.all()

    # Apply filters
    if simulation_type:
        simulations = simulations.filter(simulation_type=simulation_type)

    if status:
        simulations = simulations.filter(status=status)

    # Order by started_at (newest first)
    simulations = simulations.order_by("-started_at")

    return simulations


# ===
# Dashboard Endpoints
# ===

@godmode_router.get("/dashboard/stats")
def dashboard_stats(request):
    """
    Get statistics for the God Mode dashboard.
    """
    try:
        # Get counts for various entities
        user_count = User.objects.count()
        admin_count = User.objects.filter(role="admin").count()
        client_count = User.objects.filter(role="client").count()
        applicant_count = User.objects.filter(role="applicant").count()
        job_count = Job.objects.count()
        application_count = Application.objects.count()
        payment_count = Payment.objects.count()

        # Get active users (logged in within the last 24 hours)
        active_users = (
            UserActivityLog.objects.filter(
                action_type="login", timestamp__gte=timezone.now() - timedelta(hours=24)
            )
            .values("user")
            .distinct()
            .count()
        )

        # Get payment stats
        payment_stats = {
            "total": payment_count,
            "successful": Payment.objects.filter(status="Completed").count(),
            "failed": Payment.objects.filter(status="Failed").count(),
        }

        # Calculate success rate
        if payment_stats["total"] > 0:
            payment_stats["success_rate"] = (
                payment_stats["successful"] / payment_stats["total"]
            ) * 100
        else:
            payment_stats["success_rate"] = 0

        # Get webhook stats
        webhook_stats = get_webhook_stats()

        # Get cache stats
        cache_stats = {}
        if CACHE_ENABLED and redis_client:
            try:
                info = redis_client.info()

                # Get hit rate
                hits = info.get("keyspace_hits", 0)
                misses = info.get("keyspace_misses", 0)
                total_ops = hits + misses
                hit_rate = (hits / total_ops * 100) if total_ops > 0 else 0

                cache_stats = {
                    "hit_rate": hit_rate,
                    "hits": hits,
                    "misses": misses,
                    "total_operations": total_ops,
                }
            except Exception as e:
                logger.error(f"Error getting Redis stats: {str(e)}")

        return {
            "users": {
                "total": user_count,
                "admin": admin_count,
                "client": client_count,
                "applicant": applicant_count,
                "active": active_users,
            },
            "jobs": {
                "total": job_count,
            },
            "applications": {
                "total": application_count,
            },
            "payments": payment_stats,
            "webhooks": webhook_stats,
            "cache": cache_stats,
        }
    except Exception as e:
        logger.exception(f"Error getting dashboard stats: {str(e)}")
        return {"status": "error", "message": str(e)}
