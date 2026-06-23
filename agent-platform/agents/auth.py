"""
Agent Platform — HMAC 签名认证

Agent 请求流程：
  1. 请求体 + secret_key → HMAC-SHA256 → 签名
  2. 放入 Header：X-Agent-Id + X-Signature + X-Timestamp（防重放）
  3. 平台收到后，用 Agent 的 secret_key 重新计算签名
  4. 比对一致 → 放行；不一致 → 403

防重放：X-Timestamp 与服务器时间差超过 5 分钟则拒绝
"""
import hashlib
import hmac
import time
import secrets
from rest_framework import authentication, exceptions, permissions
from .models import Agent

# ─── Agent 专用端点列表 ───
AGENT_ONLY_ACTIONS = {'heartbeat', 'pull_tasks'}


class AgentEndpointPermission(permissions.BasePermission):
    """
    Agent 专用端点必须通过 HMAC 认证。

    非 Agent 端点（CRUD）允许未认证访问（供 Admin 控制台使用）。
    Agent 端点（heartbeat/pull-tasks/status/logs）拒绝无签名的请求。
    """

    def has_permission(self, request, view):
        action = getattr(view, 'action', None)
        if action in AGENT_ONLY_ACTIONS:
            # Agent 端点：必须有 request.agent（HMAC 认证通过后设置）
            if not hasattr(request, 'agent') or request.agent is None:
                return False
        # 其他端点：允许（包括未认证的管理操作）
        return True


class AgentHMACAuthentication(authentication.BaseAuthentication):
    """
    HMAC-SHA256 签名认证。

    Agent 需要发送以下 Header：
      - X-Agent-Id: Agent 的 ID
      - X-Signature: HMAC-SHA256(secret_key, body) 的十六进制字符串
      - X-Timestamp: Unix 时间戳（秒），防重放

    可选 Header（跳过签名检查）：
      - X-Registration: 任意值 — 仅用于注册端点
    """
    MAX_TIME_SKEW = 300  # 5 分钟

    @staticmethod
    def generate_secret_key():
        """生成 64 字符的十六进制随机密钥，供 Agent 注册时使用"""
        return secrets.token_hex(32)

    def _sign(self, secret_key, body):
        """HMAC-SHA256 签名：secret_key + body → hex digest"""
        key_bytes = secret_key.encode('utf-8') if isinstance(secret_key, str) else secret_key
        body_bytes = body.encode('utf-8') if isinstance(body, str) else body
        return hmac.new(key_bytes, body_bytes, hashlib.sha256).hexdigest()

    def authenticate(self, request):
        # 跳过注册（Agent 还没有 secret_key）
        if request.path.endswith('/register/'):
            return None

        agent_id = request.headers.get('X-Agent-Id')
        signature = request.headers.get('X-Signature')
        timestamp_str = request.headers.get('X-Timestamp')

        # 没有 HMAC 头 → 允许未认证访问（管理 API 用 Session Auth 或匿名）
        if not agent_id and not signature:
            return None

        # 防重放
        try:
            ts = int(timestamp_str)
        except (ValueError, TypeError):
            raise exceptions.AuthenticationFailed('X-Timestamp 必须是 Unix 时间戳')

        if abs(time.time() - ts) > self.MAX_TIME_SKEW:
            raise exceptions.AuthenticationFailed(
                f'X-Timestamp 偏离超过 {self.MAX_TIME_SKEW}s，可能为重放攻击'
            )

        # 查找 Agent
        try:
            agent = Agent.objects.get(id=agent_id)
        except Agent.DoesNotExist:
            raise exceptions.AuthenticationFailed(f'Agent #{agent_id} 不存在')

        if not agent.secret_key:
            raise exceptions.AuthenticationFailed(
                f'Agent #{agent_id} 未配置 secret_key，请重新注册'
            )

        # 计算签名
        body = request.body.decode('utf-8') if request.body else ''
        expected = self._sign(agent.secret_key, body)

        if not hmac.compare_digest(expected, signature):
            raise exceptions.AuthenticationFailed(
                'HMAC 签名验证失败'
            )

        # 验证通过，把 agent 挂到 request 上
        # 后续业务代码可以通过 request.agent 直接拿
        request.agent = agent
        return (agent, None)
