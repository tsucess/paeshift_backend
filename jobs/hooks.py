import json
import logging

from django.utils.timezone import now
from django_q.models import Failure

logger = logging.getLogger(__name__)


def handle_geocode_result(task):
    """Robust task result handler with enhanced error protection"""
    log_data = {
        "task_id": task.id,
        "function": task.func,
        "status": "unknown",
        "job_id": None,
        "errors": [],
        "timestamp": now().isoformat(),
    }

    try:
        # Safely parse arguments
        try:
            if task.args and len(task.args) > 0:
                job_id = task.args[0]
                log_data["job_id"] = job_id
            else:
                logger.error("No job ID provided in task arguments")
                return
        except Exception as e:
            log_data["errors"].append(f"Argument parsing error: {str(e)}")
            logger.error(f"Failed to parse task arguments: {str(e)}")
            return

        # Process task result
        result = task.result

        # Handle different result types
        if isinstance(result, dict):
            log_data.update(
                {
                    "status": result.get("status", "unknown"),
                    "provider": result.get("provider"),
                    "coordinates": {
                        "lat": result.get("latitude"),
                        "lng": result.get("longitude"),
                    },
                }
            )

            if "error" in result:
                log_data["errors"].append(result["error"])

            # Only validate job_id if it exists in the result
            if "job_id" in result and log_data["job_id"] != result.get("job_id"):
                log_data["errors"].append("Job ID mismatch between task and result")

        elif isinstance(result, str):
            # Try to parse string as JSON
            try:
                json_result = json.loads(result)
                if isinstance(json_result, dict):
                    log_data.update(
                        {
                            "status": json_result.get("status", "unknown"),
                            "provider": json_result.get("provider"),
                            "coordinates": {
                                "lat": json_result.get("latitude"),
                                "lng": json_result.get("longitude"),
                            },
                        }
                    )
                    if "error" in json_result:
                        log_data["errors"].append(json_result["error"])
                else:
                    log_data["errors"].append(
                        f"Unexpected JSON result format: {json_result}"
                    )
            except json.JSONDecodeError:
                log_data["errors"].append(
                    f"Unexpected string result (not JSON): {result}"
                )
        else:
            log_data["errors"].append(f"Invalid result type: {type(result)}")

        # Handle logging based on status
        if log_data["status"] == "success" and not log_data["errors"]:
            logger.info(
                f"Geocoding successful for job {job_id}: {json.dumps(log_data)}"
            )

            # Update the job with coordinates if available
            try:
                from jobs.models import Job

                if log_data["coordinates"]["lat"] and log_data["coordinates"]["lng"]:
                    job = Job.objects.get(id=job_id)
                    job.latitude = log_data["coordinates"]["lat"]
                    job.longitude = log_data["coordinates"]["lng"]
                    job.save(update_fields=["latitude", "longitude"])
                    logger.info(
                        f"Updated job {job_id} with coordinates: {job.latitude}, {job.longitude}"
                    )
            except Exception as job_update_error:
                logger.error(
                    f"Failed to update job with coordinates: {str(job_update_error)}"
                )
        else:
            error_msg = (
                ", ".join(log_data["errors"]) if log_data["errors"] else "Unknown error"
            )
            logger.error(f"Geocoding failed for job {job_id}: {error_msg}")

            # Record the failure
            Failure.objects.create(
                name=task.func,
                args=str(task.args)[:500],
                kwargs=str(task.kwargs)[:500],
                result=json.dumps(log_data)[:500],
                started=task.started,
                stopped=now(),
            )

    except Exception as e:
        logger.critical(f"Hook system failure: {str(e)}", exc_info=True)
