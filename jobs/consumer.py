

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
