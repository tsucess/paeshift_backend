import csv
import io
import json
import os
import subprocess
from datetime import datetime, timedelta

import xlsxwriter
from django.apps import apps
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.db.models import (Avg, Case, Count, F, IntegerField, Q, Sum, Value,
                              When)
from django.db.models.functions import Coalesce
from django.http import FileResponse, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.models import Profile
from disputes.models import Dispute
from gamification.models import UserActivity
from jobchat.models import LocationHistory
from jobs.models import Application, Job
from payment.models import Payment

from .models import (DataExport, DataExportConfig, LocationVerification,
                     SimulationRun, UserActivityLog, UserRanking, WebhookLog,
                     WorkAssignment)

User = get_user_model()
from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import redirect, render


def signup_view(request):
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("login")
    else:
        form = UserCreationForm()
    return render(request, "registration/signup.html", {"form": form})


# Helper function to check if user is an admin
def is_admin(user):
    return user.is_authenticated and user.role == "godmode"


@login_required
@user_passes_test(is_admin)
def godmode_dashboard(request):
    """
    Main dashboard for the God Mode interface.
    Shows summary statistics and recent activity.
    """
    # Get counts for various entities
    user_count = User.objects.count()
    admin_count = User.objects.filter(role="admin").count()
    client_count = User.objects.filter(role="client").count()
    applicant_count = User.objects.filter(role="applicant").count()
    job_count = Job.objects.count()
    application_count = Application.objects.count()
    payment_count = Payment.objects.count()
    dispute_count = Dispute.objects.count()

    # Get recent user activity
    recent_activity = UserActivityLog.objects.all().order_by("-timestamp")[:10]

    # Get recent logins
    recent_logins = UserActivityLog.objects.filter(action_type="login").order_by(
        "-timestamp"
    )[:10]

    # Get recent simulations
    recent_simulations = SimulationRun.objects.all().order_by("-started_at")[:5]

    # Get active users (logged in within the last 24 hours)
    active_users = (
        UserActivityLog.objects.filter(
            action_type="login", timestamp__gte=timezone.now() - timedelta(hours=24)
        )
        .values("user")
        .distinct()
        .count()
    )

    context = {
        "user_count": user_count,
        "admin_count": admin_count,
        "client_count": client_count,
        "applicant_count": applicant_count,
        "job_count": job_count,
        "application_count": application_count,
        "payment_count": payment_count,
        "dispute_count": dispute_count,
        "active_users": active_users,
        "recent_activity": recent_activity,
        "recent_logins": recent_logins,
        "recent_simulations": recent_simulations,
    }

    return render(request, "godmode/dashboard.html", context)


# @login_required
# @user_passes_test(is_admin)
def user_activity(request):
    """
    View to display all user activity with filtering options.
    """
    # Get filter parameters
    user_id = request.GET.get("user_id")
    action_type = request.GET.get("action_type")
    date_from = request.GET.get("date_from")
    date_to = request.GET.get("date_to")

    # Base queryset
    activities = UserActivityLog.objects.all()

    # Apply filters
    if user_id:
        activities = activities.filter(user_id=user_id)

    if action_type:
        activities = activities.filter(action_type=action_type)

    if date_from:
        try:
            date_from = datetime.strptime(date_from, "%Y-%m-%d")
            activities = activities.filter(timestamp__gte=date_from)
        except ValueError:
            pass

    if date_to:
        try:
            date_to = datetime.strptime(date_to, "%Y-%m-%d")
            # Add one day to include the entire end date
            date_to = date_to + timedelta(days=1)
            activities = activities.filter(timestamp__lt=date_to)
        except ValueError:
            pass

    # Order by timestamp (newest first)
    activities = activities.order_by("-timestamp")

    # Paginate results
    paginator = Paginator(activities, 50)  # 50 activities per page
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # Get all users for the filter dropdown
    users = User.objects.all().order_by("username")

    context = {
        "page_obj": page_obj,
        "users": users,
        "action_types": UserActivityLog.ACTION_TYPES,
        "filters": {
            "user_id": user_id,
            "action_type": action_type,
            "date_from": date_from,
            "date_to": date_to,
        },
    }

    return render(request, "godmode/user_activity.html", context)


