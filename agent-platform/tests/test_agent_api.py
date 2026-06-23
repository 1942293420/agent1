"""Agent 管理 API 测试"""
import pytest
from rest_framework import status
from django.urls import reverse

pytestmark = pytest.mark.django_db


class TestAgentList:
    def test_list_agents(self, api_client, factories):
        """查询 Agent 列表"""
        factories.AgentFactory.create_batch(2)
        url = reverse('agents:agent-list')
        resp = api_client.get(url)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data['count'] >= 2

    def test_list_agents_empty(self, api_client):
        """空列表也正常返回"""
        url = reverse('agents:agent-list')
        resp = api_client.get(url)
        assert resp.status_code == status.HTTP_200_OK


class TestAgentDetail:
    def test_get_agent(self, api_client, factories):
        """获取单个 Agent 详情"""
        a = factories.AgentFactory.create()
        url = reverse('agents:agent-detail', args=[a.id])
        resp = api_client.get(url)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data['id'] == a.id
        assert resp.data['name'] == a.name

    def test_get_nonexistent_agent(self, api_client):
        """不存在的 Agent 返回 404"""
        url = reverse('agents:agent-detail', args=[99999])
        resp = api_client.get(url)
        assert resp.status_code == status.HTTP_404_NOT_FOUND


class TestAgentCreate:
    def test_create_agent(self, api_client):
        """创建 Agent"""
        url = reverse('agents:agent-list')
        data = {
            "name": "TestAgent",
            "feishu_app_id": "test_app_001",
            "webhook_url": "https://example.com/hook",
            "portrait": "你是测试Agent",
        }
        resp = api_client.post(url, data, format='json')
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data['name'] == "TestAgent"

    def test_create_agent_invalid(self, api_client):
        """无效数据应返回 400"""
        url = reverse('agents:agent-list')
        resp = api_client.post(url, {}, format='json')
        assert resp.status_code == status.HTTP_400_BAD_REQUEST


class TestAgentUpdate:
    def test_update_agent_name(self, api_client, factories):
        """更新 Agent 名称"""
        a = factories.AgentFactory.create(name="OldName")
        url = reverse('agents:agent-detail', args=[a.id])
        resp = api_client.patch(url, {"name": "NewName"}, format='json')
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data['name'] == "NewName"


class TestAgentDelete:
    def test_delete_agent(self, api_client, factories):
        """删除 Agent"""
        a = factories.AgentFactory.create()
        url = reverse('agents:agent-detail', args=[a.id])
        resp = api_client.delete(url)
        assert resp.status_code == status.HTTP_204_NO_CONTENT
