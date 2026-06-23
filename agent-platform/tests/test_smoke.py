"""冒烟测试 — 核心端点可达性"""
import pytest
import requests

BASE = "http://localhost:8001"

ENDPOINTS = [
    "/api/agents/",
    "/api/tasks/",
    "/api/skills/",
    "/api/conversations/",
    "/api/messages/",
    "/api/knowledge/",
    "/api/cron-jobs/",
    "/api/capabilities/",
]

@pytest.mark.smoke
@pytest.mark.parametrize("path", ENDPOINTS)
def test_endpoint_returns_200(path):
    """每个核心 API 端点返回 200"""
    resp = requests.get(f"{BASE}{path}", timeout=10)
    assert resp.status_code == 200, f"{path} 返回 {resp.status_code}"

@pytest.mark.smoke
def test_agents_list_has_data():
    """Agent 列表至少有一个"""
    resp = requests.get(f"{BASE}/api/agents/", timeout=10)
    data = resp.json()
    assert data["count"] >= 1, "Agent 列表不应为空"

@pytest.mark.smoke
def test_conversations_not_empty():
    """会话列表至少有一个"""
    resp = requests.get(f"{BASE}/api/conversations/", timeout=10)
    data = resp.json()
    assert data["count"] >= 1

@pytest.mark.smoke
def test_system_workers():
    """Worker 状态端点"""
    resp = requests.get(f"{BASE}/api/system/workers/", timeout=10)
    assert resp.status_code == 200
    data = resp.json()
    assert "workers" in data