# @login_required
# @user_passes_test(is_admin)
def user_detail(request, user_id):
    """
    Detailed view of a specific user, including their activity and location history.
    """
    user = get_object_or_404(User, id=user_id)
    profile = Profile.objects.filter(user=user).first()

    # Get user's activity
    activities = UserActivityLog.objects.filter(user=user).order_by("-timestamp")[:50]

    # Get user's location history
    locations = LocationHistory.objects.filter(user=user).order_by("-created_at")[:100]

    # Get user's jobs (if client) or applications (if applicant)
    jobs = []
    applications = []

    if user.role == "client":
        jobs = Job.objects.filter(client=user).order_by("-created_at")[:20]
    elif user.role == "applicant":
        applications = Application.objects.filter(applicant=user).order_by(
            "-created_at"
        )[:20]

    # Get user's payments
    payments = Payment.objects.filter(payer=user).order_by("-created_at")[:20]

    # Get user's disputes
    disputes = Dispute.objects.filter(
        Q(filed_by=user) | Q(filed_against=user)
    ).order_by("-created_at")[:20]

    context = {
        "user_obj": user,
        "profile": profile,
        "activities": activities,
        "locations": locations,
        "jobs": jobs,
        "applications": applications,
        "payments": payments,
        "disputes": disputes,
    }

    return render(request, "godmode/user_detail.html", context)


# @login_required
# @user_passes_test(is_admin)
def location_verification(request):
    """
    View to verify user locations by comparing claimed addresses with location history.
    """
    # Get filter parameters
    user_id = request.GET.get("user_id")
    status = request.GET.get("status")

    # Base queryset
    verifications = LocationVerification.objects.all()

    # Apply filters
    if user_id:
        verifications = verifications.filter(user_id=user_id)

    if status:
        verifications = verifications.filter(verification_status=status)

    # Order by created_at (newest first)
    verifications = verifications.order_by("-created_at")

    # Paginate results
    paginator = Paginator(verifications, 20)  # 20 verifications per page
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # Get all users for the filter dropdown
    users = User.objects.all().order_by("username")

    context = {
        "page_obj": page_obj,
        "users": users,
        "status_choices": LocationVerification.STATUS_CHOICES,
        "filters": {
            "user_id": user_id,
            "status": status,
        },
    }

    return render(request, "godmode/location_verification.html", context)


# @login_required
# @user_passes_test(is_admin)
def verify_location(request, verification_id):
    """
    Process a location verification and update its status.
    """
    verification = get_object_or_404(LocationVerification, id=verification_id)

    if request.method == "POST":
        status = request.POST.get("status")
        notes = request.POST.get("notes", "")

        if status in [s[0] for s in LocationVerification.STATUS_CHOICES]:
            verification.verification_status = status
            verification.verification_details = {
                "notes": notes,
                "verified_by": request.user.username,
                "verified_at": timezone.now().isoformat(),
            }
            verification.verified_at = timezone.now()
            verification.verified_by = request.user
            verification.save()

            messages.success(
                request,
                f"Location verification for {verification.user.username} updated to {status}.",
            )
        else:
            messages.error(request, "Invalid status provided.")

        return redirect("godmode:location_verification")

    # Get user's location history
    locations = LocationHistory.objects.filter(user=verification.user).order_by(
        "-created_at"
    )[:100]

    context = {
        "verification": verification,
        "locations": locations,
        "status_choices": LocationVerification.STATUS_CHOICES,
    }

    return render(request, "godmode/verify_location.html", context)


