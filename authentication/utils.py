import secrets
import hashlib
from datetime import datetime, timedelta
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken
from .models import PasswordResetToken, EmailVerificationToken, LoginAttempt


User = get_user_model()


def generate_token():
    """Generate a secure random token"""
    return secrets.token_urlsafe(32)


def generate_jwt_tokens(user):
    """Generate JWT access and refresh tokens for user"""
    refresh = RefreshToken.for_user(user)
    return {
        'access': str(refresh.access_token),
        'refresh': str(refresh)
    }


def generate_verification_token(user):
    """Generate email verification token"""
    token = generate_token()
    expires_at = timezone.now() + timedelta(days=1)
    
    # Delete any existing tokens
    EmailVerificationToken.objects.filter(user=user).delete()
    
    # Create new token
    verification_token = EmailVerificationToken.objects.create(
        user=user,
        token=token,
        expires_at=expires_at
    )
    
    return verification_token


def generate_password_reset_token(user):
    """Generate password reset token"""
    token = generate_token()
    expires_at = timezone.now() + timedelta(hours=2)
    
    # Delete any existing tokens
    PasswordResetToken.objects.filter(user=user).delete()
    
    # Create new token
    reset_token = PasswordResetToken.objects.create(
        user=user,
        token=token,
        expires_at=expires_at
    )
    
    return reset_token


def send_verification_email(user):
    """Send email verification email"""
    token_obj = generate_verification_token(user)
    
    verification_url = f"{settings.FRONTEND_URL}/verify-email?token={token_obj.token}"
    
    subject = 'Verify your email address'
    message = f'''
    Hi {user.first_name},
    
    Please click the link below to verify your email address:
    {verification_url}
    
    This link will expire in 24 hours.
    
    If you didn't create an account, please ignore this email.
    
    Best regards,
    The E-Commerce Team
    '''
    
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )


def send_password_reset_email(user):
    """Send password reset email"""
    token_obj = generate_password_reset_token(user)
    
    reset_url = f"{settings.FRONTEND_URL}/reset-password?token={token_obj.token}"
    
    subject = 'Reset your password'
    message = f'''
    Hi {user.first_name},
    
    You requested to reset your password. Click the link below:
    {reset_url}
    
    This link will expire in 2 hours.
    
    If you didn't request this, please ignore this email.
    
    Best regards,
    The E-Commerce Team
    '''
    
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )


def verify_email_token(token):
    """Verify email verification token"""
    try:
        token_obj = EmailVerificationToken.objects.get(
            token=token,
            used=False,
            expires_at__gt=timezone.now()
        )
        
        # Mark token as used
        token_obj.used = True
        token_obj.save()
        
        # Mark user as verified
        user = token_obj.user
        user.is_verified = True
        user.save()
        
        return user
    except EmailVerificationToken.DoesNotExist:
        return None


def verify_password_reset_token(token):
    """Verify password reset token"""
    try:
        token_obj = PasswordResetToken.objects.get(
            token=token,
            used=False,
            expires_at__gt=timezone.now()
        )
        return token_obj
    except PasswordResetToken.DoesNotExist:
        return None


def reset_password_with_token(token, new_password):
    """Reset password using token"""
    token_obj = verify_password_reset_token(token)
    if not token_obj:
        return False
    
    # Mark token as used
    token_obj.used = True
    token_obj.save()
    
    # Update user password
    user = token_obj.user
    user.set_password(new_password)
    user.save()
    
    return True


def log_login_attempt(email, ip_address, user_agent, success, failure_reason=None):
    """Log login attempt for security monitoring"""
    LoginAttempt.objects.create(
        email=email,
        ip_address=ip_address,
        user_agent=user_agent,
        success=success,
        failure_reason=failure_reason
    )


