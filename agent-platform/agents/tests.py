"""
Agent Platform — 全套单元测试

覆盖：
  1. Models — 创建、关系、约束、索引、排序
  2. Serializers — 序列化、验证、read_only、write_only
  3. API 端点 — CRUD、分页、搜索、过滤
  4. 调度引擎 — 任务匹配、Skill 注入、知识引用
  5. HMAC 认证 — 正确签名、错误签名、过期时间戳、无签名
"""
import json, hmac, hashlib, time
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase, APIClient
from rest_framework import status as http_status

from .models import (
    CapabilityTag, Agent, Skill, AgentSkill,
    Task, ExecutionLog, KnowledgeEntry,
)
from .serializers import (
    AgentRegisterSerializer,
    TaskCreateSerializer,
    TaskStatusUpdateSerializer,
    AgentHeartbeatSerializer,
)
from .auth import AgentHMACAuthentication


# ═══════════════════════════════════════════════
# 1. Model Tests
# ═══════════════════════════════════════════════

class CapabilityTagModelTest(TestCase):
    def setUp(self):
        self.tag = CapabilityTag.objects.create(name='代码生成', slug='code-gen')

    def test_create(self):
        self.assertEqual(self.tag.name, '代码生成')
        self.assertEqual(self.tag.slug, 'code-gen')

    def test_agent_count(self):
        agent = Agent.objects.create(name='A', feishu_app_id='c1')
        agent.capabilities.add(self.tag)
        self.assertEqual(self.tag.agents.count(), 1)


class AgentModelTest(TestCase):
    def setUp(self):
        self.agent = Agent.objects.create(name='Bot', feishu_app_id='app_001')

    def test_default_status_offline(self):
        self.assertEqual(self.agent.status, Agent.Status.OFFLINE)

    def test_secret_key_auto_generated(self):
        data = {'name': 'NewBot', 'feishu_app_id': 'app_new',
                'webhook_url': 'https://example.com/hook', 'version': '1.0'}
        serializer = AgentRegisterSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        agent = serializer.save()
        self.assertEqual(len(agent.secret_key), 64)
        self.assertEqual(agent.status, Agent.Status.ONLINE)

    def test_capability_m2m(self):
        tag = CapabilityTag.objects.create(name='测试', slug='test')
        self.agent.capabilities.add(tag)
        self.assertEqual(self.agent.capabilities.count(), 1)
        self.assertEqual(tag.agents.count(), 1)

    def test_task_count_via_related(self):
        self.assertEqual(self.agent.tasks.count(), 0)
        Task.objects.create(title='T1', agent=self.agent)
        self.assertEqual(self.agent.tasks.count(), 1)


class SkillModelTest(TestCase):
    def test_defaults(self):
        skill = Skill.objects.create(name='Test', slug='test-skill')
        self.assertEqual(skill.status, Skill.Status.ACTIVE)
        self.assertEqual(skill.source, Skill.Source.LOCAL)
        self.assertEqual(skill.version, '1.0.0')

    def test_unique_slug(self):
        Skill.objects.create(name='A', slug='unique-slug')
        with self.assertRaises(Exception):
            Skill.objects.create(name='B', slug='unique-slug')


class TaskModelTest(TestCase):
    def setUp(self):
        self.agent = Agent.objects.create(name='A', feishu_app_id='task_test')

    def test_defaults(self):
        task = Task.objects.create(title='Hello')
        self.assertEqual(task.status, Task.Status.PENDING)
        self.assertEqual(task.priority, Task.Priority.MEDIUM)

    def test_parent_task_dependency(self):
        parent = Task.objects.create(title='Parent')
        child = Task.objects.create(title='Child', parent_task=parent)
        self.assertEqual(child.parent_task, parent)
        self.assertEqual(parent.subtasks.count(), 1)

    def test_skill_assignment(self):
        skill = Skill.objects.create(name='S', slug='s')
        task = Task.objects.create(title='With Skill')
        task.assigned_skills.add(skill)
        self.assertEqual(task.assigned_skills.count(), 1)
        self.assertEqual(skill.tasks.count(), 1)


class KnowledgeEntryModelTest(TestCase):
    def test_visibility_default(self):
        entry = KnowledgeEntry.objects.create(
            title='Test', content='Body',
            entry_type=KnowledgeEntry.EntryType.BEST_PRACTICE,
        )
        self.assertEqual(entry.visibility, KnowledgeEntry.Visibility.PUBLIC)

    def test_relevance_score_bounds(self):
        entry = KnowledgeEntry(title='T', content='C', relevance_score=1.5)
        with self.assertRaises(Exception):
            entry.full_clean()


