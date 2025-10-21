import reflex as rx


class PaymentState(rx.State):
    payments = []
    filter = "all"

    async def fetch_payments(self, filter: str = "all"):
        """Fetch payments from Django Ninja API."""
        import httpx

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"http://127.0.0.1:8000/api/payments?filter={filter}"
            )
            if response.status_code == 200:
                self.payments = response.json()["payments"]
                self.filter = filter


def payment_page() -> rx.Component:
    return rx.center(
        rx.vstack(
            rx.heading("Payment Records", size="lg"),
            rx.hstack(
                rx.button("All", on_click=lambda: PaymentState.fetch_payments("all")),
                rx.button(
                    "Today", on_click=lambda: PaymentState.fetch_payments("today")
                ),
                rx.button(
                    "Yesterday",
                    on_click=lambda: PaymentState.fetch_payments("yesterday"),
                ),
                rx.button(
                    "This Week",
                    on_click=lambda: PaymentState.fetch_payments("this_week"),
                ),
                rx.button(
                    "Last Week",
                    on_click=lambda: PaymentState.fetch_payments("last_week"),
                ),
                rx.button(
                    "This Month",
                    on_click=lambda: PaymentState.fetch_payments("this_month"),
                ),
                spacing="4",
            ),
            rx.box(height="2em"),  # Spacer
            rx.foreach(
                PaymentState.payments,
                lambda payment: rx.card(
                    rx.text(f"💵 Amount: {payment['amount']}"),
                    rx.text(f"🕒 Created At: {payment['created_at']}"),
                    rx.text(f"✅ Status: {payment['status']}"),
                    padding="4",
                    border_radius="2xl",
                    shadow="md",
                    margin_y="2",
                ),
            ),
        ),
        padding="8",
    )