# @login_required
# @user_passes_test(is_admin)
def run_simulation(request):
    """
    View to run simulations from the God Mode interface.
    """
    if request.method == "POST":
        simulation_type = request.POST.get("simulation_type")

        # Validate simulation type
        if simulation_type not in [s[0] for s in SimulationRun.SIMULATION_TYPES]:
            messages.error(request, "Invalid simulation type.")
            return redirect("godmode:run_simulation")

        # Get parameters based on simulation type
        parameters = {}

        if simulation_type in ["admin", "client", "applicant"]:
            parameters["count"] = int(request.POST.get("count", 1))
            parameters["password"] = request.POST.get("password", "password123")

        if simulation_type == "job":
            parameters["client_count"] = int(request.POST.get("client_count", 2))
            parameters["jobs_per_client"] = int(request.POST.get("jobs_per_client", 3))
            parameters["use_existing_clients"] = True

        if simulation_type == "application":
            parameters["applicant_count"] = int(request.POST.get("applicant_count", 5))
            parameters["applications_per_applicant"] = int(
                request.POST.get("applications_per_applicant", 2)
            )
            parameters["use_existing_applicants"] = True

        if simulation_type == "payment":
            parameters["count"] = int(request.POST.get("count", 3))
            parameters["payment_method"] = request.POST.get("payment_method", "both")
            parameters["success_rate"] = float(request.POST.get("success_rate", 0.8))

        if simulation_type == "dispute":
            parameters["count"] = int(request.POST.get("count", 5))
            parameters["resolution_rate"] = float(
                request.POST.get("resolution_rate", 0.7)
            )
            parameters["client_favor_rate"] = float(
                request.POST.get("client_favor_rate", 0.5)
            )

        if simulation_type == "location":
            parameters["user_count"] = int(request.POST.get("user_count", 10))
            parameters["updates_per_user"] = int(
                request.POST.get("updates_per_user", 5)
            )
            parameters["update_home_address"] = True
            parameters["create_location_history"] = True
            parameters["update_job_locations"] = True

        if simulation_type == "webhook":
            parameters["payment_method"] = request.POST.get(
                "payment_method", "paystack"
            )
            parameters["success"] = request.POST.get("success", "true") == "true"

        if simulation_type == "full":
            parameters["admin_count"] = int(request.POST.get("admin_count", 1))
            parameters["client_count"] = int(request.POST.get("client_count", 2))
            parameters["applicant_count"] = int(request.POST.get("applicant_count", 5))
            parameters["jobs_per_client"] = int(request.POST.get("jobs_per_client", 3))
            parameters["applications_per_applicant"] = int(
                request.POST.get("applications_per_applicant", 2)
            )
            parameters["payment_success_rate"] = float(
                request.POST.get("payment_success_rate", 0.8)
            )
            parameters[
                "output_file"
            ] = f"simulation_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        # Create simulation run record
        simulation = SimulationRun.objects.create(
            simulation_type=simulation_type,
            parameters=parameters,
            status="running",
            initiated_by=request.user,
        )

        # Log the activity
        UserActivityLog.objects.create(
            user=request.user,
            action_type="simulation",
            details={
                "simulation_id": simulation.id,
                "simulation_type": simulation_type,
                "parameters": parameters,
            },
        )

        # Run the simulation asynchronously
        try:
            # Build command
            cmd = [
                "python",
                "manage.py",
                "run_simulations",
                f"--simulations={simulation_type}",
            ]

            # Add parameters based on simulation type
            for key, value in parameters.items():
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

            # Update simulation status
            simulation.status = "running"
            simulation.save()

            messages.success(
                request,
                f"{simulation.get_simulation_type_display()} simulation started successfully.",
            )
        except Exception as e:
            simulation.status = "failed"
            simulation.result = {"error": str(e)}
            simulation.completed_at = timezone.now()
            simulation.save()

            messages.error(request, f"Error starting simulation: {str(e)}")

        return redirect("godmode:simulations")

    context = {
        "simulation_types": SimulationRun.SIMULATION_TYPES,
    }

    return render(request, "godmode/run_simulation.html", context)


# @login_required
# @user_passes_test(is_admin)
def simulations(request):
    """
    View to list all simulation runs.
    """
    # Get filter parameters
    simulation_type = request.GET.get("simulation_type")
    status = request.GET.get("status")

    # Base queryset
    simulations = SimulationRun.objects.all()

    # Apply filters
    if simulation_type:
        simulations = simulations.filter(simulation_type=simulation_type)

    if status:
        simulations = simulations.filter(status=status)

    # Order by started_at (newest first)
    simulations = simulations.order_by("-started_at")

    # Paginate results
    paginator = Paginator(simulations, 20)  # 20 simulations per page
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "simulation_types": SimulationRun.SIMULATION_TYPES,
        "status_choices": SimulationRun.STATUS_CHOICES,
        "filters": {
            "simulation_type": simulation_type,
            "status": status,
        },
    }

    return render(request, "godmode/simulations.html", context)


