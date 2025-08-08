from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Sum, Count
from .models import (
    PaymentProvider, PaymentMethod, Payment, Refund, Subscription,
    Invoice, PaymentWebhook, PaymentDispute
)
from django.utils import timezone


@admin.register(PaymentProvider)
class PaymentProviderAdmin(admin.ModelAdmin):
    list_display = ('name', 'provider_type', 'is_active', 'supports_credit_cards',
                   'supports_debit_cards', 'processing_fee_percentage', 'created_at')
    list_filter = ('provider_type', 'is_active', 'supports_credit_cards', 'supports_debit_cards')
    search_fields = ('name', 'provider_type')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'provider_type', 'is_active')
        }),
        ('Configuration', {
            'fields': ('api_key', 'secret_key', 'webhook_secret', 'config'),
            'classes': ('collapse',)
        }),
        ('Supported Features', {
            'fields': ('supports_credit_cards', 'supports_debit_cards', 'supports_bank_transfers',
                      'supports_digital_wallets', 'supports_cryptocurrency')
        }),
        ('Processing Fees', {
            'fields': ('processing_fee_percentage', 'processing_fee_fixed')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ('customer_id', 'method_type', 'card_display', 'provider', 'is_default', 'is_active')
    list_filter = ('method_type', 'is_default', 'is_active', 'provider', 'created_at')
    search_fields = ('customer_id', 'card_last4', 'provider__name')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Customer Information', {
            'fields': ('customer_id', 'method_type', 'provider')
        }),
        ('Card Information', {
            'fields': ('card_last4', 'card_brand', 'card_exp_month', 'card_exp_year'),
            'classes': ('collapse',)
        }),
        ('Provider Data', {
            'fields': ('provider_payment_method_id', 'provider_customer_id'),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('is_default', 'is_active')
        }),
        ('Additional Data', {
            'fields': ('billing_address', 'metadata'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def card_display(self, obj):
        if obj.card_last4:
            return f"{obj.card_brand.title()} ****{obj.card_last4}"
        return obj.get_method_type_display()
    card_display.short_description = 'Card'


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('transaction_id', 'order_id', 'amount', 'currency', 'status', 'provider', 'created_at')
    list_filter = ('status', 'currency', 'provider', 'created_at')
    search_fields = ('transaction_id', 'order_id', 'provider_payment_id')
    readonly_fields = ('transaction_id', 'created_at', 'updated_at', 'authorized_at', 'captured_at',
                      'failed_at', 'refunded_at')
    
    fieldsets = (
        ('Payment Information', {
            'fields': ('transaction_id', 'order_id', 'payment_method', 'provider')
        }),
        ('Amount and Currency', {
            'fields': ('amount', 'currency', 'description')
        }),
        ('Status Tracking', {
            'fields': ('status', 'intent_status')
        }),
        ('Provider Data', {
            'fields': ('provider_payment_id', 'provider_intent_id', 'provider_charge_id'),
            'classes': ('collapse',)
        }),
        ('Gateway Response', {
            'fields': ('gateway_response', 'error_message', 'error_code'),
            'classes': ('collapse',)
        }),
        ('Fees and Amounts', {
            'fields': ('processing_fee', 'tax_amount', 'refunded_amount')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'authorized_at', 'captured_at', 'failed_at', 'refunded_at'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
    )


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = ('id', 'payment', 'amount', 'currency', 'reason', 'status', 'created_at')
    list_filter = ('status', 'reason', 'currency', 'created_at')
    search_fields = ('payment__transaction_id', 'provider_refund_id')
    readonly_fields = ('created_at', 'updated_at', 'processed_at')
    
    fieldsets = (
        ('Refund Information', {
            'fields': ('payment', 'amount', 'currency', 'reason', 'description')
        }),
        ('Status', {
            'fields': ('status',)
        }),
        ('Provider Data', {
            'fields': ('provider_refund_id', 'gateway_response', 'error_message'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'processed_at'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
    )


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('name', 'customer_id', 'amount', 'currency', 'interval', 'status', 'current_period_end')
    list_filter = ('status', 'interval', 'currency', 'created_at')
    search_fields = ('name', 'customer_id', 'provider_subscription_id')
    readonly_fields = ('created_at', 'updated_at', 'canceled_at')
    
    fieldsets = (
        ('Subscription Information', {
            'fields': ('name', 'description', 'customer_id', 'payment_method', 'provider')
        }),
        ('Billing Details', {
            'fields': ('amount', 'currency', 'interval', 'interval_count')
        }),
        ('Status and Dates', {
            'fields': ('status', 'current_period_start', 'current_period_end', 'trial_start', 'trial_end')
        }),
        ('Provider Data', {
            'fields': ('provider_subscription_id', 'provider_customer_id'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'canceled_at'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
    )


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('number', 'subscription', 'amount', 'currency', 'status', 'due_date')
    list_filter = ('status', 'currency', 'due_date', 'created_at')
    search_fields = ('number', 'subscription__name', 'provider_invoice_id')
    readonly_fields = ('number', 'created_at', 'updated_at', 'paid_at')
    
    fieldsets = (
        ('Invoice Information', {
            'fields': ('number', 'subscription', 'payment', 'amount', 'currency', 'description')
        }),
        ('Status and Dates', {
            'fields': ('status', 'due_date', 'paid_at')
        }),
        ('Provider Data', {
            'fields': ('provider_invoice_id',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
    )


@admin.register(PaymentWebhook)
class PaymentWebhookAdmin(admin.ModelAdmin):
    list_display = ('provider', 'event_type', 'status', 'received_at')
    list_filter = ('provider', 'event_type', 'status', 'received_at')
    search_fields = ('provider__name', 'event_type', 'provider_event_id')
    readonly_fields = ('received_at', 'processed_at')
    
    fieldsets = (
        ('Webhook Information', {
            'fields': ('provider', 'event_type', 'provider_event_id')
        }),
        ('Status', {
            'fields': ('status', 'error_message')
        }),
        ('Payload', {
            'fields': ('raw_payload', 'processed_payload'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('received_at', 'processed_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(PaymentDispute)
class PaymentDisputeAdmin(admin.ModelAdmin):
    list_display = ('payment', 'amount', 'currency', 'reason', 'status', 'created_at')
    list_filter = ('status', 'reason', 'currency', 'created_at')
    search_fields = ('payment__transaction_id', 'provider_dispute_id')
    readonly_fields = ('created_at', 'updated_at', 'closed_at')
    
    fieldsets = (
        ('Dispute Information', {
            'fields': ('payment', 'provider_dispute_id', 'amount', 'currency', 'reason', 'description')
        }),
        ('Status', {
            'fields': ('status', 'response_deadline')
        }),
        ('Evidence', {
            'fields': ('evidence',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'closed_at'),
            'classes': ('collapse',)
        }),
    )


# Custom admin actions
class PaymentAdminWithActions(PaymentAdmin):
    actions = ['mark_as_succeeded', 'mark_as_failed', 'mark_as_refunded']
    
    def mark_as_succeeded(self, request, queryset):
        updated = queryset.update(status='succeeded', captured_at=timezone.now())
        self.message_user(request, f'{updated} payments marked as succeeded.')
    mark_as_succeeded.short_description = "Mark selected payments as succeeded"
    
    def mark_as_failed(self, request, queryset):
        updated = queryset.update(status='failed', failed_at=timezone.now())
        self.message_user(request, f'{updated} payments marked as failed.')
    mark_as_failed.short_description = "Mark selected payments as failed"
    
    def mark_as_refunded(self, request, queryset):
        updated = queryset.update(status='refunded', refunded_at=timezone.now())
        self.message_user(request, f'{updated} payments marked as refunded.')
    mark_as_refunded.short_description = "Mark selected payments as refunded"


class RefundAdminWithActions(RefundAdmin):
    actions = ['mark_as_succeeded', 'mark_as_failed']
    
    def mark_as_succeeded(self, request, queryset):
        updated = queryset.update(status='succeeded', processed_at=timezone.now())
        self.message_user(request, f'{updated} refunds marked as succeeded.')
    mark_as_succeeded.short_description = "Mark selected refunds as succeeded"
    
    def mark_as_failed(self, request, queryset):
        updated = queryset.update(status='failed')
        self.message_user(request, f'{updated} refunds marked as failed.')
    mark_as_failed.short_description = "Mark selected refunds as failed"


class SubscriptionAdminWithActions(SubscriptionAdmin):
    actions = ['cancel_subscriptions']
    
    def cancel_subscriptions(self, request, queryset):
        updated = queryset.update(status='canceled', canceled_at=timezone.now())
        self.message_user(request, f'{updated} subscriptions cancelled.')
    cancel_subscriptions.short_description = "Cancel selected subscriptions"

# Re-register models with actions
admin.site.unregister(Payment)
admin.site.register(Payment, PaymentAdminWithActions)

admin.site.unregister(Refund)
admin.site.register(Refund, RefundAdminWithActions)

admin.site.unregister(Subscription)
admin.site.register(Subscription, SubscriptionAdminWithActions)
