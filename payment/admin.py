from django.contrib import admin
from django.urls import path, reverse
from django.utils.html import format_html

from .models import Payment, Wallet, Transaction  # Removed EscrowPayment - doesn't exist


class PaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'pay_code', 'payer', 'recipient', 'original_amount', 'status', 'created_at', 'payment_method')
    list_filter = ('status', 'payment_method', 'created_at')
    search_fields = ('pay_code', 'payer__email', 'recipient__email')
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('webhook-dashboard/', self.admin_site.admin_view(self.webhook_dashboard_view), name='payment_webhook_dashboard'),
        ]
        return custom_urls + urls

    def webhook_dashboard_view(self, request):
        from .admin_views import webhook_dashboard
        return webhook_dashboard(request)

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['webhook_dashboard_url'] = reverse('admin:payment_webhook_dashboard')
        return super().changelist_view(request, extra_context=extra_context)


class WalletAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'balance')
    search_fields = ('user__email', 'user__username')




class TransactionAdmin(admin.ModelAdmin):
    list_display = ('id', 'wallet', 'amount', 'transaction_type', 'created_at')
    list_filter = ('transaction_type', 'created_at')
    search_fields = ('wallet__user__email', 'description')
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'


admin.site.register(Payment, PaymentAdmin)
admin.site.register(Wallet, WalletAdmin)
admin.site.register(Transaction, TransactionAdmin)
