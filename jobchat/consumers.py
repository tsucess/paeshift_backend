import asyncio
import json
import logging
from datetime import datetime

# Define a custom channel layer function to work with newer channels version
def get_channel_layer():
    from channels.layers import get_channel_layer as gcl
    return gcl()

from channels.db import database_sync_to_async

# Import AsyncWebsocketConsumer directly from the module to 
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings
from django.contrib.auth import get_user_model

# Import models using string references to avoid circular import issues
from jobchat.models import LocationHistory, Message
from jobs.models import Job

logger = logging.getLogger(__name__)


# ✅ Function to fetch user model only when needed
def get_user():
    return get_user_model()


class ChatConsumer(AsyncWebsocketConsumer):
    """Handles real-time job chat messaging"""

    async def connect(self):
        self.job_id = self.scope["url_route"]["kwargs"]["job_id"]
        self.room_group_name = f"chat_{self.job_id}"
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()
        print(f"✅ Chat WebSocket connected for Job #{self.job_id}")

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
        print(f"❌ Chat WebSocket disconnected for Job #{self.job_id}")

    async def receive(self, text_data):
        """Handles incoming chat messages"""
        data = json.loads(text_data)
        message = data.get("message", "").strip()
        sender = self.scope["user"]

        if sender and sender.is_authenticated and message:
            await self.save_message(sender, message)  # ✅ Save to DB
            await self.channel_layer.group_send(
                self.room_group_name,
                {"type": "chat_message", "message": message, "sender": sender.username},
            )

    async def chat_message(self, event):
        """Sends chat messages to all connected users"""
        sender = event.get("sender", "Anonymous")
        message = event.get("message", "[No message]")
        await self.send(text_data=json.dumps({"sender": sender, "message": message}))

    @database_sync_to_async
    def save_message(self, sender, message):
        """Saves the message in the database"""
        job = Job.objects.get(id=self.job_id)
        return Message.objects.create(job=job, sender=sender, content=message)


class JobLocationConsumer(AsyncWebsocketConsumer):
    """Handles real-time job location tracking"""

    async def connect(self):
        self.job_id = self.scope["url_route"]["kwargs"]["job_id"]
        self.group_name = f"job_{self.job_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        logger.info(f"Location WebSocket connected: {self.channel_name}")

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)
        logger.info(f"Location WebSocket disconnected: {self.channel_name}")

    async def receive(self, text_data):
        """Processes received location data"""
        data = json.loads(text_data)

        if data.get("type") == "heartbeat":
            await self.send(text_data=json.dumps({"type": "heartbeat_ack"}))
            return

        user = self.scope.get("user")
        latitude = data.get("latitude")
        longitude = data.get("longitude")

        if user and user.is_authenticated and latitude and longitude:
            await self.process_location(user, latitude, longitude)

    async def process_location(self, user, latitude, longitude):
        """Saves or updates the user's location"""
        current_time = datetime.utcnow()
        last_location = await self.get_last_location(user)

        if (
            last_location
            and last_location.latitude == latitude
            and last_location.longitude == longitude
        ):
            await self.update_last_location_time(last_location, current_time)
        else:
            await self.save_location(user, latitude, longitude, current_time)

        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "location_update",
                "latitude": latitude,
                "longitude": longitude,
                "user": user.username,
            },
        )

    async def location_update(self, event):
        """Sends updated location data to frontend"""
        await self.send(text_data=json.dumps(event))

    @database_sync_to_async
    def get_last_location(self, user):
        """Gets the last recorded location of the user"""
        return LocationHistory.objects.filter(user=user).order_by("-timestamp").first()

    @database_sync_to_async
    def save_location(self, user, lat, lon, timestamp):
        """Saves user location to the database"""
        job = Job.objects.get(id=self.job_id)
        return LocationHistory.objects.create(
            job=job, user=user, latitude=lat, longitude=lon, timestamp=timestamp
        )

    @database_sync_to_async
    def update_last_location_time(self, last_location, new_timestamp):
        """Updates the timestamp of the last saved location"""
        last_location.timestamp = new_timestamp
        last_location.save()


