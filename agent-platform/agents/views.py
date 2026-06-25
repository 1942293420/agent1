"""
Agent Platform — REST API Views + 调度引擎

11 个端点 + 4 个自定义 action + 调度引擎逻辑:
  1. GET/POST  /api/agents/
  2. GET/PUT   /api/agents/{id}/
  3. POST      /api/agents/{id}/heartbeat/
  4. POST      /api/agents/{id}/assign-skill/
  5. POST      /api/agents/{id}/pull-tasks/       ← 调度引擎入口
  6. GET/POST  /api/capabilities/
  7. GET/POST  /api/skills/
  8. GET/PUT   /api/skills/{slug}/
  9. GET/POST  /api/tasks/
  10. GET/PATCH /api/tasks/{id}/
  11. POST     /api/tasks/{id}/status/            ← Agent 回报状态
  12. POST     /api/tasks/{id}/logs/             ← 执行日志
  13. GET       /api/tasks/{id}/logs/
  14. GET/POST  /api/knowledge/
  15. GET       /api/knowledge/{id}/
"""
import json, threading
import requests
from django.db import transaction
from django.db.models import Count, Q, Prefetch
from django.utils import timezone
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from rest_framework import viewsets, status, filters, permissions
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend

import os

# LLM 配置
LLM_CONFIG = {
    'api_key': os.environ.get('DEEPSEEK_API_KEY', ''),
    'base_url': os.environ.get('DEEPSEEK_BASE_URL', 'https://api.deepseek.com'),
    'model': os.environ.get('DEEPSEEK_MODEL', 'deepseek-chat'),
    'max_tokens': 2000,
    'temperature': 0.7,
}


def _build_system_prompt(agent_portrait: str = '') -> str:
    """构建注入 memory + user profile 的系统提示词，确保 Web Chat 人格与飞书小温一致"""
    profile_dir = os.path.expanduser('~/.hermes/profiles/Banni/memories')
    parts = []

    # 基础人格
    parts.append('你是小温，范先生的二号飞书助手。友好、高效、直接。用中文回复。')
    parts.append('【应答机制】你必须在以下时机主动汇报：\\n'
                '1. 收到任务时先确认：「已收到，正在处理...」\\n'
                '2. 分步执行时每完成一步就报告进度（如：「✅ 第1步完成 — XXX，开始第2步...」）\\n'
                '3. 遇到阻塞或需要用户决策时立即说明情况\\n'
                '4. 全部完成后给出总结（完成了什么、结果如何、下一步建议）\\n'
                '不要沉默执行，用户需要随时知道你在做什么。')
    parts.append('你可以通过 AgentOS Web 前端的「输出面板」向用户展示长篇文档/报告/方案：只需在回复末尾用特殊标记\\n'
                '【OUTPUT_PANEL】\\n...你的文档内容...\\n【/OUTPUT_PANEL】\\n'
                '系统会自动截取标记中的 Markdown 内容推送到用户的输出面板（右侧可打开），方便用户预览和下载 .md 文件。')

    # 注入 USER profile（用户是谁、偏好、禁忌）
    user_file = os.path.join(profile_dir, 'USER.md')
    if os.path.exists(user_file):
        with open(user_file) as f:
            user_content = f.read().strip()
        if user_content:
            parts.append(f'【用户信息】\n{user_content}')

    # 注入 MEMORY（技术环境、项目配置、经验教训）
    mem_file = os.path.join(profile_dir, 'MEMORY.md')
    if os.path.exists(mem_file):
        with open(mem_file) as f:
            mem_content = f.read().strip()
        if mem_content:
            parts.append(f'【你的记忆与知识】\n{mem_content}')

    # Agent 人物画像（如数据库中有）
    if agent_portrait:
        parts.append(f'【人物画像】\n{agent_portrait}')

    return '\n\n---\n\n'.join(parts)


def _call_llm_for_reply(conversation_id: int, agent_portrait: str = ''):
    """在后台线程中调用 LLM 生成回复，并写入数据库"""
    try:
        from .models import Conversation, Message

        conv = Conversation.objects.select_related('agent').get(id=conversation_id)
        # 取最近 20 条消息作为上下文
        history = conv.messages.order_by('-created_at')[:20]
        history = list(reversed(history))  # 按时间正序

        # 构建 messages — 使用注入 memory 的系统提示词
        messages = [{'role': 'system', 'content': _build_system_prompt(agent_portrait)}]

        for msg in history:
            role = 'assistant' if msg.role in ('agent', 'system') else 'user'
            messages.append({'role': role, 'content': msg.content})

        # 调用 DeepSeek API
        resp = requests.post(
            f"{LLM_CONFIG['base_url']}/v1/chat/completions",
            headers={
                'Authorization': f"Bearer {LLM_CONFIG['api_key']}",
                'Content-Type': 'application/json',
            },
            json={
                'model': LLM_CONFIG['model'],
                'messages': messages,
                'max_tokens': LLM_CONFIG['max_tokens'],
                'temperature': LLM_CONFIG['temperature'],
            },
            timeout=30,
        )
        resp.raise_for_status()
        reply = resp.json()['choices'][0]['message']['content']

        # 写入 Agent 回复
        Message.objects.create(
            conversation=conv,
            role=Message.Role.AGENT,
            content=reply,
        )
    except Exception as e:
        # 失败时写入错误消息
        try:
            from .models import Conversation, Message
            conv = Conversation.objects.get(id=conversation_id)
            Message.objects.create(
                conversation=conv,
                role=Message.Role.AGENT,
                content=f'⚠️ 回复生成失败: {str(e)}',
            )
        except Exception:
            pass  # 静默失败，避免影响主流程