# @login_required
# @user_passes_test(is_admin)
def simulation_detail(request, simulation_id):
    """
    Detailed view of a specific simulation run.
    """
    simulation = get_object_or_404(SimulationRun, id=simulation_id)

    context = {
        "simulation": simulation,
    }

    return render(request, "godmode/simulation_detail.html", context)


# @login_required
# @user_passes_test(is_admin)
def webhook_logs(request):
    """
    View to display payment webhook logs with filtering options.
    """
    # Get filter parameters
    gateway = request.GET.get("gateway")
    status = request.GET.get("status")
    date_from = request.GET.get("date_from")
    date_to = request.GET.get("date_to")
    reference = request.GET.get("reference")

    # Base queryset
    logs = WebhookLog.objects.all()

    # Apply filters
    if gateway:
        logs = logs.filter(gateway=gateway)

    if status:
        logs = logs.filter(status=status)

    if reference:
        logs = logs.filter(reference__icontains=reference)

    if date_from:
        try:
            date_from = datetime.strptime(date_from, "%Y-%m-%d")
            logs = logs.filter(created_at__gte=date_from)
        except ValueError:
            pass

    if date_to:
        try:
            date_to = datetime.strptime(date_to, "%Y-%m-%d")
            # Add one day to include the entire end date
            date_to = date_to + timedelta(days=1)
            logs = logs.filter(created_at__lt=date_to)
        except ValueError:
            pass

    # Order by created_at (newest first)
    logs = logs.order_by("-created_at")

    # Paginate results
    paginator = Paginator(logs, 50)  # 50 logs per page
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "gateway_choices": WebhookLog.GATEWAY_CHOICES,
        "status_choices": WebhookLog.STATUS_CHOICES,
        "filters": {
            "gateway": gateway,
            "status": status,
            "reference": reference,
            "date_from": date_from,
            "date_to": date_to,
        },
    }

    return render(request, "godmode/webhook_logs.html", context)


# @login_required
# @user_passes_test(is_admin)
def webhook_log_detail(request, log_id):
    """
    Detailed view of a specific webhook log.
    """
    log = get_object_or_404(WebhookLog, id=log_id)

    # Get related payment if available
    payment = None
    try:
        payment = Payment.objects.get(reference=log.reference)
    except Payment.DoesNotExist:
        pass

    # Get related transactions if available
    transactions = []  # Transaction.objects.filter(reference=log.reference)

    context = {
        "log": log,
        "payment": payment,
        "transactions": transactions,
    }

    return render(request, "godmode/webhook_log_detail.html", context)


# @login_required
# @user_passes_test(is_admin)
def work_assignments(request):
    """
    View to display and manage work assignments for admin staff.
    """
    # Get filter parameters
    admin_id = request.GET.get("admin_id")
    task_type = request.GET.get("task_type")
    status = request.GET.get("status")
    priority = request.GET.get("priority")

    # Base queryset
    assignments = WorkAssignment.objects.all()

    # Apply filters
    if admin_id:
        assignments = assignments.filter(admin_id=admin_id)

    if task_type:
        assignments = assignments.filter(task_type=task_type)

    if status:
        assignments = assignments.filter(status=status)

    if priority:
        assignments = assignments.filter(priority=priority)

    # Non-superusers can only see their own assignments
    if not request.user.is_superuser:
        assignments = assignments.filter(admin=request.user)

    # Order by priority (highest first) and due_date (soonest first)
    assignments = assignments.order_by(
        Case(
            When(priority="urgent", then=Value(0)),
            When(priority="high", then=Value(1)),
            When(priority="medium", then=Value(2)),
            When(priority="low", then=Value(3)),
            default=Value(4),
            output_field=IntegerField(),
        ),
        F("due_date").asc(nulls_last=True),
        "-created_at",
    )

    # Paginate results
    paginator = Paginator(assignments, 20)  # 20 assignments per page
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # Get all admin users for the filter dropdown
    admin_users = User.objects.filter(role="admin").order_by("username")

    context = {
        "page_obj": page_obj,
        "admin_users": admin_users,
        "task_types": WorkAssignment.TYPE_CHOICES,
        "status_choices": WorkAssignment.STATUS_CHOICES,
        "priority_choices": WorkAssignment.PRIORITY_CHOICES,
        "filters": {
            "admin_id": admin_id,
            "task_type": task_type,
            "status": status,
            "priority": priority,
        },
    }

    return render(request, "godmode/work_assignments.html", context)


