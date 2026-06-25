"""
Agent Platform — Serializers

按照 DRF 最佳实践：
  - read_only_fields 显式声明
  - 嵌套序列化器控制深度
  - HyperlinkedIdentityField 用于关联
"""
from rest_framework import serializers
from django.db.models import Count
from .models import (
    CapabilityTag, Agent, Skill, AgentSkill,
    Task, ExecutionLog, KnowledgeEntry, CronExecution, CronJob,
    Conversation, Message, TaskNode, UploadedFile,
)


# ═══════════════════════════════════════════════
# CapabilityTag
# ═══════════════════════════════════════════════

class CapabilityTagSerializer(serializers.ModelSerializer):
    agent_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = CapabilityTag
        fields = ['id', 'name', 'slug', 'description', 'agent_count', 'created_at']
        read_only_fields = ['id', 'created_at']


class CapabilityTagBriefSerializer(serializers.ModelSerializer):
    """嵌套在 Agent 里用，只展示 name"""

    class Meta:
        model = CapabilityTag
        fields = ['id', 'name', 'slug']


# ═══════════════════════════════════════════════
# Agent
# ═══════════════════════════════════════════════

class AgentSerializer(serializers.ModelSerializer):
    capabilities = CapabilityTagBriefSerializer(many=True, read_only=True)
    task_count = serializers.IntegerField(read_only=True)
    skill_count = serializers.SerializerMethodField()
    # 只展示脱敏后的配置
    config_masked = serializers.SerializerMethodField()

    class Meta:
        model = Agent
        fields = [
            'id', 'name', 'feishu_app_id', 'webhook_url',
            'capabilities', 'status', 'last_heartbeat',
            'version', 'metadata', 'task_count', 'skill_count',
            'portrait', 'config_public', 'config_masked',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'status', 'last_heartbeat', 'created_at', 'updated_at',
        ]

    def get_skill_count(self, obj):
        return obj.skill_assignments.filter(is_active=True).count()

    def get_config_masked(self, obj):
        """返回脱敏后的加密配置"""
        from .crypto_utils import decrypt_config, mask_config
        if not obj.config_encrypted:
            return {}
        try:
            config = decrypt_config(obj.config_encrypted)
            return mask_config(config)
        except Exception:
            return {}


class AgentBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Agent
        fields = ['id', 'name', 'status', 'feishu_app_id']


class AgentRegisterSerializer(serializers.ModelSerializer):
    """Agent 注册专用（心跳逻辑用）"""
    capabilities = serializers.ListField(
        child=serializers.CharField(), write_only=True, required=False,
    )
    secret_key = serializers.CharField(read_only=True)

    class Meta:
        model = Agent
        fields = ['id', 'name', 'feishu_app_id', 'webhook_url', 'version', 'capabilities', 'secret_key', 'status']
        read_only_fields = ['id', 'secret_key', 'status']

    def create(self, validated_data):
        from .auth import AgentHMACAuthentication
        capability_names = validated_data.pop('capabilities', [])
        validated_data['secret_key'] = AgentHMACAuthentication.generate_secret_key()
        validated_data['status'] = Agent.Status.ONLINE
        agent = Agent.objects.create(**validated_data)
        for slug in capability_names:
            tag, _ = CapabilityTag.objects.get_or_create(slug=slug, defaults={'name': slug, 'slug': slug})
            agent.capabilities.add(tag)
        return agent


class AgentHeartbeatSerializer(serializers.Serializer):
    """心跳请求体"""
    status = serializers.ChoiceField(
        choices=['online', 'offline', 'busy', 'error'],
        default='online',
    )
    version = serializers.CharField(required=False, allow_blank=True)


class AgentConfigUpdateSerializer(serializers.Serializer):
    """更新 Agent 配置"""
    config_public = serializers.JSONField(required=False, default=dict)
    config_secret = serializers.JSONField(required=False, default=dict)  # 会被加密存储
    portrait = serializers.CharField(required=False, allow_blank=True)


class AgentRevealConfigSerializer(serializers.Serializer):
    """验证密码后返回完整配置"""
    password = serializers.CharField()


# ═══════════════════════════════════════════════
# Skill
# ═══════════════════════════════════════════════

