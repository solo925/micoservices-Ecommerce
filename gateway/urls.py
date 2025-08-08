from django.urls import path
from . import views

urlpatterns = [
    path('graphql/', views.GraphQLView.as_view(), name='graphql'),
    path('health/', views.health_check, name='health_check'),
]