# @login_required
# @user_passes_test(is_admin)
def work_assignment_detail(request, assignment_id):
    """
    Detailed view of a specific work assignment.
    """
    assignment = get_object_or_404(WorkAssignment, id=assignment_id)

    # Non-superusers can only view their own assignments
    if not request.user.is_superuser and assignment.admin != request.user:
        messages.error(request, "You do not have permission to view this assignment.")
        return redirect("godmode:work_assignments")

    # Get related object if available
    related_object = None
    if assignment.related_object_type and assignment.related_object_id:
        try:
            model = apps.get_model(assignment.related_object_type)
            related_object = model.objects.get(id=assignment.related_object_id)
        except (LookupError, model.DoesNotExist):
            pass

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "update_status":
            status = request.POST.get("status")
            notes = request.POST.get("notes", "")

            if status in [s[0] for s in WorkAssignment.STATUS_CHOICES]:
                assignment.status = status

                if notes:
                    if assignment.notes:
                        assignment.notes += f"\n\n{timezone.now().strftime('%Y-%m-%d %H:%M')} - {request.user.username}:\n{notes}"
                    else:
                        assignment.notes = f"{timezone.now().strftime('%Y-%m-%d %H:%M')} - {request.user.username}:\n{notes}"

                if status == "completed":
                    assignment.completed_at = timezone.now()

                assignment.save()

                messages.success(request, f"Assignment status updated to {status}.")
            else:
                messages.error(request, "Invalid status provided.")

        elif action == "reassign":
            admin_id = request.POST.get("admin_id")

            try:
                admin = User.objects.get(id=admin_id, role="admin")
                assignment.admin = admin
                assignment.save()

                messages.success(request, f"Assignment reassigned to {admin.username}.")
            except User.DoesNotExist:
                messages.error(request, "Invalid admin user selected.")

        return redirect("godmode:work_assignment_detail", assignment_id=assignment.id)

    # Get all admin users for reassignment
    admin_users = User.objects.filter(role="admin").order_by("username")

    context = {
        "assignment": assignment,
        "related_object": related_object,
        "admin_users": admin_users,
        "status_choices": WorkAssignment.STATUS_CHOICES,
    }

    return render(request, "godmode/work_assignment_detail.html", context)


# @login_required
# @user_passes_test(is_admin)
def create_work_assignment(request):
    """
    View to create a new work assignment.
    """
    if request.method == "POST":
        admin_id = request.POST.get("admin_id")
        title = request.POST.get("title")
        description = request.POST.get("description")
        task_type = request.POST.get("task_type")
        priority = request.POST.get("priority")
        due_date_str = request.POST.get("due_date")

        # Validate required fields
        if not all([admin_id, title, description, task_type, priority]):
            messages.error(request, "All required fields must be filled.")
            return redirect("godmode:create_work_assignment")

        try:
            admin = User.objects.get(id=admin_id, role="admin")
        except User.DoesNotExist:
            messages.error(request, "Invalid admin user selected.")
            return redirect("godmode:create_work_assignment")

        # Parse due date if provided
        due_date = None
        if due_date_str:
            try:
                due_date = datetime.strptime(due_date_str, "%Y-%m-%dT%H:%M")
            except ValueError:
                messages.error(request, "Invalid due date format.")
                return redirect("godmode:create_work_assignment")

        # Create the assignment
        assignment = WorkAssignment.objects.create(
            admin=admin,
            assigned_by=request.user,
            title=title,
            description=description,
            task_type=task_type,
            priority=priority,
            due_date=due_date,
            status="pending",
        )

        messages.success(request, f"Work assignment '{title}' created successfully.")
        return redirect("godmode:work_assignment_detail", assignment_id=assignment.id)

    # Get all admin users
    admin_users = User.objects.filter(role="admin").order_by("username")

    context = {
        "admin_users": admin_users,
        "task_types": WorkAssignment.TYPE_CHOICES,
        "priority_choices": WorkAssignment.PRIORITY_CHOICES,
    }

    return render(request, "godmode/create_work_assignment.html", context)


