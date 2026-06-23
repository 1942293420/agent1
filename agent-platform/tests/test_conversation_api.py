"""会话 & 消息 API 测试"""
import pytest
from rest_framework import status
from django.urls import reverse

pytestmark = pytest.mark.django_db


class TestConversationAPI:
    def test_create_conversation(self, api_client, factories):
        a = factories.AgentFactory.create()
        url = reverse('agents:conversation-list')
        resp = api_client.post(url, {
            "title": "测试会话",
            "agent": a.id,
        }, format='json')
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data['title'] == "测试会话"
        assert resp.data['agent_name'] == a.name

    def test_list_conversations(self, api_client, factories):
        factories.ConversationFactory.create_batch(2)
        url = reverse('agents:conversation-list')
        resp = api_client.get(url)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data['count'] >= 2

    def test_get_conversation_with_messages(self, api_client, factories):
        conv = factories.ConversationFactory.create()
        factories.MessageFactory.create_batch(3, conversation=conv)
        url = reverse('agents:conversation-detail', args=[conv.id])
        resp = api_client.get(url)
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data['messages']) >= 3

    def test_delete_conversation(self, api_client, factories):
        conv = factories.ConversationFactory.create()
        url = reverse('agents:conversation-detail', args=[conv.id])
        resp = api_client.delete(url)
        assert resp.status_code == status.HTTP_204_NO_CONTENT


class TestMessageAPI:
    def test_send_message(self, api_client, factories):
        conv = factories.ConversationFactory.create()
        url = reverse('agents:message-list')
        resp = api_client.post(url, {
            "conversation": conv.id,
            "role": "user",
            "content": "测试消息",
            "source": "web",
        }, format='json')
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data['role'] == 'user'
        assert resp.data['processed'] is False

    def test_list_messages(self, api_client, factories):
        conv = factories.ConversationFactory.create()
        factories.MessageFactory.create_batch(2, conversation=conv)
        url = reverse('agents:message-list')
        resp = api_client.get(url)
        assert resp.status_code == status.HTTP_200_OK

    def test_pending_messages_api(self, api_client, factories):
        """待处理消息端点"""
        conv = factories.ConversationFactory.create()
        factories.MessageFactory.create(
            conversation=conv, role='user', processed=False)
        url = reverse('agents:message-pending-messages')
        resp = api_client.get(url)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data['count'] >= 1

    def test_pending_includes_agent_info(self, api_client, factories):
        """待处理消息包含 Agent portrait"""
        agent = factories.AgentFactory.create(
            portrait='你是一个数据分析师')
        conv = factories.ConversationFactory.create(agent=agent)
        factories.MessageFactory.create(
            conversation=conv, role='user', processed=False)
        url = reverse('agents:message-pending-messages')
        resp = api_client.get(url)
        msgs = resp.data['messages']
        assert len(msgs) >= 1
        assert msgs[0].get('agent_portrait') == '你是一个数据分析师'
        assert msgs[0].get('agent_name') == agent.name