class SkillSerializer(serializers.ModelSerializer):
    agent_count = serializers.SerializerMethodField()
    knowledge_count = serializers.SerializerMethodField()
    agent_names = serializers.SerializerMethodField()

    class Meta:
        model = Skill
        fields = [
            'id', 'name', 'name_zh', 'slug', 'version', 'description', 'description_zh', 'content',
            'file_url', 'file_hash', 'file_size',
            'source', 'status', 'category', 'tags',
            'meyo_skill_id', 'last_synced_at',
            'agent_count', 'knowledge_count', 'agent_names',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'file_size', 'last_synced_at', 'created_at', 'updated_at',
        ]

    def get_agent_count(self, obj):
        return obj.agent_assignments.filter(is_active=True).count()

    def get_knowledge_count(self, obj):
        return obj.knowledge_entries.count()

    def get_agent_names(self, obj):
        return list(
            obj.agent_assignments
            .filter(is_active=True)
            .select_related('agent')
            .values_list('agent__name', flat=True)
        )


class SkillBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skill
        fields = ['id', 'name', 'slug', 'version', 'category']


# ═══════════════════════════════════════════════
# AgentSkill — 分配关系
# ═══════════════════════════════════════════════

class AgentSkillSerializer(serializers.ModelSerializer):
    agent_name = serializers.CharField(source='agent.name', read_only=True)
    skill_name = serializers.CharField(source='skill.name', read_only=True)

    class Meta:
        model = AgentSkill
        fields = [
            'id', 'agent', 'agent_name', 'skill', 'skill_name',
            'is_active', 'assigned_at',
        ]
        read_only_fields = ['id', 'assigned_at']


class AgentSkillAssignSerializer(serializers.Serializer):
    """分配 Skill 请求体"""
    skill_slug = serializers.CharField()
    is_active = serializers.BooleanField(default=True)


# ═══════════════════════════════════════════════
# ExecutionLog
# ═══════════════════════════════════════════════

