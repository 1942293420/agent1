"""Agent Platform 共享 Fixtures"""
import pytest
from rest_framework.test import APIClient

@pytest.fixture
def api_client():
    """未认证的 API 客户端"""
    return APIClient()

@pytest.fixture
def factories(db):
    """返回所有 Factory 的命名空间"""
    from tests import factories as f
    return f