class JobMatchingConsumer(AsyncWebsocketConsumer):
    """Handles real-time job matching and updates."""

    async def connect(self):
        """Handles WebSocket connection."""
        self.user = self.scope["user"]
        if self.user.is_authenticated:
            self.room_group_name = f"user_{self.user.id}"
            await self.channel_layer.group_add(self.room_group_name, self.channel_name)
            await self.accept()
            logger.info(f"✅ {self.user.username} connected to Job Matching WebSocket.")
        else:
            await self.close()

    async def disconnect(self, close_code):
        """Handles WebSocket disconnection."""
        if self.user.is_authenticated:
            await self.channel_layer.group_discard(
                self.room_group_name, self.channel_name
            )
            logger.info(
                f"❌ {self.user.username} disconnected from Job Matching WebSocket."
            )

    async def receive(self, text_data):
        """Handles incoming WebSocket messages."""
        data = json.loads(text_data)
        action = data.get("action")

        if action == "subscribe_jobs":
            await self.handle_job_subscription()
        elif action == "update_location":
            await self.handle_location_update(data)

    async def handle_job_subscription(self):
        """Sends nearby job listings to the user."""
        jobs = await self.get_nearby_jobs(self.user)
        await self.send(text_data=json.dumps({"type": "job_list", "jobs": jobs}))

    async def handle_location_update(self, data):
        """Updates user location and sends matched jobs."""
        latitude = data.get("latitude")
        longitude = data.get("longitude")

        if latitude and longitude:
            await self.update_user_location(self.user, latitude, longitude)

            # Send new job matches based on updated location
            jobs = await self.get_nearby_jobs(self.user)
            await self.channel_layer.group_send(
                self.room_group_name, {"type": "job_match_update", "jobs": jobs}
            )

    async def job_match_update(self, event):
        """Sends updated job match data to the frontend."""
        # Save the notification to the database
        await self.save_notification(event["message"])

        # Send the notification to the client
        await self.send(text_data=json.dumps(event))

    @database_sync_to_async
    def get_nearby_jobs(self, user):
        """Fetches jobs near the user's location."""
        user_location = LocationHistory.objects.filter(user=user).last()
        if not user_location:
            return []

        jobs = Job.objects.filter(status="upcoming")
        job_list = []
        for job in jobs:
            distance = self.calculate_distance(
                user_location.latitude,
                user_location.longitude,
                job.latitude,
                job.longitude,
            )
            if distance <= 50:  # 50km radius
                job_list.append(
                    {
                        "id": job.id,
                        "title": job.title,
                        "shift_type": job.shift_type,
                        "rate": job.rate,
                        "distance": round(distance, 2),
                    }
                )

        return sorted(job_list, key=lambda x: x["distance"])

    @database_sync_to_async
    def update_user_location(self, user, latitude, longitude):
        """Saves user location to the database."""
        return LocationHistory.objects.update_or_create(
            user=user,
            defaults={
                "latitude": latitude,
                "longitude": longitude,
                "timestamp": datetime.utcnow(),
            },
        )

    def calculate_distance(self, lat1, lon1, lat2, lon2):
        """Haversine formula to calculate distance between two locations."""
        from math import atan2, cos, radians, sin, sqrt

        R = 6371.0  # Radius of Earth in km
        dlat = radians(lat2 - lat1)
        dlon = radians(lon2 - lon1)
        a = (
            sin(dlat / 2) ** 2
            + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
        )
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        return R * c  # Distance in km

    @database_sync_to_async
    def save_notification(self, message):
        """Save the notification to the database"""
        from .models import Notification  # Import Notification model

        Notification.objects.create(user=self.user, message=message)


class JobApplicationConsumer(AsyncWebsocketConsumer):
    """Handles real-time job application notifications"""

    async def connect(self):
        """Connect employer to job application notifications"""
        self.job_id = self.scope["url_route"]["kwargs"]["job_id"]
        self.group_name = f"job_applications_{self.job_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        """Disconnect employer from job notifications"""
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        """Handle new applicant notifications"""
        data = json.loads(text_data)
        applicant_id = data.get("applicant_id")

        if applicant_id:
            applicant = await self.get_applicant(applicant_id)
            if applicant:
                await self.channel_layer.group_send(
                    self.group_name,
                    {
                        "type": "application_notification",
                        "applicant": {"id": applicant.id, "name": applicant.username},
                    },
                )

    async def application_notification(self, event):
        """Send new applicant notification to the employer"""
        message = event.get(
            "message", "New applicant applied!"
        )  # Default message if not provided
        await self.save_notification(message)  # Save the notification to the database
        await self.send(
            text_data=json.dumps(event)
        )  # Send the notification to the client

    @database_sync_to_async
    def save_notification(self, message):
        """Save the notification to the database"""
        from .models import Notification  # Import Notification model

        Notification.objects.create(user=self.user, message=message)


class PaymentNotificationConsumer(AsyncWebsocketConsumer):
    """Handles real-time payment success notifications"""

    async def connect(self):
        """Connect user to their payment notifications"""
        self.user = self.scope["user"]
        if self.user.is_authenticated:
            self.group_name = f"user_payments_{self.user.id}"
            await self.channel_layer.group_add(self.group_name, self.channel_name)
            await self.accept()
        else:
            await self.close()

    async def disconnect(self, close_code):
        """Disconnect user from payment notifications"""
        if self.user.is_authenticated:
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def payment_success(self, event):
        """Send payment success notification to user"""
        # Save the notification to the database
        await self.save_notification(event["message"])

        # Send the notification to the client
        await self.send(text_data=json.dumps(event))

    @database_sync_to_async
    def save_notification(self, message):
        """Save the notification to the database"""
        from .models import Notification  # Import Notification model

        Notification.objects.create(user=self.user, message=message)

    """Handles real-time payment success notifications"""

    async def connect(self):
        """Connect user to their payment notifications"""
        self.user = self.scope["user"]
        if self.user.is_authenticated:
            self.group_name = f"user_payments_{self.user.id}"
            await self.channel_layer.group_add(self.group_name, self.channel_name)
            await self.accept()
        else:
            await self.close()

    async def disconnect(self, close_code):
        """Disconnect user from payment notifications"""
        if self.user.is_authenticated:
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def payment_success(self, event):
        """Send payment success notification to user"""
        await self.send(text_data=json.dumps(event))

    @database_sync_to_async
    def get_user_profile(self):
        """Fetch user profile from database"""
        User = get_user_model()
        return User.objects.get(id=self.user.id)
