"""
沙箱管理器 — 生命周期 + 会话引用计数 + Redis 缓存
"""
import os
import threading
from django.utils import timezone
from django.conf import settings
from .models import SandboxSession
from .provider import DockerSandboxProvider, SandboxConfig


SANDBOX_ROOT = os.environ.get("SANDBOX_ROOT", "/var/sandboxes")


class SandboxManager:
    _instance = None

    def __init__(self):
        self._provider = None
        self._lock = threading.Lock()

    @property
    def provider(self):
        if self._provider is None:
            self._provider = DockerSandboxProvider()
        return self._provider

    def ensure_sandbox_dir(self, user_id: int):
        path = os.path.join(SANDBOX_ROOT, f"user_{user_id}")
        os.makedirs(path, mode=0o700, exist_ok=True)
        return path

    def get_or_create(self, user_id: int) -> SandboxSession:
        session = SandboxSession.objects.filter(
            user_id=user_id, status__in=['running', 'idle', 'creating']
        ).first()
        if session:
            return session
        return self._create(user_id)

    def _create(self, user_id: int) -> SandboxSession:
        workspace = self.ensure_sandbox_dir(user_id)

        session = SandboxSession.objects.create(
            user_id=user_id,
            container_name=f"sandbox-user-{user_id}",
            workspace_path=workspace,
            status='creating',
        )

        try:
            config = SandboxConfig(
                user_id=user_id,
                cpu_limit=1.0,
                memory_limit_mb=512,
                workspace_host_path=workspace,
            )
            container_id = self.provider.create(config)
            session.container_id = container_id
            session.status = 'running'
            session.started_at = timezone.now()
            session.last_active_at = timezone.now()
            session.save()
            return session
        except Exception as e:
            session.status = 'error'
            session.save()
            raise

    def acquire(self, user_id: int) -> SandboxSession:
        session = self.get_or_create(user_id)
        with self._lock:
            session.active_conversations += 1
            session.save(update_fields=['active_conversations'])
        return session

    def release(self, user_id: int):
        session = SandboxSession.objects.filter(
            user_id=user_id, status__in=['running', 'idle']
        ).first()
        if session:
            with self._lock:
                session.active_conversations = max(0, session.active_conversations - 1)
                if session.active_conversations == 0:
                    session.status = 'idle'
                session.save()

    def exec_cmd(self, user_id: int, command: str, timeout: int = 30) -> dict:
        session = self.get_or_create(user_id)
        result = self.provider.exec_cmd(session.container_id, command, timeout)
        session.last_active_at = timezone.now()
        session.save(update_fields=['last_active_at'])
        return result

    def destroy(self, user_id: int):
        session = SandboxSession.objects.filter(
            user_id=user_id, status__in=['running', 'idle']
        ).first()
        if not session:
            return
        try:
            self.provider.destroy(session.container_id)
        except Exception:
            pass
        session.status = 'destroyed'
        session.destroyed_at = timezone.now()
        session.save()

    def cleanup(self):
        now = timezone.now()
        expired = SandboxSession.objects.filter(
            status__in=['running', 'idle'],
            last_active_at__lt=now - timezone.timedelta(minutes=30),
        )
        for s in expired:
            try:
                self.destroy(s.user_id)
            except Exception:
                pass


sandbox_manager = SandboxManager()