# ═══════════════════════════════════════════════
# 2. Serializer Tests
# ═══════════════════════════════════════════════

class SerializerTest(TestCase):
    def test_secret_key_auto_generated(self):
        data = {'name': 'NewBot', 'feishu_app_id': 'app_new',
                'webhook_url': 'https://example.com/hook', 'version': '1.0'}
        s = AgentRegisterSerializer(data=data)
        self.assertTrue(s.is_valid())
        agent = s.save()
        self.assertIn('secret_key', s.data)
        self.assertEqual(len(agent.secret_key), 64)

    def test_task_create_with_skill_slugs(self):
        Skill.objects.create(name='S', slug='s1', status=Skill.Status.ACTIVE)
        data = {'title': 'T', 'skill_slugs': ['s1']}
        s = TaskCreateSerializer(data=data)
        self.assertTrue(s.is_valid())
        task = s.save()
        self.assertEqual(task.assigned_skills.count(), 1)

    def test_task_status_update_valid(self):
        s = TaskStatusUpdateSerializer(data={'status': 'completed'})
        self.assertTrue(s.is_valid())

    def test_task_status_update_invalid(self):
        s = TaskStatusUpdateSerializer(data={'status': 'unknown'})
        self.assertFalse(s.is_valid())

    def test_heartbeat_serializer(self):
        s = AgentHeartbeatSerializer(data={'status': 'online'})
        self.assertTrue(s.is_valid())


# ═══════════════════════════════════════════════
# 3. API Endpoint Tests
# ═══════════════════════════════════════════════

