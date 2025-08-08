from django.urls import path
from . import views

app_name = 'notification'

urlpatterns = [
    # Template URLs
    path('templates/', views.NotificationTemplateListCreateView.as_view(), name='template-list-create'),
    path('templates/create/', views.NotificationTemplateCreateView.as_view(), name='template-create'),
    path('templates/<uuid:pk>/', views.NotificationTemplateDetailView.as_view(), name='template-detail'),
    
    # Channel URLs
    path('channels/', views.NotificationChannelListCreateView.as_view(), name='channel-list-create'),
    path('channels/create/', views.NotificationChannelCreateView.as_view(), name='channel-create'),
    path('channels/<uuid:pk>/', views.NotificationChannelDetailView.as_view(), name='channel-detail'),
    
    # Notification URLs
    path('notifications/', views.NotificationListCreateView.as_view(), name='notification-list-create'),
    path('notifications/create/', views.NotificationCreateView.as_view(), name='notification-create'),
    path('notifications/<uuid:pk>/', views.NotificationDetailView.as_view(), name='notification-detail'),
    path('notifications/<uuid:pk>/update/', views.NotificationUpdateView.as_view(), name='notification-update'),
    path('notifications/<uuid:pk>/status/', views.NotificationStatusUpdateView.as_view(), name='notification-status-update'),
    
    # Delivery URLs
    path('deliveries/', views.NotificationDeliveryListView.as_view(), name='delivery-list'),
    path('deliveries/<uuid:pk>/', views.NotificationDeliveryDetailView.as_view(), name='delivery-detail'),
    
    # Preference URLs
    path('preferences/', views.NotificationPreferenceListCreateView.as_view(), name='preference-list-create'),
    path('preferences/<uuid:pk>/', views.NotificationPreferenceDetailView.as_view(), name='preference-detail'),
    path('preferences/<uuid:pk>/update/', views.NotificationPreferenceUpdateView.as_view(), name='preference-update'),
    path('preferences/bulk-update/', views.bulk_update_preferences, name='preference-bulk-update'),
    path('preferences/user/<uuid:user_id>/', views.user_preferences, name='user-preferences'),
    
    # Batch URLs
    path('batches/', views.NotificationBatchListCreateView.as_view(), name='batch-list-create'),
    path('batches/create/', views.NotificationBatchCreateView.as_view(), name='batch-create'),
    path('batches/<uuid:pk>/', views.NotificationBatchDetailView.as_view(), name='batch-detail'),
    path('batches/<uuid:pk>/status/', views.NotificationBatchStatusUpdateView.as_view(), name='batch-status-update'),
    path('batches/<uuid:batch_id>/process/', views.process_batch_notification, name='batch-process'),
    
    # Log URLs
    path('logs/', views.NotificationLogListView.as_view(), name='log-list'),
    path('logs/<uuid:pk>/', views.NotificationLogDetailView.as_view(), name='log-detail'),
    
    # Specialized notification URLs
    path('send/order/', views.send_order_notification, name='send-order-notification'),
    path('send/payment/', views.send_payment_notification, name='send-payment-notification'),
    path('send/low-stock-alert/', views.send_low_stock_alert, name='send-low-stock-alert'),
    path('send/promotion/', views.send_promotion_notification, name='send-promotion-notification'),
    path('send/bulk/', views.send_bulk_notification, name='send-bulk-notification'),
    
    # Utility URLs
    path('retry/', views.retry_notification, name='retry-notification'),
    path('test/template/', views.test_template, name='test-template'),
    path('test/channel/', views.test_channel, name='test-channel'),
    path('stats/', views.notification_stats, name='notification-stats'),
    path('stats/channel/<uuid:channel_id>/', views.channel_stats, name='channel-stats'),
    path('search/', views.search_notifications, name='search-notifications'),
    
    # Health check
    path('health/', views.health_check, name='health-check'),
]