# @login_required
# @user_passes_test(is_admin)
def data_exports(request):
    """
    View to manage data exports.
    """
    # Get filter parameters
    model_name = request.GET.get("model_name")
    created_by_id = request.GET.get("created_by_id")

    # Base queryset
    configs = DataExportConfig.objects.all()

    # Apply filters
    if model_name:
        configs = configs.filter(model_name=model_name)

    if created_by_id:
        configs = configs.filter(created_by_id=created_by_id)

    # Non-superusers can only see their own configs
    if not request.user.is_superuser:
        configs = configs.filter(created_by=request.user)

    # Order by created_at (newest first)
    configs = configs.order_by("-created_at")

    # Get recent exports
    exports = DataExport.objects.all().order_by("-created_at")[:10]

    # Get available models for export
    available_models = []
    for app_config in apps.get_app_configs():
        if app_config.name in [
            "accounts",
            "jobs",
            "payment",
            "disputes",
            "gamification",
        ]:
            for model in app_config.get_models():
                available_models.append(
                    f"{model._meta.app_label}.{model._meta.model_name}"
                )

    # Get all users for the filter dropdown
    users = User.objects.all().order_by("username")

    context = {
        "configs": configs,
        "exports": exports,
        "available_models": sorted(available_models),
        "users": users,
        "filters": {
            "model_name": model_name,
            "created_by_id": created_by_id,
        },
    }

    return render(request, "godmode/data_exports.html", context)


# @login_required
# @user_passes_test(is_admin)
def create_export_config(request):
    """
    View to create a new data export configuration.
    """
    if request.method == "POST":
        name = request.POST.get("name")
        description = request.POST.get("description", "")
        model_name = request.POST.get("model_name")
        fields = request.POST.getlist("fields")

        # Validate required fields
        if not all([name, model_name, fields]):
            messages.error(
                request, "Name, model, and at least one field must be specified."
            )
            return redirect("godmode:create_export_config")

        # Validate model
        try:
            app_label, model_name_part = model_name.split(".")
            model = apps.get_model(app_label, model_name_part)
        except (ValueError, LookupError):
            messages.error(request, f"Invalid model: {model_name}")
            return redirect("godmode:create_export_config")

        # Validate fields
        valid_fields = []
        for field in fields:
            try:
                model._meta.get_field(field)
                valid_fields.append(field)
            except:
                pass

        if not valid_fields:
            messages.error(request, "No valid fields selected.")
            return redirect("godmode:create_export_config")

        # Create the config
        config = DataExportConfig.objects.create(
            name=name,
            description=description,
            model_name=model_name,
            fields=valid_fields,
            created_by=request.user,
        )

        messages.success(
            request, f"Export configuration '{name}' created successfully."
        )
        return redirect("godmode:data_exports")

    # Get available models for export
    available_models = []
    for app_config in apps.get_app_configs():
        if app_config.name in [
            "accounts",
            "jobs",
            "payment",
            "disputes",
            "gamification",
        ]:
            for model in app_config.get_models():
                available_models.append(
                    {
                        "name": f"{model._meta.app_label}.{model._meta.model_name}",
                        "verbose_name": model._meta.verbose_name,
                        "fields": [
                            {"name": field.name, "verbose_name": field.verbose_name}
                            for field in model._meta.fields
                        ],
                    }
                )

    context = {
        "available_models": sorted(available_models, key=lambda x: x["name"]),
    }

    return render(request, "godmode/create_export_config.html", context)