class ExecutionLogSerializer(serializers.ModelSerializer):
    agent_name = serializers.CharField(source='agent.name', read_only=True)

    class Meta:
        model = ExecutionLog
        fields = [
            'id', 'task', 'agent', 'agent_name',
            'level', 'message', 'quality_gate',
            'duration_ms', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']

    def create(self, validated_data):
        # 自动推进 Task 状态
        log = super().create(validated_data)
        task = log.task
        if log.level == 'error':
            task.status = Task.Status.FAILED
            task.save(update_fields=['status'])
        return log


# ═══════════════════════════════════════════════
# Task
# ═══════════════════════════════════════════════

class TaskSerializer(serializers.ModelSerializer):
    agent_name = serializers.CharField(source='agent.name', read_only=True)
    assigned_skills = SkillBriefSerializer(many=True, read_only=True)
    log_count = serializers.IntegerField(read_only=True)
    subtask_count = serializers.IntegerField(read_only=True)
    source_label = serializers.CharField(source='get_source_display', read_only=True)

    class Meta:
        model = Task
        fields = [
            'id', 'title', 'description',
            'contract', 'context', 'knowledge_refs',
            'agent', 'agent_name',
            'assigned_skills', 'parent_task',
            'conversation',
            'status', 'priority', 'source', 'source_label',
            'log_count', 'subtask_count',
            'result',
            'created_at', 'started_at', 'completed_at', 'deadline',
        ]

    def create(self, validated_data):
        task = Task.objects.create(**validated_data)
        # 如果有 assigned_skills，自动写入知识引用
        return task


class TaskCreateSerializer(serializers.ModelSerializer):
    """创建任务专用：允许指定技能 slug 列表"""
    skill_slugs = serializers.ListField(
        child=serializers.CharField(), write_only=True, required=False,
    )

    class Meta:
        model = Task
        fields = [
            'id', 'title', 'description', 'contract', 'context',
            'knowledge_refs', 'agent', 'priority', 'deadline',
            'parent_task', 'status', 'created_at', 'source',
            'skill_slugs',
        ]
        read_only_fields = ['id', 'status', 'created_at']

    def create(self, validated_data):
        skill_slugs = validated_data.pop('skill_slugs', [])
        task = Task.objects.create(**validated_data)
        if skill_slugs:
            skills = Skill.objects.filter(slug__in=skill_slugs, status=Skill.Status.ACTIVE)
            task.assigned_skills.set(skills)
        return task


class TaskStatusUpdateSerializer(serializers.Serializer):
    """更新任务状态（Agent 回调用）"""
    status = serializers.ChoiceField(
        choices=['assigned', 'running', 'completed', 'failed'],
    )
    result = serializers.JSONField(required=False, default=dict)


class TaskBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = ['id', 'title', 'status', 'priority']


class TaskDetailSerializer(serializers.ModelSerializer):
    """任务详情页专用：含子任务树 + 执行日志"""
    agent_name = serializers.CharField(source='agent.name', read_only=True)
    agent_status = serializers.CharField(source='agent.status', read_only=True)
    assigned_skills = SkillBriefSerializer(many=True, read_only=True)
    log_count = serializers.IntegerField(read_only=True)
    subtask_count = serializers.IntegerField(read_only=True)
    subtasks = serializers.SerializerMethodField()
    recent_logs = serializers.SerializerMethodField()
    source_label = serializers.CharField(source='get_source_display', read_only=True)

    class Meta:
        model = Task
        fields = [
            'id', 'title', 'description',
            'contract', 'context', 'knowledge_refs',
            'agent', 'agent_name', 'agent_status',
            'assigned_skills', 'parent_task',
            'status', 'priority', 'source', 'source_label',
            'log_count', 'subtask_count',
            'subtasks', 'recent_logs',
            'result',
            'created_at', 'started_at', 'completed_at', 'deadline',
        ]

    def get_subtasks(self, obj):
        """返回直接子任务（一层），含执行摘要"""
        children = obj.subtasks.select_related('agent').annotate(
            log_count=Count('execution_logs'),
        ).order_by('created_at')
        return TaskDetailSummarySerializer(children, many=True).data

    def get_recent_logs(self, obj):
        """返回最近 50 条执行日志"""
        logs = obj.execution_logs.select_related('agent').order_by('-created_at')[:50]
        return ExecutionLogSerializer(logs, many=True).data


class TaskDetailSummarySerializer(serializers.ModelSerializer):
    """子任务摘要：用于嵌套在父任务详情中"""
    agent_name = serializers.CharField(source='agent.name', read_only=True)
    log_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Task
        fields = [
            'id', 'title', 'description', 'status', 'priority',
            'agent_name', 'log_count',
            'result',
            'created_at', 'started_at', 'completed_at',
        ]


# ═══════════════════════════════════════════════
# KnowledgeEntry
# ═══════════════════════════════════════════════

class KnowledgeEntrySerializer(serializers.ModelSerializer):
    source_agent_name = serializers.CharField(source='source_agent.name', read_only=True)
    related_skills = SkillBriefSerializer(many=True, read_only=True)

    class Meta:
        model = KnowledgeEntry
        fields = [
            'id', 'title', 'content', 'entry_type',
            'source_task', 'source_agent', 'source_agent_name',
            'related_skills', 'tags',
            'visibility', 'relevance_score',
            'view_count', 'useful_count',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'view_count', 'useful_count', 'created_at', 'updated_at',
        ]


# ═══════════════════════════════════════════════
# CronExecution
# ═══════════════════════════════════════════════

class CronExecutionSerializer(serializers.ModelSerializer):
    agent_name = serializers.CharField(source='agent.name', read_only=True)

    class Meta:
        model = CronExecution
        fields = [
            'id', 'job_id', 'name', 'agent', 'agent_name', 'source', 'skill', 'schedule',
            'status', 'result', 'error_message',
            'created_at', 'completed_at',
        ]
        read_only_fields = ['id', 'created_at', 'completed_at']


# ═══════════════════════════════════════════════
# CronJob
# ═══════════════════════════════════════════════

class CronJobSerializer(serializers.ModelSerializer):
    agent_name = serializers.CharField(source='agent.name', read_only=True)

    class Meta:
        model = CronJob
        fields = [
            'id', 'job_id', 'name', 'agent', 'agent_name', 'schedule', 'skill',
            'enabled', 'last_run_at', 'last_status', 'next_run_at', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


# ═══════════════════════════════════════════════
# Conversation & Message
# ═══════════════════════════════════════════════

class MessageSerializer(serializers.ModelSerializer):
    role_label = serializers.CharField(source='get_role_display', read_only=True)

    class Meta:
        model = Message
        fields = ['id', 'conversation', 'role', 'role_label', 'content', 'task', 'processed', 'source', 'metadata', 'created_at']
        read_only_fields = ['id', 'created_at']


class ConversationSerializer(serializers.ModelSerializer):
    agent_name = serializers.CharField(source='agent.name', read_only=True)
    messages = MessageSerializer(many=True, read_only=True)
    message_count = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = ['id', 'title', 'agent', 'agent_name', 'feishu_chat_id', 'output_content', 'messages', 'message_count', 'last_message', 'created_at']
        read_only_fields = ['id', 'created_at', 'messages', 'message_count', 'last_message']

    def get_message_count(self, obj):
        return obj.messages.count()

    def get_last_message(self, obj):
        last = obj.messages.last()
        if last:
            return {'content': last.content[:100], 'role': last.role, 'created_at': last.created_at}
        return None


class ConversationListSerializer(serializers.ModelSerializer):
    agent_name = serializers.CharField(source='agent.name', read_only=True)
    message_count = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    is_cross_platform = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = ['id', 'title', 'agent', 'agent_name', 'feishu_chat_id', 'message_count', 'last_message', 'is_cross_platform', 'created_at']

    def get_message_count(self, obj):
        return obj.messages.count()

    def get_last_message(self, obj):
        last = obj.messages.last()
        if last:
            return {'content': last.content[:100], 'role': last.role, 'created_at': last.created_at, 'source': last.source}
        return None

    def get_is_cross_platform(self, obj):
        """是否有多个来源的消息"""
        sources = obj.messages.values_list('source', flat=True).distinct()
        return len(set(sources)) > 1

# ═══════════════════════════════════════════════
# UploadedFile
# ═══════════════════════════════════════════════

class UploadedFileSerializer(serializers.ModelSerializer):
    uploader_name = serializers.CharField(source='uploader.username', read_only=True)
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = UploadedFile
        fields = ['id', 'uploader', 'uploader_name', 'conversation', 'file', 'original_name',
                  'mime_type', 'size', 'is_admin', 'expires_at', 'agent_name', 'created_at', 'file_url']
        read_only_fields = ['id', 'created_at', 'uploader_name', 'uploader']
        extra_kwargs = {'original_name': {'required': False}, 'file': {'required': True}}


    def get_file_url(self, obj):
        if obj.file:
            return f'/media/{obj.file.name}'
        return None


# ═══════════════════════════════════════════════
# TaskNode — 任务节点可视化（Basir 方案）
# ═══════════════════════════════════════════════

class TaskNodeSerializer(serializers.ModelSerializer):
    status_label = serializers.CharField(source='get_status_display', read_only=True)
    progress_events_count = serializers.SerializerMethodField()

    class Meta:
        model = TaskNode
        fields = [
            'id', 'parent_task', 'node_id', 'label', 'description',
            'agent_name', 'action', 'depends_on',
            'status', 'status_label',
            'started_at', 'finished_at', 'duration_ms',
            'is_bottleneck', 'bottleneck_reason',
            'child_task',
            'seq', 'metadata', 'created_at',
            'progress_events_count',
        ]
        read_only_fields = ['id', 'created_at']

    def get_progress_events_count(self, obj):
        if obj.child_task:
            return obj.child_task.progress_events.count()
        return 0


class TaskGraphSerializer(serializers.Serializer):
    """整个任务图：包含节点列表 + 依赖图 + 卡点汇总"""
    parent_task_id = serializers.IntegerField()
    parent_status = serializers.CharField()
    total_nodes = serializers.IntegerField()
    completed_nodes = serializers.IntegerField()
    failed_nodes = serializers.IntegerField()
    running_nodes = serializers.IntegerField()
    pending_nodes = serializers.IntegerField()
    bottlenecks = serializers.ListField(child=serializers.DictField())
    nodes = TaskNodeSerializer(many=True)
    edges = serializers.ListField(child=serializers.DictField())
