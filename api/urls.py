from django.urls import path
from . import views

urlpatterns = [
    path('auth/register/', views.register),
    path('auth/login/', views.login),
    path('auth/guest/', views.guest),
    path('auth/me/', views.me),
    path('payments/', views.payments),
    path('predictions/', views.predictions),
    path('predictions/<str:game>/', views.clear_predictions),
    path('admin/payments/', views.admin_payments),
    path('admin/payments/<int:pk>/', views.admin_review_payment),
    path('admin/payments/<int:pk>/screenshot/', views.admin_payment_screenshot),
    path('admin/users/', views.admin_users),
]
