import json
import logging
from datetime import datetime

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404

from jobchat.models import LocationHistory, Message
from jobs.models import Job

logger = logging.getLogger(__name__)

User = get_user_model()


# ==
# ✅ BASE WEBSOCKET CONSUMER
# ==
class BaseWebSocketConsumer(AsyncWebsocketConsumer):
    """Base WebSocket Consumer with common utilities."""

    async def connect(self):
        """Handles WebSocket connection."""
        self.user = self.scope["user"]
        if self.user.is_authenticated:
            await self.channel_layer.group_add(self.group_name, self.channel_name)
            await self.accept()
            logger.info(
                f"✅ {self.user.username} connected to {self.__class__.__name__}"
            )
        else:
            await self.close()

    async def disconnect(self, close_code):
        """Handles WebSocket disconnection."""
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)


# ==
# ✅ JOB MATCHING CONSUMER
# ==
class JobMatchingConsumer(BaseWebSocketConsumer):
    """Handles real-time job matching and updates."""

    async def connect(self):
        self.group_name = f"user_{self.scope['user'].id}"
        await super().connect()

    async def receive(self, text_data):
        """Handles incoming WebSocket messages."""
        data = json.loads(text_data)
        if data.get("action") == "subscribe_jobs":
            await self.send_nearby_jobs()

    async def send_nearby_jobs(self):
        """Sends nearby job listings to the user."""
        jobs = await self.get_nearby_jobs(self.user)
        await self.send(text_data=json.dumps({"type": "job_list", "jobs": jobs}))

    @database_sync_to_async
    def get_nearby_jobs(self, user):
        """Fetches jobs near the user's location."""
        user_location = LocationHistory.objects.filter(user=user).last()
        if not user_location:
            return []

        jobs = Job.objects.filter(status="upcoming").values(
            "id", "title", "shift_type", "rate"
        )
        return list(jobs)


# ==
# ✅ JOB APPLICATION CONSUMER
# ==
class JobApplicationConsumer(BaseWebSocketConsumer):
    """Handles real-time job application notifications."""

    async def connect(self):
        self.job_id = self.scope["url_route"]["kwargs"]["job_id"]
        self.group_name = f"job_applications_{self.job_id}"
        await super().connect()

    async def job_notification(self, event):
        """Sends job application notifications."""
        await self.send(text_data=json.dumps(event))


# ==
# ✅ PAYMENT NOTIFICATION CONSUMER
# ==
class PaymentNotificationConsumer(BaseWebSocketConsumer):
    """Handles real-time payment success notifications."""

    async def connect(self):
        self.group_name = f"user_payments_{self.scope['user'].id}"
        await super().connect()

    async def payment_success(self, event):
        """Sends payment success notifications."""
        await self.send(text_data=json.dumps(event))


import json
import logging
from datetime import datetime

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404

from jobchat.models import LocationHistory, Message
from jobs.models import Job

logger = logging.getLogger(__name__)

User = get_user_model()


# ==
# ✅ BASE WEBSOCKET CONSUMER
# ==
class BaseWebSocketConsumer(AsyncWebsocketConsumer):
    """Base WebSocket Consumer with common utilities."""

    async def connect(self):
        """Handles WebSocket connection."""
        self.user = self.scope["user"]
        if self.user.is_authenticated:
            await self.channel_layer.group_add(self.group_name, self.channel_name)
            await self.accept()
            logger.info(
                f"✅ {self.user.username} connected to {self.__class__.__name__}"
            )
        else:
            await self.close()

    async def disconnect(self, close_code):
        """Handles WebSocket disconnection."""
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)



# ==
# ✅ PAYMENT NOTIFICATION CONSUMER
# ==
class PaymentNotificationConsumer(BaseWebSocketConsumer):
    """Handles real-time payment success notifications."""

    async def connect(self):
        self.group_name = f"user_payments_{self.scope['user'].id}"
        await super().connect()

    async def payment_success(self, event):
        """Sends payment success notifications."""
        await self.send(text_data=json.dumps(event))
