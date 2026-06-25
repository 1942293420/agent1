from django.db import models
from django.conf import settings


class SandboxSession(models.Model):
    STATUS_CHOICES = [
        ('creating', '创建中'),
        ('running', '运行中'),
        ('idle', '空闲'),
        ('stopped', '已停止'),
        ('destroyed', '已销毁'),
        ('error', '错误'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    container_id = models.CharField(max_length=128, unique=True, null=True, blank=True)
    container_name = models.CharField(max_length=128, unique=True)
    workspace_path = models.CharField(max_length=512)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='creating')
    cpu_limit = models.FloatField(default=1.0)
    memory_limit_mb = models.IntegerField(default=512)
    max_lifetime_minutes = models.IntegerField(default=1440)
    idle_timeout_minutes = models.IntegerField(default=30)

    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    last_active_at = models.DateTimeField(null=True, blank=True)
    destroyed_at = models.DateTimeField(null=True, blank=True)
    active_conversations = models.IntegerField(default=0)

    class Meta:
        db_table = 'sandbox_sessions'
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['status', 'last_active_at']),
        ]

    def __str__(self):
        return f'{self.user.username} — {self.status}'