# @login_required
# @user_passes_test(is_admin)
def run_export(request, config_id):
    """
    View to run a data export using a configuration.
    """
    config = get_object_or_404(DataExportConfig, id=config_id)

    # Non-superusers can only use their own configs
    if not request.user.is_superuser and config.created_by != request.user:
        messages.error(
            request, "You do not have permission to use this export configuration."
        )
        return redirect("godmode:data_exports")

    if request.method == "POST":
        export_format = request.POST.get("format", "csv")

        # Create export record
        timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
        file_name = f"{config.model_name.replace('.', '_')}_{timestamp}.{export_format}"

        export = DataExport.objects.create(
            config=config,
            file_name=file_name,
            status="processing",
            created_by=request.user,
        )

        try:
            # Get model and data
            app_label, model_name = config.model_name.split(".")
            model = apps.get_model(app_label, model_name)

            # Apply filters if any
            queryset = model.objects.all()
            if config.filters:
                queryset = queryset.filter(**config.filters)

            # Count rows
            row_count = queryset.count()
            export.row_count = row_count

            # Generate export file
            if export_format == "csv":
                response = HttpResponse(content_type="text/csv")
                response["Content-Disposition"] = f'attachment; filename="{file_name}"'

                writer = csv.writer(response)

                # Write header row
                header = [
                    model._meta.get_field(field).verbose_name for field in config.fields
                ]
                writer.writerow(header)

                # Write data rows
                for obj in queryset:
                    row = []
                    for field in config.fields:
                        value = getattr(obj, field)
                        if callable(value):
                            value = value()
                        row.append(str(value))
                    writer.writerow(row)

            elif export_format == "xlsx":
                # Create a BytesIO object to store the Excel file
                output = io.BytesIO()

                # Create Excel workbook and worksheet
                workbook = xlsxwriter.Workbook(output)
                worksheet = workbook.add_worksheet()

                # Write header row
                for col, field in enumerate(config.fields):
                    worksheet.write(0, col, model._meta.get_field(field).verbose_name)

                # Write data rows
                for row_idx, obj in enumerate(queryset, start=1):
                    for col_idx, field in enumerate(config.fields):
                        value = getattr(obj, field)
                        if callable(value):
                            value = value()
                        worksheet.write(row_idx, col_idx, str(value))

                workbook.close()

                # Prepare response
                output.seek(0)
                response = HttpResponse(
                    output.read(),
                    content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
                response["Content-Disposition"] = f'attachment; filename="{file_name}"'

            # Update export record
            export.status = "completed"
            export.completed_at = timezone.now()
            export.save()

            # Update last used timestamp
            config.last_used = timezone.now()
            config.save()

            return response

        except Exception as e:
            export.status = "failed"
            export.error_message = str(e)
            export.save()

            messages.error(request, f"Error generating export: {str(e)}")
            return redirect("godmode:data_exports")

    context = {
        "config": config,
    }

    return render(request, "godmode/run_export.html", context)


# @login_required
# @user_passes_test(is_admin)
def user_rankings(request):
    """
    View to display user rankings and leaderboards.
    """
    ranking_type = request.GET.get("ranking_type", "points")

    # Get rankings for the selected type
    rankings = UserRanking.objects.filter(ranking_type=ranking_type).order_by("rank")

    # If no rankings exist, generate them
    if not rankings.exists():
        generate_rankings(request, ranking_type)
        rankings = UserRanking.objects.filter(ranking_type=ranking_type).order_by(
            "rank"
        )

    context = {
        "rankings": rankings,
        "ranking_type": ranking_type,
        "ranking_types": UserRanking.RANKING_TYPE_CHOICES,
    }

    return render(request, "godmode/user_rankings.html", context)


# @login_required
# @user_passes_test(is_admin)
def generate_rankings(request, ranking_type=None):
    """
    Generate or update user rankings for a specific type.
    """
    if not ranking_type:
        ranking_type = request.GET.get("ranking_type", "points")

    # Validate ranking type
    valid_types = [choice[0] for choice in UserRanking.RANKING_TYPE_CHOICES]
    if ranking_type not in valid_types:
        messages.error(request, f"Invalid ranking type: {ranking_type}")
        return redirect("godmode:user_rankings")

    try:
        # Get existing rankings to track changes
        existing_rankings = {
            ranking.user_id: {
                "rank": ranking.rank,
                "score": ranking.score,
            }
            for ranking in UserRanking.objects.filter(ranking_type=ranking_type)
        }

        # Calculate new rankings based on type
        if ranking_type == "points":
            # Rank by total gamification points
            user_scores = (
                UserActivity.objects.values("user")
                .annotate(total_points=Sum("points_earned"))
                .order_by("-total_points")
            )

        elif ranking_type == "payments":
            # Rank by total payment amount
            user_scores = (
                Payment.objects.filter(status="Completed")
                .values("payer")
                .annotate(total_amount=Sum("amount"))
                .order_by("-total_amount")
            )

        elif ranking_type == "jobs_created":
            # Rank by number of jobs created
            user_scores = (
                Job.objects.values("client")
                .annotate(job_count=Count("id"))
                .order_by("-job_count")
            )

        elif ranking_type == "jobs_completed":
            # Rank by number of jobs completed
            user_scores = (
                Application.objects.filter(status="Completed")
                .values("applicant")
                .annotate(completed_count=Count("id"))
                .order_by("-completed_count")
            )

        elif ranking_type == "applications":
            # Rank by number of applications submitted
            user_scores = (
                Application.objects.values("applicant")
                .annotate(app_count=Count("id"))
                .order_by("-app_count")
            )

        elif ranking_type == "activity":
            # Rank by activity level (login frequency and actions)
            user_scores = (
                UserActivityLog.objects.values("user")
                .annotate(activity_count=Count("id"))
                .order_by("-activity_count")
            )

        # Update or create rankings
        for rank, score_data in enumerate(user_scores, start=1):
            user_id = (
                score_data.get("user")
                or score_data.get("client")
                or score_data.get("applicant")
                or score_data.get("payer")
            )
            if not user_id:
                continue

            score_value = (
                score_data.get("total_points")
                or score_data.get("total_amount")
                or score_data.get("job_count")
                or score_data.get("completed_count")
                or score_data.get("app_count")
                or score_data.get("activity_count")
                or 0
            )

            # Get previous rank and score if available
            previous_rank = None
            previous_score = None
            if user_id in existing_rankings:
                previous_rank = existing_rankings[user_id]["rank"]
                previous_score = existing_rankings[user_id]["score"]

            # Calculate percentile (higher is better)
            percentile = None
            if len(user_scores) > 0:
                percentile = 100 - (rank / len(user_scores) * 100)

            # Update or create ranking
            UserRanking.objects.update_or_create(
                user_id=user_id,
                ranking_type=ranking_type,
                defaults={
                    "rank": rank,
                    "score": score_value,
                    "percentile": percentile,
                    "previous_rank": previous_rank,
                    "previous_score": previous_score,
                    "updated_at": timezone.now(),
                },
            )

        messages.success(
            request,
            f"Rankings for {dict(UserRanking.RANKING_TYPE_CHOICES)[ranking_type]} updated successfully.",
        )

    except Exception as e:
        messages.error(request, f"Error generating rankings: {str(e)}")

    return redirect("godmode:user_rankings")


# @login_required
# @user_passes_test(is_admin)
def delete_user(request, user_id):
    """
    View to delete a user account.
    """
    # Only superusers can delete users
    if not request.user.is_superuser:
        messages.error(request, "You do not have permission to delete users.")
        return redirect("godmode:dashboard")

    user = get_object_or_404(User, id=user_id)

    if request.method == "POST":
        confirmation = request.POST.get("confirmation")

        if confirmation == user.username:
            # Log the deletion
            UserActivityLog.objects.create(
                user=request.user,
                action_type="admin_action",
                details={
                    "action": "delete_user",
                    "deleted_user_id": user.id,
                    "deleted_username": user.username,
                    "deleted_email": user.email,
                    "deleted_role": user.role,
                },
            )

            # Delete the user
            user.delete()

            messages.success(request, f"User {user.username} has been deleted.")
            return redirect("godmode:dashboard")
        else:
            messages.error(request, "Confirmation text does not match the username.")

    context = {
        "user_obj": user,
    }

    return render(request, "godmode/delete_user.html", context)


# @login_required
# @user_passes_test(is_admin)
def security_dashboard(request):
    """
    Security and business insights dashboard with real-time monitoring.
    """
    # Get recent security-related activity
    security_activity = UserActivityLog.objects.filter(
        action_type__in=["login_failed", "admin_action"]
    ).order_by("-timestamp")[:20]

    # Get recent webhook errors
    webhook_errors = WebhookLog.objects.filter(status="error").order_by("-created_at")[
        :10
    ]

    # Get payment stats
    payment_stats = {
        "total": Payment.objects.count(),
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

    context = {
        "security_activity": security_activity,
        "webhook_errors": webhook_errors,
        "payment_stats": payment_stats,
    }

    return render(request, "godmode/security_dashboard.html", context)


@login_required
@user_passes_test(lambda u: u.is_superuser)
def cache_sync_view(request):
    """Cache synchronization view for manually syncing Redis cache with the database."""
    context = {
        "title": "Cache Synchronization",
        "active_tab": "cache_sync",
    }
    return render(request, "godmode/cache_sync.html", context)