def check_rate_limit(email, ip_address, window_minutes=15, max_attempts=5):
    """Check if login attempts exceed rate limit"""
    cutoff_time = timezone.now() - timedelta(minutes=window_minutes)
    
    # Check failed attempts by email
    email_attempts = LoginAttempt.objects.filter(
        email=email,
        success=False,
        timestamp__gte=cutoff_time
    ).count()
    
    # Check failed attempts by IP
    ip_attempts = LoginAttempt.objects.filter(
        ip_address=ip_address,
        success=False,
        timestamp__gte=cutoff_time
    ).count()
    
    return email_attempts >= max_attempts or ip_attempts >= max_attempts


def get_client_ip(request):
    """Get client IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def get_user_agent(request):
    """Get user agent from request"""
    return request.META.get('HTTP_USER_AGENT', '')


def hash_sensitive_data(data):
    """Hash sensitive data for storage"""
    return hashlib.sha256(data.encode()).hexdigest()


def generate_api_key():
    """Generate API key for service-to-service communication"""
    return f"ecom_{secrets.token_urlsafe(32)}"


def validate_api_key(api_key):
    """Validate API key for service communication"""
    # In production, this would check against a database of valid API keys
    # For now, we'll just check the format
    return api_key.startswith("ecom_") and len(api_key) > 40


class RoleManager:
    """Helper class for role management"""
    
    @staticmethod
    def assign_role(user, role_name, assigned_by=None, expires_at=None):
        """Assign role to user"""
        from .models import Role, UserRole
        
        try:
            role = Role.objects.get(name=role_name, is_active=True)
            user_role, created = UserRole.objects.get_or_create(
                user=user,
                role=role,
                defaults={
                    'assigned_by': assigned_by,
                    'expires_at': expires_at,
                    'is_active': True
                }
            )
            return user_role
        except Role.DoesNotExist:
            return None
    
    @staticmethod
    def remove_role(user, role_name):
        """Remove role from user"""
        from .models import Role, UserRole
        
        try:
            role = Role.objects.get(name=role_name)
            UserRole.objects.filter(user=user, role=role).update(is_active=False)
            return True
        except Role.DoesNotExist:
            return False
    
    @staticmethod
    def has_role(user, role_name):
        """Check if user has specific role"""
        from .models import Role, UserRole
        
        return UserRole.objects.filter(
            user=user,
            role__name=role_name,
            is_active=True,
            role__is_active=True
        ).exists()
    
    @staticmethod
    def has_permission(user, permission_name):
        """Check if user has specific permission"""
        from django.contrib.auth.models import Permission
        
        # Check direct user permissions
        if user.user_permissions.filter(codename=permission_name).exists():
            return True
        
        # Check role-based permissions
        from .models import UserRole
        return UserRole.objects.filter(
            user=user,
            is_active=True,
            role__is_active=True,
            role__permissions__codename=permission_name
        ).exists()


def cleanup_expired_tokens():
    """Cleanup expired tokens (run as scheduled task)"""
    cutoff_time = timezone.now()
    
    # Cleanup expired verification tokens
    EmailVerificationToken.objects.filter(expires_at__lt=cutoff_time).delete()
    
    # Cleanup expired password reset tokens
    PasswordResetToken.objects.filter(expires_at__lt=cutoff_time).delete()
    
    # Cleanup old login attempts (keep 30 days)
    old_cutoff = timezone.now() - timedelta(days=30)
    LoginAttempt.objects.filter(timestamp__lt=old_cutoff).delete()


def get_user_permissions(user):
    """Get all permissions for a user (direct + role-based)"""
    permissions = set()
    
    # Direct permissions
    for perm in user.user_permissions.all():
        permissions.add(f"{perm.content_type.app_label}.{perm.codename}")
    
    # Role-based permissions
    from .models import UserRole
    for user_role in UserRole.objects.filter(user=user, is_active=True, role__is_active=True):
        for perm in user_role.role.permissions.all():
            permissions.add(f"{perm.content_type.app_label}.{perm.codename}")
    
    return list(permissions)