from .models import (
    CapabilityTag, Agent, Skill, AgentSkill,
    Task, ExecutionLog, KnowledgeEntry, CronExecution, CronJob,
    Conversation, Message,
)
from .auth import AgentEndpointPermission
from .serializers import (
    CapabilityTagSerializer, CapabilityTagBriefSerializer,
    AgentSerializer, AgentBriefSerializer,
    AgentRegisterSerializer, AgentHeartbeatSerializer,
    AgentConfigUpdateSerializer, AgentRevealConfigSerializer,
    SkillSerializer, SkillBriefSerializer,
    AgentSkillSerializer, AgentSkillAssignSerializer,
    TaskSerializer, TaskCreateSerializer, TaskDetailSerializer,
    TaskStatusUpdateSerializer, TaskBriefSerializer,
    ExecutionLogSerializer,
    KnowledgeEntrySerializer,
    CronExecutionSerializer,
    CronJobSerializer,
    MessageSerializer,
    ConversationSerializer,
    ConversationListSerializer,
)


# ═══════════════════════════════════════════════
# 调度引擎
# ═══════════════════════════════════════════════

class TaskDispatchEngine:
    """
    Agent 按需拉取任务的核心逻辑。

    流程：
      1. Agent 调用 POST /api/agents/{id}/pull-tasks/
      2. 引擎查询该 Agent 的能力标签 → 匹配 Skill
      3. 找到 status=pending 的任务 → 按优先级排序
      4. 检查 parent_task 依赖 → 父任务未完成则跳过
      5. 分配任务给 Agent，附上 skill 文件 + knowledge 知识
      6. 返回任务包 JSON
    """

    MAX_TASKS_PER_PULL = 3

    def __init__(self, agent):
        self.agent = agent
        self.assigned_tasks = []

    def pull_tasks(self) -> list[dict]:
        """拉取可执行的任务，返回任务包列表"""
        agent_caps = self.agent.capabilities.values_list('id', flat=True)

        # 查找待分配任务：agent 为 NULL 或已分配给该 agent
        pending = Task.objects.filter(status=Task.Status.PENDING).order_by(
            '-priority', 'created_at'
        ).prefetch_related(
            'assigned_skills', 'subtasks',
        )

        task_packages = []
        for task in pending:
            if len(task_packages) >= self.MAX_TASKS_PER_PULL:
                break

            # 依赖检查：父任务必须已完成
            if task.parent_task and task.parent_task.status != Task.Status.COMPLETED:
                continue

            # 分配
            task_package = self._assign_task(task)
            if task_package:
                task_packages.append(task_package)

        return task_packages

    def _assign_task(self, task: Task) -> dict | None:
        """分配单个任务，写入 task.agent + 状态变更"""
        with transaction.atomic():
            task.agent = self.agent
            task.status = Task.Status.ASSIGNED
            task.started_at = timezone.now()
            task.save(update_fields=['agent', 'status', 'started_at'])

            # 收集关联的 Skill 文件 URL 和 Knowledge
            skills_info = []
            for skill in task.assigned_skills.filter(status=Skill.Status.ACTIVE):
                skills_info.append({
                    'name': skill.name,
                    'slug': skill.slug,
                    'version': skill.version,
                    'file_url': skill.file_url,
                    'file_hash': skill.file_hash,
                })

            # 知识注入：读取 task.knowledge_refs 或根据 skills 自动匹配
            knowledge_ids = task.knowledge_refs or []
            if not knowledge_ids and task.assigned_skills.exists():
                skill_ids = task.assigned_skills.values_list('id', flat=True)
                knowledge_ids = KnowledgeEntry.objects.filter(
                    related_skills__in=skill_ids,
                    visibility__in=['public', 'team'],
                    entry_type__in=['solution', 'best_practice', 'pitfall'],
                ).order_by('-relevance_score').values_list('id', flat=True)[:5]

            knowledge_list = list(
                KnowledgeEntry.objects.filter(id__in=knowledge_ids).values(
                    'id', 'title', 'entry_type', 'relevance_score',
                )
            )

            task_package = {
                'task_id': task.id,
                'title': task.title,
                'description': task.description,
                'contract': task.contract,
                'context': task.context,
                'skills': skills_info,
                'knowledge': knowledge_list,
                'priority': task.priority,
                'deadline': task.deadline.isoformat() if task.deadline else None,
            }

            # 记录调度日志
            ExecutionLog.objects.create(
                task=task,
                agent=self.agent,
                level='info',
                message=f'任务已分配给 Agent {self.agent.name}，携带 {len(skills_info)} 个 Skill、{len(knowledge_list)} 条知识',
            )

            self.assigned_tasks.append(task)
            return task_package


# ═══════════════════════════════════════════════
# Pagination
# ═══════════════════════════════════════════════

class StandardPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 200


# ═══════════════════════════════════════════════
# CapabilityTag ViewSet
# ═══════════════════════════════════════════════

class CapabilityTagViewSet(viewsets.ModelViewSet):
    queryset = CapabilityTag.objects.annotate(
        agent_count=Count('agents')
    ).order_by('name')
    serializer_class = CapabilityTagSerializer
    permission_classes = [AgentEndpointPermission]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'slug']
    lookup_field = 'slug'


# ═══════════════════════════════════════════════
# Agent ViewSet（含心跳、分配 Skill、拉取任务）
# ═══════════════════════════════════════════════

