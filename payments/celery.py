from celery import Celery

app = Celery('payments',
             broker='pyamqp://rabbitmq//',
             backend='redis://redis:6379/0',
             include=['payments.tasks'])
