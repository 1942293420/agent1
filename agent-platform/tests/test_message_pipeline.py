"""消息链路集成测试"""
import pytest
import redis
from rest_framework import status
from django.urls import reverse

pytestmark = pytest.mark.django_db

REDIS_URL = "redis://localhost:6379/0"


class TestMessagePipeline:
    """完整消息链路: POST → Redis → Pending API → mark-processed"""

    def test_message_flow(self, api_client, factories):
        # 1. 创建会话
        agent = factories.AgentFactory.create()
        conv = factories.ConversationFactory.create(agent=agent)

        # 2. 发消息
        url = reverse('agents:message-list')
        resp = api_client.post(url, {
            "conversation": conv.id,
            "role": "user",
            "content": "你好",
            "source": "web",
        }, format='json')
        assert resp.status_code == status.HTTP_201_CREATED
        msg_id = resp.data['id']
        assert resp.data['processed'] is False

        # 3. 确认出现在 pending
        pending_url = reverse('agents:message-pending-messages')
        resp = api_client.get(pending_url)
        pending_ids = [m['id'] for m in resp.data['messages']]
        assert msg_id in pending_ids

        # 4. 标记已处理
        mark_url = reverse('agents:message-mark-processed')
        resp = api_client.post(mark_url, {"ids": [msg_id]}, format='json')
        assert resp.status_code == status.HTTP_200_OK

        # 5. 确认不再 pending
        resp = api_client.get(pending_url)
        pending_ids = [m['id'] for m in resp.data['messages']]
        assert msg_id not in pending_ids

    def test_mark_processed_batch(self, api_client, factories):
        """批量标记"""
        conv = factories.ConversationFactory.create()
        msgs = factories.MessageFactory.create_batch(
            3, conversation=conv, role='user', processed=False)
        ids = [m.id for m in msgs]
        mark_url = reverse('agents:message-mark-processed')
        resp = api_client.post(mark_url, {"ids": ids}, format='json')
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data['ok'] is True

    def test_pending_returns_agent_profile(self, api_client, factories):
        """Pending API 返回 agent_profile (多Agent路由用)"""
        agent = factories.AgentFactory.create(
            config_public={"profile": "test-profile", "model": "gpt-4"})
        conv = factories.ConversationFactory.create(agent=agent)
        factories.MessageFactory.create(
            conversation=conv, role='user', processed=False)
        url = reverse('agents:message-pending-messages')
        resp = api_client.get(url)
        msg = resp.data['messages'][0]
        assert 'agent_profile' in msg
        assert 'agent_model' in msg