class AgentViewSet(viewsets.ModelViewSet):
    queryset = Agent.objects.prefetch_related('capabilities').annotate(
        task_count=Count('tasks')
    ).order_by('-created_at')
    serializer_class = AgentSerializer
    permission_classes = [AgentEndpointPermission]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    search_fields = ['name', 'feishu_app_id']
    filterset_fields = ['status']
    pagination_class = StandardPagination

    def get_serializer_class(self):
        if self.action == 'register':
            return AgentRegisterSerializer
        return super().get_serializer_class()

    @action(detail=False, methods=['post'], url_path='register')
    def register(self, request):
        """Agent 注册（飞书机器人首次接入）"""
        serializer = AgentRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        agent = serializer.save()
        # 注册时返回 secret_key，之后不再暴露
        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['post'], url_path='heartbeat')
    def heartbeat(self, request, pk=None):
        """Agent 心跳上报"""
        agent = self.get_object()
        serializer = AgentHeartbeatSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        agent.status = serializer.validated_data.get('status', 'online')
        agent.last_heartbeat = timezone.now()
        if 'version' in serializer.validated_data:
            agent.version = serializer.validated_data['version']
        agent.save(update_fields=['status', 'last_heartbeat', 'version'])

        return Response({
            'status': 'ok',
            'timestamp': agent.last_heartbeat.isoformat(),
            'pending_tasks': agent.tasks.filter(status='pending').count(),
        })

    @action(detail=True, methods=['post'], url_path='assign-skill')
    def assign_skill(self, request, pk=None):
        """为 Agent 分配 Skill"""
        agent = self.get_object()
        serializer = AgentSkillAssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        skill = get_object_or_404(
            Skill, slug=serializer.validated_data['skill_slug']
        )

        assignment, created = AgentSkill.objects.update_or_create(
            agent=agent, skill=skill,
            defaults={
                'is_active': serializer.validated_data['is_active'],
                'assigned_by': request.user if request.user.is_authenticated else None,
            },
        )

        return Response(
            AgentSkillSerializer(assignment).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @action(detail=True, methods=['post'], url_path='config')
    def update_config(self, request, pk=None):
        """更新 Agent 配置（公开 + 加密敏感信息）"""
        agent = self.get_object()
        serializer = AgentConfigUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        from .crypto_utils import encrypt_config
        updated = []

        if 'config_public' in serializer.validated_data:
            agent.config_public = serializer.validated_data['config_public']
            updated.append('config_public')

        if 'config_secret' in serializer.validated_data:
            agent.config_encrypted = encrypt_config(serializer.validated_data['config_secret'])
            updated.append('config_secret')

        if 'portrait' in serializer.validated_data:
            agent.portrait = serializer.validated_data['portrait']
            updated.append('portrait')

        if updated:
            agent.save(update_fields=updated + ['updated_at'])

        return Response({
            'status': 'ok',
            'updated': updated,
        })

    @action(detail=True, methods=['post'], url_path='reveal-config')
    def reveal_config(self, request, pk=None):
        """验证管理员密码后返回完整配置（含明文 API Key）"""
        agent = self.get_object()
        serializer = AgentRevealConfigSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # 验证密码：使用 Django admin 用户的密码
        from django.contrib.auth import authenticate
        password = serializer.validated_data['password']

        # 检查是否为 admin 用户
        user = authenticate(username='admin', password=password)
        if not user or not user.is_superuser:
            return Response(
                {'error': '密码错误或无权限'},
                status=status.HTTP_403_FORBIDDEN,
            )

        from .crypto_utils import decrypt_config
        if not agent.config_encrypted:
            return Response({'config': {}, 'message': '无加密配置'})

        try:
            config = decrypt_config(agent.config_encrypted)
            return Response({
                'config': config,
                'message': '解密成功（此配置仅本次请求可见）',
            })
        except Exception as e:
            return Response(
                {'error': f'解密失败: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=['post'], url_path='pull-tasks')
    def pull_tasks(self, request, pk=None):
        """
        🎯 调度引擎入口：Agent 主动拉取任务

        Agent 调用此端点 → 引擎匹配任务 → 返回任务包
        （含 Skill 文件 URL + Knowledge 知识注入）
        """
        agent = self.get_object()

        # 更新心跳
        agent.last_heartbeat = timezone.now()
        agent.status = Agent.Status.ONLINE
        agent.save(update_fields=['last_heartbeat', 'status'])

        # 调度
        engine = TaskDispatchEngine(agent)
        task_packages = engine.pull_tasks()

        return Response({
            'agent': agent.name,
            'tasks': task_packages,
            'task_count': len(task_packages),
            'hint': '执行完每个任务后，POST /api/tasks/{task_id}/status/ 回报状态',
        })


# ═══════════════════════════════════════════════
# Skill ViewSet
# ═══════════════════════════════════════════════

class SkillViewSet(viewsets.ModelViewSet):
    queryset = Skill.objects.all().order_by('-updated_at')

    def get_queryset(self):
        qs = super().get_queryset()
        agent_id = self.request.query_params.get('agent')
        if agent_id:
            qs = qs.filter(agent_assignments__agent_id=agent_id, agent_assignments__is_active=True)
        return qs
    serializer_class = SkillSerializer
    permission_classes = [AgentEndpointPermission]
    pagination_class = StandardPagination
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    search_fields = ['name', 'slug', 'description']
    filterset_fields = ['status', 'source', 'category']
    lookup_field = 'slug'


# ═══════════════════════════════════════════════
# Task ViewSet（含状态回报、执行日志）
# ═══════════════════════════════════════════════

class TaskViewSet(viewsets.ModelViewSet):
    queryset = Task.objects.select_related(
        'agent', 'parent_task',
    ).prefetch_related(
        'assigned_skills', 'subtasks',
    ).annotate(
        log_count=Count('execution_logs'),
        subtask_count=Count('subtasks'),
    ).order_by('-created_at')
    serializer_class = TaskSerializer
    permission_classes = [AgentEndpointPermission]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    search_fields = ['title', 'description']
    filterset_fields = ['status', 'priority', 'agent']
    pagination_class = StandardPagination

    def get_serializer_class(self):
        if self.action == 'create':
            return TaskCreateSerializer
        if self.action == 'retrieve':
            return TaskDetailSerializer
        return super().get_serializer_class()

    def perform_create(self, serializer):
        task = serializer.save()
        # 自动匹配 Agent：如果有能力标签匹配的就分配
        # （这里留给调度引擎做主逻辑，create 只存任务）
        return task

    @action(detail=True, methods=['post'], url_path='status')
    def update_status(self, request, pk=None):
        """Agent 回报任务状态（running → completed/failed）"""
        task = self.get_object()
        serializer = TaskStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        new_status = serializer.validated_data['status']
        task.status = new_status

        extra = {}

        if new_status == 'completed':
            task.completed_at = timezone.now()
            task.result = serializer.validated_data.get('result', {})

            # 🔗 依赖链自动触发
            subtasks = task.subtasks.filter(status=Task.Status.PENDING)
            triggered = 0
            for child in subtasks:
                # 检查是否所有父任务都已完成
                incomplete_parents = child.parent_task
                if incomplete_parents is None or incomplete_parents.status == Task.Status.COMPLETED:
                    # 父任务全部完成 → 子任务可被拉取
                    # 如果当前 Agent 在线，尝试直接分配
                    if task.agent and task.agent.status == Agent.Status.ONLINE:
                        engine = TaskDispatchEngine(task.agent)
                        # 子任务已可拉取，下次 pull 会拿到
                        pass
                    triggered += 1

            if triggered:
                ExecutionLog.objects.create(
                    task=task, agent=task.agent,
                    level='info',
                    message=f'依赖链触发：父任务完成，{triggered} 个子任务自动解锁',
                )
                extra['dependency_triggered'] = triggered

        elif new_status == 'failed':
            task.result = serializer.validated_data.get('result', {})

            # 标记子任务为 cancelled（父失败，子无意义）
            subtasks = task.subtasks.filter(
                status__in=[Task.Status.PENDING, Task.Status.ASSIGNED]
            )
            cancelled = subtasks.update(status=Task.Status.CANCELLED)
            if cancelled:
                ExecutionLog.objects.create(
                    task=task, agent=task.agent,
                    level='warning',
                    message=f'父任务失败，{cancelled} 个子任务已自动取消',
                )
                extra['children_cancelled'] = cancelled

        task.save()

        response = {
            'task_id': task.id,
            'status': task.status,
            'message': f'任务状态已更新为 {task.get_status_display()}',
        }
        response.update(extra)
        return Response(response)

    @action(detail=True, methods=['post'], url_path='logs')
    def add_log(self, request, pk=None):
        """Agent 上报执行日志"""
        task = self.get_object()
        data = request.data.copy()
        data['task'] = task.id
        data['agent'] = task.agent_id or (request.data.get('agent'))

        serializer = ExecutionLogSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        log = serializer.save()

        return Response(
            ExecutionLogSerializer(log).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['get'], url_path='logs')
    def list_logs(self, request, pk=None):
        """查看任务执行日志"""
        task = self.get_object()
        logs = task.execution_logs.all().order_by('-created_at')
        page = self.paginate_queryset(logs)
        if page is not None:
            return self.get_pagination_response(
                ExecutionLogSerializer(page, many=True).data
            )
        return Response(ExecutionLogSerializer(logs, many=True).data)

    @action(detail=True, methods=['post'], url_path='cancel')
    def cancel_task(self, request, pk=None):
        """强制取消任务"""
        task = self.get_object()
        if task.status in (Task.Status.COMPLETED, Task.Status.CANCELLED):
            return Response({'ok': False, 'message': '任务已完成或已取消'})
        task.status = Task.Status.CANCELLED
        task.save()
        # 取消子任务
        task.subtasks.filter(status__in=['pending', 'assigned', 'in_progress', 'running']).update(status=Task.Status.CANCELLED)
        return Response({'ok': True, 'message': '任务已取消'})

    @action(detail=False, methods=['post'], url_path='batch-cancel')
    def batch_cancel(self, request):
        """批量取消任务"""
        ids = request.data.get('ids', [])
        if not ids:
            return Response({'ok': False, 'message': '未指定任务 ID'})
        updated = Task.objects.filter(id__in=ids).exclude(
            status__in=[Task.Status.COMPLETED, Task.Status.CANCELLED]
        ).update(status=Task.Status.CANCELLED)
        return Response({'ok': True, 'cancelled': updated})

    @action(detail=False, methods=['post'], url_path='batch-delete')
    def batch_delete(self, request):
        """批量删除任务"""
        ids = request.data.get('ids', [])
        if not ids:
            return Response({'ok': False, 'message': '未指定任务 ID'})
        deleted, _ = Task.objects.filter(id__in=ids).delete()
        return Response({'ok': True, 'deleted': deleted})


# ═══════════════════════════════════════════════
# KnowledgeEntry ViewSet
# ═══════════════════════════════════════════════

class KnowledgeEntryViewSet(viewsets.ModelViewSet):
    queryset = KnowledgeEntry.objects.select_related(
        'source_agent', 'source_task',
    ).prefetch_related(
        'related_skills',
    ).order_by('-relevance_score', '-created_at')
    serializer_class = KnowledgeEntrySerializer
    permission_classes = [AgentEndpointPermission]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    search_fields = ['title', 'content', 'tags']
    filterset_fields = ['entry_type', 'visibility']
    pagination_class = StandardPagination


# ═══════════════════════════════════════════════
# CronExecution ViewSet
# ═══════════════════════════════════════════════

class CronExecutionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CronExecution.objects.all().order_by('-created_at')
    serializer_class = CronExecutionSerializer
    permission_classes = [AgentEndpointPermission]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    search_fields = ['name', 'job_id']
    filterset_fields = ['status', 'job_id', 'agent', 'source']
    pagination_class = StandardPagination


# ═══════════════════════════════════════════════
# CronJob ViewSet — 定时任务定义
# ═══════════════════════════════════════════════

class CronJobViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CronJob.objects.select_related('agent').order_by('name')
    serializer_class = CronJobSerializer
    permission_classes = [AgentEndpointPermission]
    pagination_class = StandardPagination


# ═══════════════════════════════════════════════
# Conversation & Message ViewSets
# ═══════════════════════════════════════════════

class ConversationViewSet(viewsets.ModelViewSet):
    queryset = Conversation.objects.select_related('agent').prefetch_related('messages').order_by('-created_at')
    permission_classes = [AgentEndpointPermission]
    pagination_class = StandardPagination

    def get_serializer_class(self):
        if self.action == 'list':
            return ConversationListSerializer
        return ConversationSerializer

    def perform_create(self, serializer):
        agent = serializer.validated_data.get('agent')
        feishu_chat_id = serializer.validated_data.get('feishu_chat_id', '')

        # 飞书消息：按 feishu_chat_id 匹配
        if feishu_chat_id:
            existing = Conversation.objects.filter(feishu_chat_id=feishu_chat_id).first()
            if existing:
                serializer.instance = existing
                return

        # Web / 非飞书：同一 agent 优先复用任何已有对话（含飞书对话）
        if agent and not feishu_chat_id:
            # 优先复用已有的飞书对话（跨端统一）
            existing = Conversation.objects.filter(agent=agent).first()
            if existing:
                serializer.instance = existing
                return

        conversation = serializer.save()
        Message.objects.create(
            conversation=conversation,
            role=Message.Role.SYSTEM,
            content=f'对话已创建 — 与 {conversation.agent.name if conversation.agent else "Agent"} 的会话',
        )

    @action(detail=True, methods=['get'], url_path='orchestration-progress')
    def orchestration_progress(self, request, pk=None):
        """返回该对话的编排任务进度"""
        conversation = self.get_object()
        tasks = Task.objects.filter(
            contract__orchestrator=True,
            contract__conversation_id=conversation.id,
        ).order_by('created_at')

        if not tasks.exists():
            return Response({'active': False})

        total = tasks.count()
        done = tasks.filter(status__in=['completed', 'failed', 'cancelled']).count()
        running = tasks.filter(status='in_progress').count()
        pending = tasks.filter(status='pending').count()

        current = None
        if running:
            t = tasks.filter(status='in_progress').first()
            current = t.title[:80] if t else None

        return Response({
            'active': True,
            'total': total,
            'done': done,
            'running': running,
            'pending': pending,
            'current_step': current,
            'plan_id': tasks.first().contract.get('plan_id') if tasks.first() else None,
        })


    @action(detail=True, methods=['post'], url_path='stop')
    def stop_orchestration(self, request, pk=None):
        """强制停止该对话的编排任务"""
        conversation = self.get_object()
        try:
            from redis import Redis
            r = Redis.from_url("redis://localhost:6379/0")
            r.set(f"orch:stop:{conversation.id}", "1", ex=300)
            r.set(f"orch:state:{conversation.id}", "stopped")
            from .models import Task
            Task.objects.filter(
                contract__orchestrator=True,
                contract__conversation_id=conversation.id,
                status__in=['pending', 'in_progress', 'running'],
            ).update(status='cancelled')
        except Exception as e:
            print(f"[stop_orchestration] Redis error: {e}")
        return Response({'ok': True, 'stopped': True})

    @action(detail=True, methods=['post'], url_path='pause')
    def pause_orchestration(self, request, pk=None):
        """暂停该对话的编排任务"""
        conversation = self.get_object()
        try:
            from redis import Redis
            r = Redis.from_url("redis://localhost:6379/0")
            r.set(f"orch:pause:{conversation.id}", "1", ex=300)
            r.set(f"orch:state:{conversation.id}", "paused")
        except Exception as e:
            print(f"[pause_orchestration] Redis error: {e}")
        return Response({'ok': True, 'paused': True})

    @action(detail=True, methods=['get'], url_path='orch-state')
    def orch_state(self, request, pk=None):
        conversation = self.get_object()
        state = 'idle'
        try:
            from redis import Redis
            r = Redis.from_url("redis://localhost:6379/0")
            raw = r.get(f"orch:state:{conversation.id}")
            if raw:
                state = raw.decode() if isinstance(raw, bytes) else raw
        except Exception:
            pass
        return Response({'state': state})

    @action(detail=True, methods=['post'], url_path='set-output')
    def set_output(self, request, pk=None):
        """Agent 推送文档到输出面板。请求体: {content: 'markdown...'}"""
        conversation = self.get_object()
        content = request.data.get('content', '')
        if not isinstance(content, str):
            return Response({'error': 'content must be a string'}, status=400)
        conversation.output_content = content
        conversation.save(update_fields=['output_content'])
        return Response({'ok': True, 'length': len(content)})

    @action(detail=True, methods=['get'], url_path='get-output')
    def get_output(self, request, pk=None):
        """前端轮询获取输出面板内容"""
        conversation = self.get_object()
        return Response({'content': conversation.output_content})


class MessageViewSet(viewsets.ModelViewSet):
    queryset = Message.objects.select_related('conversation', 'task').order_by('created_at')
    serializer_class = MessageSerializer
    permission_classes = [AgentEndpointPermission]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['conversation', 'role']
    pagination_class = StandardPagination

    def perform_create(self, serializer):
        message = serializer.save()
        conv = message.conversation
        # 用第一条用户消息更新对话标题
        if message.role == Message.Role.USER and conv.title == '新对话':
            conv.title = message.content[:40] + ('...' if len(message.content) > 40 else '')
            conv.save(update_fields=['title'])

        # 🎯 用户消息 → Redis 队列实时处理
        if message.role == Message.Role.USER:
            try:
                from redis import Redis
                r = Redis.from_url("redis://localhost:6379/0")
                r.lpush("msg_queue", message.id)
            except Exception as e:
                print(f"[MessageViewSet] Redis push failed: {e}")

        # 📄 Agent 回复中提取输出面板内容
        if message.role == Message.Role.AGENT and '【OUTPUT_PANEL】' in message.content:
            import re
            m = re.search(r'【OUTPUT_PANEL】\s*\n?(.*?)\n?\s*【/OUTPUT_PANEL】', message.content, re.DOTALL)
            if m:
                conv.output_content = m.group(1).strip()
                conv.save(update_fields=['output_content'])

    @action(detail=False, methods=['get'], url_path='pending')
    def pending_messages(self, request):
        """Hermes Agent 拉取待处理消息（不自动标记）"""
        messages = Message.objects.filter(
            role=Message.Role.USER,
            processed=False,
        ).select_related('conversation__agent').order_by('created_at')[:5]

        result = []
        for msg in messages:
            history = []
            if msg.conversation:
                prev = msg.conversation.messages.filter(
                    created_at__lt=msg.created_at
                ).order_by('-created_at')[:20]
                for m in reversed(list(prev)):
                    history.append({
                        'id': m.id,
                        'role': m.role,
                        'content': m.content,
                    })

            result.append({
                'id': msg.id,
                'conversation_id': msg.conversation_id,
                'content': msg.content,
                'source': msg.source,
                'feishu_chat_id': msg.conversation.feishu_chat_id if msg.conversation else None,
                'agent_id': msg.conversation.agent_id if msg.conversation else None,
                'agent_name': msg.conversation.agent.name if msg.conversation.agent else None,
                'agent_portrait': msg.conversation.agent.portrait if msg.conversation.agent else None,
                'agent_model': (msg.conversation.agent.config_public or {}).get('model', 'deepseek-chat') if msg.conversation.agent else 'deepseek-chat',
                'agent_profile': (msg.conversation.agent.config_public or {}).get('profile', 'banni') if msg.conversation.agent else 'banni',
                'created_at': msg.created_at.isoformat(),
                'history': history,
            })

        return Response({'messages': result, 'count': len(result)})

    @action(detail=False, methods=['post'], url_path='mark-processed')
    def mark_processed(self, request):
        """Hermes Agent 标记消息为已处理"""
        ids = request.data.get('ids', [])
        if ids:
            Message.objects.filter(id__in=ids, role='user').update(processed=True)
        return Response({'ok': True, 'count': len(ids)})



@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def system_workers(request):
    """返回所有 Worker/服务的实时状态"""
    import subprocess, redis as redis_lib, os, time

    workers = []
    services = [
        {'name': 'agent-backend', 'label': 'API 后端', 'icon': '🔌', 'port': 8001},
        {'name': 'agent-frontend', 'label': 'Web 前端', 'icon': '🌐', 'port': 5174},
        {'name': 'agent-worker', 'label': '消息 Worker', 'icon': '📨', 'desc': 'Redis 事件驱动，处理飞书/Web 消息'},
        {'name': 'orch-daemon', 'label': '编排守护进程', 'icon': '🎯', 'desc': '30s 轮询，执行编排任务'},
    ]

    for svc in services:
        try:
            r = subprocess.run(
                ['systemctl', '--user', 'show', svc['name'],
                 '--property=ActiveState,SubState,ExecMainPID,ActiveEnterTimestampMonotonic,MemoryCurrent'],
                capture_output=True, text=True, timeout=5,
                env={**os.environ, 'HOME': '/home/jiangli'}
            )
            info = {}
            for line in r.stdout.strip().split('\n'):
                if '=' in line:
                    k, v = line.split('=', 1)
                    info[k] = v

            pid = info.get('ExecMainPID', '0')
            active = info.get('ActiveState', 'unknown')
            substate = info.get('SubState', '')

            # 计算运行时长
            uptime_sec = 0
            mono_raw = info.get('ActiveEnterTimestampMonotonic', 'MISSING')
            if mono_raw and mono_raw != 'MISSING' and mono_raw.isdigit():
                try:
                    with open('/proc/uptime') as f:
                        sys_uptime = float(f.readline().split()[0])
                    boot_time = time.time() - sys_uptime
                    started_real = boot_time + int(mono_raw) / 1_000_000
                    uptime_sec = int(time.time() - started_real)
                except Exception as e:
                    uptime_sec = -1  # signal error
            elif mono_raw == 'MISSING':
                uptime_sec = -2  # key missing

            # 内存使用
            mem = info.get('MemoryCurrent', '0')
            mem_mb = int(mem) / (1024 * 1024) if mem and mem != '[not set]' else 0

            # 端口检查
            port_ok = None
            if 'port' in svc:
                try:
                    import socket
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.settimeout(1)
                    port_ok = s.connect_ex(('127.0.0.1', svc['port'])) == 0
                    s.close()
                except Exception:
                    port_ok = False

            workers.append({
                'name': svc['name'],
                'label': svc['label'],
                'icon': svc['icon'],
                'desc': svc.get('desc', ''),
                'status': active,
                'substate': substate,
                'pid': int(pid) if pid and pid.isdigit() else 0,
                'uptime_seconds': uptime_sec,
                'uptime_display': f'{uptime_sec // 3600}h {(uptime_sec % 3600) // 60}m' if uptime_sec > 0 else '—',
                'memory_mb': round(mem_mb, 1),
                'port': svc.get('port'),
                'port_ok': port_ok,
            })
        except Exception as e:
            workers.append({
                'name': svc['name'], 'label': svc['label'], 'icon': svc['icon'],
                'status': 'error', 'error': str(e),
            })

    # Redis 连接检查
    redis_status = 'disconnected'
    try:
        r = redis_lib.Redis.from_url('redis://localhost:6379/0')
        r.ping()
        redis_status = 'connected'
    except Exception:
        pass

    # 坑位记忆统计
    pitfall_stats = {}
    try:
        from .pitfall_memory import get_stats
        pitfall_stats = get_stats()
    except Exception:
        pass

    return Response({
        'workers': workers,
        'redis': redis_status,
        'pitfalls': pitfall_stats,
        'timestamp': time.time(),
    })


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def system_pipeline(request):
    """全链路状态监控：Worker → Redis → Hermes AI → 回复"""
    import subprocess, redis as redis_lib, os, time, sqlite3

    result = {
        'worker': {},
        'redis_queue': {},
        'hermes_engine': {},
        'messages': {},
        'timestamp': time.time(),
    }

    # ── 1. Worker 状态 ──
    try:
        r = subprocess.run(
            ['systemctl', '--user', 'show', 'agent-worker',
             '--property=ActiveState,ExecMainPID,ActiveEnterTimestampMonotonic,MemoryCurrent'],
            capture_output=True, text=True, timeout=5,
            env={**os.environ, 'HOME': '/home/jiangli'}
        )
        info = {}
        for line in r.stdout.strip().split('\n'):
            if '=' in line:
                k, v = line.split('=', 1)
                info[k] = v
        active = info.get('ActiveState', 'unknown')
        pid = info.get('ExecMainPID', '0')
        result['worker'] = {
            'status': active,
            'pid': int(pid) if pid and pid.isdigit() else 0,
            'version': 'v4.2',
            'concurrency': 3,
        }
        # 运行时长
        mono_raw = info.get('ActiveEnterTimestampMonotonic', '')
        if mono_raw and mono_raw.isdigit():
            with open('/proc/uptime') as f:
                sys_uptime = float(f.readline().split()[0])
            boot_time = time.time() - sys_uptime
            started_real = boot_time + int(mono_raw) / 1_000_000
            uptime_sec = int(time.time() - started_real)
            result['worker']['uptime_seconds'] = uptime_sec
            result['worker']['uptime_display'] = f'{uptime_sec // 3600}h {(uptime_sec % 3600) // 60}m {uptime_sec % 60}s'
    except Exception as e:
        result['worker'] = {'status': 'error', 'error': str(e)}

    # ── 2. Redis 队列 ──
    try:
        rds = redis_lib.Redis.from_url('redis://localhost:6379/0')
        rds.ping()
        queue_len = rds.llen('msg_queue')
        # orchestrator 信号键
        orch_keys = rds.keys('orch:*') or []
        result['redis_queue'] = {
            'status': 'connected',
            'queue_name': 'msg_queue',
            'queue_length': queue_len,
            'blocked': 'waiting' if queue_len == 0 else 'processing',
            'orch_signals': len(orch_keys),
        }
    except Exception as e:
        result['redis_queue'] = {'status': 'disconnected', 'error': str(e)}

    # ── 3. Hermes AI 引擎 ──
    try:
        ps = subprocess.run(
            ['pgrep', '-a', 'hermes'], capture_output=True, text=True, timeout=3
        )
        hermes_procs = []
        for line in ps.stdout.strip().split('\n'):
            if line.strip():
                hermes_procs.append(line.strip())
        result['hermes_engine'] = {
            'status': 'active' if hermes_procs else 'idle',
            'active_processes': len(hermes_procs),
            'details': hermes_procs[:5],
        }
    except Exception as e:
        result['hermes_engine'] = {'status': 'unknown', 'error': str(e)}

    # ── 4. 消息统计 ──
    try:
        db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'db.sqlite3')
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM messages")
        total = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM messages WHERE role='user' AND processed=1")
        processed = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM messages WHERE role='user' AND processed=0")
        pending = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM messages WHERE role='agent'")
        replies = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM messages WHERE created_at > datetime('now', '-5 minutes')")
        recent_5m = c.fetchone()[0]
        conn.close()
        result['messages'] = {
            'total': total,
            'processed': processed,
            'pending': pending,
            'replies': replies,
            'last_5min': recent_5m,
        }
    except Exception as e:
        result['messages'] = {'error': str(e)}

    return Response(result)


# ═══════════════════════════════════════════════
# 任务节点可视化 — Task Graph API（Basir 方案）
# ═══════════════════════════════════════════════

@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def parent_task_graph(request, pk):
    """返回父任务的完整执行图：nodes + edges + 卡点检测"""
    from .models import ParentTask, TaskNode  # noqa: F811
    from .serializers import TaskNodeSerializer  # noqa: F811

    try:
        pt = ParentTask.objects.prefetch_related('task_nodes').get(pk=pk)
    except ParentTask.DoesNotExist:
        return Response({'error': '父任务不存在'}, status=404)

    nodes = pt.task_nodes.all()

    # 如果没有 TaskNode 但有 dispatch_plan，从 plan 构建节点
    if not nodes.exists() and pt.dispatch_plan:
        plan_data = pt.dispatch_plan
        # 尝试 PlanGraph 格式
        if 'nodes' in plan_data:
            TaskNode.build_from_plan(pt, plan_data)
            nodes = pt.task_nodes.all()
        # 尝试 orchestrator ExecutionPlan 格式
        elif 'steps' in plan_data:
            steps = plan_data.get('steps', [])
            for i, step in enumerate(steps):
                TaskNode.objects.create(
                    parent_task=pt,
                    node_id=step.get('id', f'step_{i+1}'),
                    label=step.get('note', step.get('id', f'步骤{i+1}'))[:128],
                    description=step.get('note', ''),
                    agent_name=step.get('agent', ''),
                    action=step.get('action', ''),
                    depends_on=step.get('depends_on', []),
                    seq=i + 1,
                )
            nodes = pt.task_nodes.all()

    # 如果已有 ChildTask 执行记录，同步状态到 TaskNode
    if pt.children.exists():
        child_map = {ct.id: ct for ct in pt.children.all()}
        for node in nodes:
            if node.child_task_id and node.child_task_id in child_map:
                ct = child_map[node.child_task_id]
                _sync_node_from_child(node, ct)

    # 卡点检测
    all_durations = [n.duration_ms for n in nodes if n.duration_ms > 0]
    bottleneck_threshold = 0
    if all_durations:
        all_durations.sort()
        cutoff = int(len(all_durations) * 0.75)
        bottleneck_threshold = all_durations[cutoff] if cutoff < len(all_durations) else all_durations[-1]
    else:
        bottleneck_threshold = 10000  # 默认 10 秒

    bottlenecks = []
    for node in nodes:
        # 重新标记卡点
        if node.status in ('done', 'running') and node.duration_ms >= max(bottleneck_threshold, 10000):
            node.is_bottleneck = True
            if not node.bottleneck_reason:
                node.bottleneck_reason = f'耗时 {node.duration_ms // 1000}s，超过阈值 {bottleneck_threshold // 1000}s'
        else:
            node.is_bottleneck = False
            node.bottleneck_reason = ''
        # 批量保存（不逐个 save 性能更好）
        if node.is_bottleneck:
            bottlenecks.append({
                'node_id': node.node_id,
                'label': node.label,
                'duration_ms': node.duration_ms,
                'reason': node.bottleneck_reason,
            })

    # 批量更新卡点字段
    TaskNode.objects.bulk_update(
        [n for n in nodes if n.is_bottleneck or not n.is_bottleneck],
        ['is_bottleneck', 'bottleneck_reason']
    )

    # 构建 edges（依赖关系）
    edges = []
    node_id_set = {n.node_id for n in nodes}
    for node in nodes:
        for dep in node.depends_on:
            if dep in node_id_set:
                edges.append({
                    'from': dep,
                    'to': node.node_id,
                })

    # 计数
    statuses = {n.status for n in nodes}
    completed_count = sum(1 for n in nodes if n.status == 'done')
    failed_count = sum(1 for n in nodes if n.status == 'failed')
    running_count = sum(1 for n in nodes if n.status == 'running')
    pending_count = sum(1 for n in nodes if n.status == 'pending')

    data = {
        'parent_task_id': pt.id,
        'parent_status': pt.status,
        'total_nodes': len(nodes),
        'completed_nodes': completed_count,
        'failed_nodes': failed_count,
        'running_nodes': running_count,
        'pending_nodes': pending_count,
        'bottlenecks': bottlenecks,
        'nodes': TaskNodeSerializer(nodes, many=True).data,
        'edges': edges,
    }

    return Response(data)


def _sync_node_from_child(node, child_task):
    """从 ChildTask 同步状态到 TaskNode"""
    node.status = {
        'PENDING': 'pending',
        'RUNNING': 'running',
        'DONE': 'done',
        'FAILED': 'failed',
        'TIMED_OUT': 'timed_out',
    }.get(child_task.status, 'pending')
    node.started_at = child_task.started_at
    node.finished_at = child_task.finished_at
    if child_task.started_at and child_task.finished_at and isinstance(child_task.finished_at, child_task.started_at.__class__):
        delta = child_task.finished_at - child_task.started_at
        node.duration_ms = int(delta.total_seconds() * 1000)
    node.save()


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def stop_parent_task(request, pk):
    """停止父任务及其所有子Agent进程"""
    from .models import ParentTask, TaskNode

    try:
        pt = ParentTask.objects.get(pk=pk)
    except ParentTask.DoesNotExist:
        return Response({'error': '任务不存在'}, status=404)

    # 标记父任务为 CANCELLED
    pt.status = 'CANCELLED'
    pt.save(update_fields=['status'])

    # 标记所有关联 TaskNode
    TaskNode.objects.filter(parent_task=pt, status__in=['pending', 'running']).update(
        status='cancelled'
    )

    # 通过 Redis 发停止信号（如果 Worker 在运行）
    try:
        from redis import Redis
        r = Redis.from_url("redis://localhost:6379/0")
        r.set(f"stop:parent_task:{pk}", "1", ex=300)
    except Exception:
        pass

    return Response({'ok': True, 'stopped': True})

@csrf_exempt
@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def login_view(request):
    username = request.data.get("username", "").strip()
    password = request.data.get("password", "")
    if not username or not password:
        return Response({"error": "请输入用户名和密码"}, status=400)
    user = authenticate(request, username=username, password=password)
    if user is None:
        return Response({"error": "用户名或密码错误"}, status=401)
    login(request, user)
    return Response({"ok": True, "user": {"id": user.id, "username": user.username, "is_staff": user.is_staff}})

@csrf_exempt
@api_view(['POST'])
def logout_view(request):
    """登出，清除 session"""
    logout(request)
    resp = Response({'ok': True})
    resp.delete_cookie('sessionid', path='/')
    return resp

@ensure_csrf_cookie
@api_view(['GET'])
def whoami_view(request):
    """验证当前登录状态"""
    if request.user.is_authenticated:
        return Response({
            'authenticated': True,
            'user': {
                'id': request.user.id,
                'username': request.user.username,
                'is_staff': request.user.is_staff,
            }
        })
    return Response({'authenticated': False})

@csrf_exempt
@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def register_view(request):
    from django.contrib.auth.models import User
    username = request.data.get("username", "").strip()
    password = request.data.get("password", "")
    password2 = request.data.get("password2", "")
    if not username or not password:
        return Response({"error": "用户名和密码不能为空"}, status=400)
    if len(username) < 3:
        return Response({"error": "用户名至少 3 个字符"}, status=400)
    if len(password) < 6:
        return Response({"error": "密码至少 6 个字符"}, status=400)
    if password != password2:
        return Response({"error": "两次密码不一致"}, status=400)
    if User.objects.filter(username=username).exists():
        return Response({"error": "用户名已被占用"}, status=409)
    user = User.objects.create_user(username=username, password=password, is_active=False, is_staff=False)
    return Response({"ok": True, "message": "注册成功，请等待管理员审批", "user_id": user.id}, status=201)

@api_view(["GET"])
def admin_list_users(request):
    if not request.user.is_authenticated or not request.user.is_staff:
        return Response({"error": "无权限"}, status=403)
    from django.contrib.auth.models import User
    users = User.objects.all().order_by("-date_joined").values("id","username","is_active","is_staff","date_joined","last_login")
    return Response(list(users))

@csrf_exempt
@api_view(["POST"])
def admin_approve_user(request, user_id):
    if not request.user.is_authenticated or not request.user.is_staff:
        return Response({"error": "无权限"}, status=403)
    from django.contrib.auth.models import User
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return Response({"error": "用户不存在"}, status=404)
    user.is_active = True
    user.save(update_fields=["is_active"])
    return Response({"ok": True, "username": user.username})

@csrf_exempt
@api_view(["POST"])
def admin_reject_user(request, user_id):
    if not request.user.is_authenticated or not request.user.is_staff:
        return Response({"error": "无权限"}, status=403)
    from django.contrib.auth.models import User
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return Response({"error": "用户不存在"}, status=404)
    username = user.username
    user.delete()
    return Response({"ok": True, "username": username})

@csrf_exempt
@api_view(["POST"])
def admin_reset_password(request, user_id):
    if not request.user.is_authenticated or not request.user.is_staff:
        return Response({"error": "无权限"}, status=403)
    from django.contrib.auth.models import User
    new_password = request.data.get("password", "")
    if not new_password or len(new_password) < 6:
        return Response({"error": "新密码至少 6 个字符"}, status=400)
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return Response({"error": "用户不存在"}, status=404)
    user.set_password(new_password)
    user.save(update_fields=["password"])
    return Response({"ok": True, "username": user.username})

@csrf_exempt
@api_view(["POST"])
def admin_add_user(request):
    if not request.user.is_authenticated or not request.user.is_staff:
        return Response({"error": "无权限"}, status=403)
    from django.contrib.auth.models import User
    username = request.data.get("username", "").strip()
    password = request.data.get("password", "")
    if not username or not password:
        return Response({"error": "用户名和密码不能为空"}, status=400)
    if len(password) < 6:
        return Response({"error": "密码至少 6 个字符"}, status=400)
    if User.objects.filter(username=username).exists():
        return Response({"error": "用户名已被占用"}, status=409)
    user = User.objects.create_user(username=username, password=password, is_active=True)
    return Response({"ok": True, "user": {"id": user.id, "username": user.username}}, status=201)
