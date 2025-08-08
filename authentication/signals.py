from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .models import UserProfile, Role, UserRole

User = get_user_model()


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Create user profile when user is created"""
    if created:
        UserProfile.objects.get_or_create(user=instance)


@receiver(post_save, sender=User)
def assign_default_role(sender, instance, created, **kwargs):
    """Assign default customer role to new users"""
    if created:
        try:
            customer_role = Role.objects.get(name='customer', is_active=True)
            UserRole.objects.get_or_create(
                user=instance,
                role=customer_role,
                defaults={'is_active': True}
            )
        except Role.DoesNotExist:
            # Customer role doesn't exist yet, will be created by management command
            pass


@receiver(pre_save, sender=User)
def normalize_email(sender, instance, **kwargs):
    """Normalize email address before saving"""
    if instance.email:
        instance.email = instance.email.lower().strip()
