from django.urls import path
from . import views

urlpatterns = [
    path('sandbox/status/', views.sandbox_status, name='sandbox-status'),
    path('sandbox/exec/', views.sandbox_exec, name='sandbox-exec'),
    path('sandbox/destroy/', views.sandbox_destroy, name='sandbox-destroy'),
]
