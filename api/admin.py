from django.contrib import admin, messages
from django.utils.html import format_html
from .models import Payment, Prediction, Profile


@admin.action(description='Approve selected payments and grant access')
def approve_payments(modeladmin, request, queryset):
    count = 0
    for payment in queryset.exclude(status='approved'):
        payment.approve(request.user)
        count += 1
    modeladmin.message_user(request, f'Approved {count} payment(s). Access has been granted.', messages.SUCCESS)


@admin.action(description='Reject selected payments')
def reject_payments(modeladmin, request, queryset):
    count = 0
    for payment in queryset.filter(status='pending'):
        payment.reject(request.user, note='Rejected by admin')
        count += 1
    modeladmin.message_user(request, f'Rejected {count} payment(s).', messages.WARNING)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone', 'registration_approved', 'diamonds', 'football_unlocked', 'bottle_unlocked')
    list_filter = ('registration_approved', 'football_unlocked', 'bottle_unlocked')
    search_fields = ('user__email', 'user__first_name', 'phone')
    readonly_fields = ('registration_approved', 'football_unlocked', 'bottle_unlocked', 'diamonds')


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'user', 'kind', 'country', 'sender_name', 'paid_from', 'status', 'screenshot_preview')
    list_filter = ('status', 'kind', 'country')
    search_fields = ('user__email', 'sender_name', 'paid_from', 'transaction_id')
    readonly_fields = ('created_at', 'reviewed_at', 'reviewed_by', 'screenshot_preview')
    actions = [approve_payments, reject_payments]
    list_editable = ()

    fieldsets = (
        ('User', {'fields': ('user', 'kind', 'status')}),
        ('Payment proof', {'fields': ('country', 'amount', 'transaction_id', 'sender_name', 'paid_from', 'screenshot', 'screenshot_preview')}),
        ('Review', {'fields': ('admin_note', 'reviewed_at', 'reviewed_by')}),
    )

    @admin.display(description='Proof')
    def screenshot_preview(self, obj):
        if not obj.screenshot:
            return '—'
        return format_html(
            '<a href="{}" target="_blank" rel="noopener"><img src="{}" alt="Payment proof" style="height:64px;border-radius:8px;object-fit:cover" /></a>',
            obj.screenshot.url,
            obj.screenshot.url,
        )

    def save_model(self, request, obj, form, change):
        if change:
            previous = Payment.objects.get(pk=obj.pk)
            if obj.status == 'approved' and previous.status != 'approved':
                obj.status = previous.status
                super().save_model(request, obj, form, change)
                obj.approve(request.user)
                return
            if obj.status == 'rejected' and previous.status == 'pending':
                note = obj.admin_note
                obj.status = previous.status
                super().save_model(request, obj, form, change)
                obj.reject(request.user, note)
                return
        super().save_model(request, obj, form, change)


@admin.register(Prediction)
class PredictionAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'user', 'game', 'cost')
    list_filter = ('game',)
    search_fields = ('user__email',)
