from celery import shared_task
from .models import Payment

@shared_task
def process_payment(payment_data):
    payment = Payment.objects.create(**payment_data)
    return payment.id