class APIEndpointTest(APITestCase):
    def setUp(self):
        self.client = APIClient()

    def test_api_root_returns_endpoints(self):
        resp = self.client.get('/api/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('agents', resp.data)
        self.assertIn('tasks', resp.data)
        self.assertIn('skills', resp.data)

    # ─── Agent ───

    def test_agent_register_and_list(self):
        resp = self.client.post('/api/agents/register/', {
            'name': 'B1', 'feishu_app_id': 'f1',
            'webhook_url': 'https://example.com/hook', 'version': '1.0',
            'capabilities': ['代码生成'],
        })
        self.assertEqual(resp.status_code, 201)
        self.assertIn('secret_key', resp.data)
        self.assertEqual(resp.data['status'], 'online')

        # List
        resp = self.client.get('/api/agents/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 1)

    def test_agent_detail(self):
        agent = Agent.objects.create(name='B2', feishu_app_id='f2')
        resp = self.client.get(f'/api/agents/{agent.id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['name'], 'B2')
        self.assertNotIn('secret_key', resp.data)  # Secret never exposed

    def test_agent_filter_by_status(self):
        Agent.objects.create(name='Online', feishu_app_id='on1', status='online')
        Agent.objects.create(name='Offline', feishu_app_id='off1', status='offline')
        resp = self.client.get('/api/agents/?status=online')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 1)

    # ─── Skills ───

    def test_skill_crud(self):
        resp = self.client.post('/api/skills/', {
            'name': 'Test Skill', 'slug': 'test-skill',
            'version': '1.0', 'source': 'local',
        })
        self.assertEqual(resp.status_code, 201)

        resp = self.client.get('/api/skills/test-skill/')
        self.assertEqual(resp.data['name'], 'Test Skill')

    # ─── Tasks ───

    def test_task_create_and_list(self):
        resp = self.client.post('/api/tasks/', {
            'title': 'Test Task', 'priority': 'high',
        })
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['status'], 'pending')

        resp = self.client.get('/api/tasks/')
        self.assertEqual(resp.data['count'], 1)

    def test_task_filter_by_status(self):
        Task.objects.create(title='Done', status='completed')
        Task.objects.create(title='Pending', status='pending')
        resp = self.client.get('/api/tasks/?status=completed')
        self.assertEqual(resp.data['count'], 1)

    # ─── Knowledge ───

    def test_knowledge_crud(self):
        resp = self.client.post('/api/knowledge/', {
            'title': 'Best Practice', 'content': 'Use DRF ViewSets',
            'entry_type': 'best_practice', 'visibility': 'public',
            'relevance_score': 0.8,
        })
        self.assertEqual(resp.status_code, 201)

        resp = self.client.get('/api/knowledge/')
        self.assertEqual(resp.data['count'], 1)

    # ─── Capabilities ───

    def test_capability_list(self):
        CapabilityTag.objects.create(name='代码', slug='code')
        resp = self.client.get('/api/capabilities/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 1)

    # ─── Pagination ───

    def test_pagination(self):
        for i in range(25):
            Agent.objects.create(name=f'Pag-{i}', feishu_app_id=f'pg_{i}')
        resp = self.client.get('/api/agents/')
        self.assertEqual(resp.data['count'], 25)
        self.assertIn('next', resp.data)
        self.assertEqual(len(resp.data['results']), 20)


# ═══════════════════════════════════════════════
# 4. Dispatch Engine Tests
# ═══════════════════════════════════════════════

class DispatchEngineTest(TestCase):
    def setUp(self):
        from .views import TaskDispatchEngine
        self.Engine = TaskDispatchEngine

        self.agent = Agent.objects.create(
            name='Worker', feishu_app_id='disp_001', status='online',
        )
        self.tag = CapabilityTag.objects.create(name='backend', slug='backend')
        self.agent.capabilities.add(self.tag)

    def test_pull_pending_task(self):
        Task.objects.create(title='Test Task', priority='high')
        engine = self.Engine(self.agent)
        packages = engine.pull_tasks()
        self.assertEqual(len(packages), 1)
        self.assertEqual(packages[0]['title'], 'Test Task')

        # Task should now be assigned
        task = Task.objects.get(id=packages[0]['task_id'])
        self.assertEqual(task.status, Task.Status.ASSIGNED)
        self.assertEqual(task.agent, self.agent)

    def test_task_with_skill_gets_skill_info(self):
        skill = Skill.objects.create(
            name='DRF Gen', slug='drf-gen',
            file_url='https://example.com/skill.zip',
            file_hash='abc123',
        )
        task = Task.objects.create(title='API Task', priority='high')
        task.assigned_skills.add(skill)

        engine = self.Engine(self.agent)
        packages = engine.pull_tasks()
        self.assertEqual(len(packages), 1)
        self.assertEqual(len(packages[0]['skills']), 1)
        self.assertEqual(packages[0]['skills'][0]['name'], 'DRF Gen')

    def test_task_with_knowledge_refs(self):
        entry = KnowledgeEntry.objects.create(
            title='Tips', content='Use select_related',
            entry_type='best_practice', visibility='public',
            relevance_score=0.9,
        )
        task = Task.objects.create(
            title='With Knowledge', priority='medium',
            knowledge_refs=[entry.id],
        )
        engine = self.Engine(self.agent)
        packages = engine.pull_tasks()
        self.assertEqual(len(packages[0]['knowledge']), 1)

    def test_parent_task_dependency_blocks_pull(self):
        parent = Task.objects.create(title='Parent', status='pending')
        child = Task.objects.create(title='Child', parent_task=parent)

        engine = self.Engine(self.agent)
        packages = engine.pull_tasks()
        # Parent should be pulled (no dependency), child blocked until parent done
        self.assertEqual(len(packages), 1)
        self.assertEqual(packages[0]['title'], 'Parent')

    def test_max_tasks_per_pull(self):
        for i in range(5):
            Task.objects.create(title=f'T{i}', priority='high')
        engine = self.Engine(self.agent)
        packages = engine.pull_tasks()
        self.assertLessEqual(len(packages), engine.MAX_TASKS_PER_PULL)

    def test_pull_creates_execution_log(self):
        Task.objects.create(title='Log Test')
        engine = self.Engine(self.agent)
        engine.pull_tasks()
        self.assertEqual(ExecutionLog.objects.count(), 1)
        log = ExecutionLog.objects.first()
        self.assertEqual(log.level, 'info')
        self.assertIn('分配', log.message)


# ═══════════════════════════════════════════════
# 5. HMAC Authentication Tests
# ═══════════════════════════════════════════════

class HMACAuthTest(APITestCase):
    def setUp(self):
        self.client = APIClient()
        # Register an agent to get a secret_key
        resp = self.client.post('/api/agents/register/', {
            'name': 'HMAC-Agent', 'feishu_app_id': 'hmac_test',
            'webhook_url': 'https://example.com/hook', 'version': '1.0',
            'capabilities': ['测试'],
        })
        self.agent_id = resp.data['id']
        self.secret_key = resp.data['secret_key']

    def _sign(self, body_dict):
        """Sign a body dict with the agent's secret key"""
        body = json.dumps(body_dict, separators=(',', ':'))
        return hmac.new(
            self.secret_key.encode(), body.encode(), hashlib.sha256
        ).hexdigest()

    def _auth_headers(self, body_dict):
        """Build HMAC auth headers"""
        return {
            'HTTP_X_AGENT_ID': str(self.agent_id),
            'HTTP_X_SIGNATURE': self._sign(body_dict),
            'HTTP_X_TIMESTAMP': str(int(time.time())),
        }

    def _agent_post(self, path, data=None):
        """POST with HMAC auth headers + JSON format"""
        if data is None:
            data = {}
        return self.client.post(
            path, data,
            format='json',
            **self._auth_headers(data),
        )

    def test_no_signature_rejected(self):
        resp = self.client.post(
            f'/api/agents/{self.agent_id}/heartbeat/',
            {'status': 'online'},
        )
        self.assertIn(resp.status_code, [401, 403])

    def test_wrong_signature_rejected(self):
        body = {'status': 'online'}
        fake_sig = hmac.new(b'wrong',
            json.dumps(body, separators=(',', ':')).encode(), hashlib.sha256).hexdigest()
        resp = self.client.post(
            f'/api/agents/{self.agent_id}/heartbeat/',
            body,
            format='json',
            HTTP_X_AGENT_ID=str(self.agent_id),
            HTTP_X_SIGNATURE=fake_sig,
            HTTP_X_TIMESTAMP=str(int(time.time())),
        )
        self.assertIn(resp.status_code, [401, 403])

    def test_old_timestamp_rejected(self):
        body = {'status': 'online'}
        old_ts = int(time.time()) - 600
        resp = self.client.post(
            f'/api/agents/{self.agent_id}/heartbeat/',
            body,
            format='json',
            HTTP_X_AGENT_ID=str(self.agent_id),
            HTTP_X_SIGNATURE=self._sign(body),
            HTTP_X_TIMESTAMP=str(old_ts),
        )
        self.assertIn(resp.status_code, [401, 403])

    def test_valid_signature_accepted(self):
        body = {'status': 'online', 'version': '1.1'}
        resp = self._agent_post(
            f'/api/agents/{self.agent_id}/heartbeat/',
            body,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], 'ok')

    def test_pull_tasks_requires_signature(self):
        # Create a task first so pull returns something
        self.client.post('/api/tasks/', {'title': 'HMAC Test'})
        resp = self._agent_post(
            f'/api/agents/{self.agent_id}/pull-tasks/',
            {},
        )
        self.assertEqual(resp.status_code, 200)

    def test_admin_api_works_without_signature(self):
        resp = self.client.post('/api/tasks/', {
            'title': 'Admin Task',
        })
        self.assertEqual(resp.status_code, 201)

    def test_secret_key_not_exposed_in_detail(self):
        resp = self.client.get(f'/api/agents/{self.agent_id}/')
        self.assertNotIn('secret_key', resp.data)

    def test_secret_key_not_exposed_in_list(self):
        resp = self.client.get('/api/agents/')
        for agent in resp.data['results']:
            self.assertNotIn('secret_key', agent)


# ═══════════════════════════════════════════════
# 6. Error Handling Tests
# ═══════════════════════════════════════════════

class ErrorHandlingTest(APITestCase):
    def test_register_missing_required(self):
        resp = self.client.post('/api/agents/register/', {})
        self.assertEqual(resp.status_code, 400)
        # 统一错误码格式: {"code": ..., "message": ..., "detail": {...}}
        self.assertIn('code', resp.data)
        self.assertIn('message', resp.data)

    def test_duplicate_feishu_app_id(self):
        self.client.post('/api/agents/register/', {
            'name': 'A', 'feishu_app_id': 'dup',
            'webhook_url': 'https://example.com/hook',
        })
        resp = self.client.post('/api/agents/register/', {
            'name': 'B', 'feishu_app_id': 'dup',
            'webhook_url': 'https://example.com/hook',
        })
        self.assertEqual(resp.status_code, 400)

    def test_agent_endpoint_requires_auth(self):
        """Agent 专用端点未带签名 → 401"""
        resp = self.client.post('/api/tasks/', {'title': 'T'})
        task_id = resp.data['id']
        resp = self.client.post(f'/api/tasks/{task_id}/status/', {
            'status': 'completed',
        })
        # 无 HMAC 签名 → 未认证
        self.assertIn(resp.status_code, [401, 403])
