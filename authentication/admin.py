from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from .models import (
    User, UserProfile, Address, Role, UserRole, 
    LoginAttempt, PasswordResetToken, EmailVerificationToken
)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('email', 'username', 'first_name', 'last_name', 'is_verified', 'is_active', 'date_joined')
    list_filter = ('is_verified', 'is_active', 'is_staff', 'date_joined')
    search_fields = ('email', 'username', 'first_name', 'last_name')
    ordering = ('-date_joined',)
    
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Additional Info', {
            'fields': ('phone_number', 'date_of_birth', 'is_verified', 'avatar', 'bio', 'last_login_ip')
        }),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'username', 'password1', 'password2', 'first_name', 'last_name'),
        }),
    )


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'newsletter_subscribed', 'marketing_consent', 'created_at')
    list_filter = ('newsletter_subscribed', 'marketing_consent', 'created_at')
    search_fields = ('user__email', 'user__username')
    raw_id_fields = ('user',)


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ('user', 'type', 'first_name', 'last_name', 'city', 'state', 'is_default')
    list_filter = ('type', 'is_default', 'country', 'state')
    search_fields = ('user__email', 'first_name', 'last_name', 'city')
    raw_id_fields = ('user',)


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'description')
    filter_horizontal = ('permissions',)


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'assigned_by', 'assigned_at', 'expires_at', 'is_active')
    list_filter = ('role', 'is_active', 'assigned_at', 'expires_at')
    search_fields = ('user__email', 'role__name')
    raw_id_fields = ('user', 'assigned_by')
    date_hierarchy = 'assigned_at'


@admin.register(LoginAttempt)
class LoginAttemptAdmin(admin.ModelAdmin):
    list_display = ('email', 'ip_address', 'success', 'failure_reason', 'timestamp')
    list_filter = ('success', 'timestamp')
    search_fields = ('email', 'ip_address')
    date_hierarchy = 'timestamp'
    readonly_fields = ('email', 'ip_address', 'user_agent', 'success', 'failure_reason', 'timestamp')
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False


@admin.register(PasswordResetToken)
class PasswordResetTokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'expires_at', 'used', 'created_at')
    list_filter = ('used', 'expires_at', 'created_at')
    search_fields = ('user__email',)
    raw_id_fields = ('user',)
    readonly_fields = ('token', 'created_at')


@admin.register(EmailVerificationToken)
class EmailVerificationTokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'expires_at', 'used', 'created_at')
    list_filter = ('used', 'expires_at', 'created_at')
    search_fields = ('user__email',)
    raw_id_fields = ('user',)
    readonly_fields = ('token', 'created_at')