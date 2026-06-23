"""
Agent 平台 — Admin 配置

按照 ah-django-developer 标准：
  - 彩色状态标签
  - list_display / list_filter / search_fields 完备
  - 内联管理（ExecutionLog 嵌入 Task）
  - 批量操作
"""
from django.contrib import admin
from django.utils.html import format_html
from .models import (
    CapabilityTag, Agent, Skill, AgentSkill,
    Task, ExecutionLog, KnowledgeEntry,
)


# ─── 通用状态徽章 ───

STATUS_COLORS = {
    'online': '#22c55e', 'offline': '#94a3b8',
    'busy': '#f59e0b', 'error': '#ef4444',
    'active': '#22c55e', 'deprecated': '#94a3b8', 'draft': '#f59e0b',
    'pending': '#94a3b8', 'assigned': '#3b82f6',
    'running': '#f59e0b', 'completed': '#22c55e',
    'failed': '#ef4444', 'cancelled': '#6b7280',
}


def status_badge(value, color_map=None):
    if color_map is None:
        color_map = STATUS_COLORS
    color = color_map.get(value, '#94a3b8')
    return format_html(
        '<span style="display:inline-block;width:10px;height:10px;'
        'border-radius:50%;background:{};margin-right:4px"></span>{}',
        color, value
    )


# ═══════════════════════════════════════════════
# CapabilityTag
# ═══════════════════════════════════════════════

@admin.register(CapabilityTag)
class CapabilityTagAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'agent_count', 'created_at']
    search_fields = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['created_at']

    def agent_count(self, obj):
        return obj.agents.count()
    agent_count.short_description = 'Agent 数'


# ═══════════════════════════════════════════════
# Agent
# ═══════════════════════════════════════════════

class AgentSkillInline(admin.TabularInline):
    model = AgentSkill
    extra = 1
    fields = ['skill', 'is_active']
    raw_id_fields = ['skill']


@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'feishu_app_id', 'status_colored',
        'capability_list', 'last_heartbeat', 'task_count',
    ]
    list_filter = ['status', 'capabilities']
    search_fields = ['name', 'feishu_app_id']
    readonly_fields = ['last_heartbeat', 'created_at', 'updated_at']
    filter_horizontal = ['capabilities']
    inlines = [AgentSkillInline]
    fieldsets = (
        ('基本信息', {
            'fields': ('name', 'feishu_app_id', 'webhook_url')
        }),
        ('能力 & 状态', {
            'fields': ('capabilities', 'status', 'last_heartbeat', 'version')
        }),
        ('扩展', {
            'fields': ('metadata',),
            'classes': ('collapse',),
        }),
        ('时间戳', {
            'fields': ('created_at', 'updated_at'),
        }),
    )
    actions = ['mark_online', 'mark_offline']

    def status_colored(self, obj):
        return status_badge(obj.status)
    status_colored.short_description = '状态'
    status_colored.admin_order_field = 'status'

    def capability_list(self, obj):
        return ', '.join(obj.capabilities.values_list('name', flat=True))
    capability_list.short_description = '能力标签'

    def task_count(self, obj):
        return obj.tasks.count()
    task_count.short_description = '任务数'

    @admin.action(description='标记为在线')
    def mark_online(self, request, queryset):
        queryset.update(status=Agent.Status.ONLINE)

    @admin.action(description='标记为离线')
    def mark_offline(self, request, queryset):
        queryset.update(status=Agent.Status.OFFLINE)


# ═══════════════════════════════════════════════
# Skill
# ═══════════════════════════════════════════════

@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'version', 'status_colored', 'source',
        'category', 'agent_count', 'knowledge_count',
        'last_synced_at',
    ]
    list_filter = ['status', 'source', 'category']
    search_fields = ['name', 'slug', 'description']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['last_synced_at', 'created_at', 'updated_at']
    fieldsets = (
        ('基本信息', {
            'fields': ('name', 'slug', 'version', 'description', 'category')
        }),
        ('文件', {
            'fields': ('file_url', 'file_hash', 'file_size')
        }),
        ('状态 & 来源', {
            'fields': ('source', 'status', 'tags')
        }),
        ('Meyo 同步', {
            'fields': ('meyo_skill_id', 'last_synced_at'),
            'classes': ('collapse',),
        }),
        ('时间戳', {
            'fields': ('created_at', 'updated_at'),
        }),
    )

    def status_colored(self, obj):
        return status_badge(obj.status)
    status_colored.short_description = '状态'
    status_colored.admin_order_field = 'status'

    def agent_count(self, obj):
        return obj.agent_assignments.filter(is_active=True).count()
    agent_count.short_description = '已分配 Agent'

    def knowledge_count(self, obj):
        return obj.knowledge_entries.count()
    knowledge_count.short_description = '关联知识'


# ═══════════════════════════════════════════════
# AgentSkill
# ═══════════════════════════════════════════════

@admin.register(AgentSkill)
class AgentSkillAdmin(admin.ModelAdmin):
    list_display = ['agent', 'skill', 'is_active', 'assigned_at']
    list_filter = ['is_active', 'assigned_at']
    search_fields = ['agent__name', 'skill__name']
    raw_id_fields = ['agent', 'skill', 'assigned_by']
    readonly_fields = ['assigned_at']


# ═══════════════════════════════════════════════
# ExecutionLog — Inline for Task
# ═══════════════════════════════════════════════

class ExecutionLogInline(admin.TabularInline):
    model = ExecutionLog
    extra = 0
    fields = ['level', 'message_preview', 'duration_ms', 'created_at']
    readonly_fields = ['level', 'message_preview', 'duration_ms', 'created_at']
    can_delete = False
    max_num = 0

    def message_preview(self, obj):
        return obj.message[:120]
    message_preview.short_description = '消息'

    def has_add_permission(self, request, obj=None):
        return False


# ═══════════════════════════════════════════════
# Task
# ═══════════════════════════════════════════════

@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'title', 'agent', 'status_colored', 'priority_colored',
        'log_count', 'created_at', 'completed_at',
    ]
    list_filter = ['status', 'priority', 'agent']
    search_fields = ['title', 'description']
    readonly_fields = ['created_at', 'started_at', 'completed_at']
    raw_id_fields = ['agent', 'parent_task']
    filter_horizontal = ['assigned_skills']
    inlines = [ExecutionLogInline]
    fieldsets = (
        ('基本信息', {
            'fields': ('title', 'description')
        }),
        ('分配', {
            'fields': ('agent', 'assigned_skills', 'parent_task')
        }),
        ('SPEC 契约', {
            'fields': ('contract',),
            'classes': ('collapse',),
        }),
        ('上下文 & 知识', {
            'fields': ('context', 'knowledge_refs'),
            'classes': ('collapse',),
        }),
        ('状态', {
            'fields': ('status', 'priority', 'deadline')
        }),
        ('结果', {
            'fields': ('result',),
            'classes': ('collapse',),
        }),
        ('时间戳', {
            'fields': ('created_at', 'started_at', 'completed_at'),
        }),
    )
    actions = ['mark_completed', 'cancel_tasks']

    def status_colored(self, obj):
        return status_badge(obj.status)
    status_colored.short_description = '状态'
    status_colored.admin_order_field = 'status'

    def priority_colored(self, obj):
        colors = {
            'low': '#94a3b8', 'medium': '#3b82f6',
            'high': '#f59e0b', 'critical': '#ef4444',
        }
        return status_badge(obj.priority, color_map=colors)
    priority_colored.short_description = '优先级'
    priority_colored.admin_order_field = 'priority'

    def log_count(self, obj):
        return obj.execution_logs.count()
    log_count.short_description = '日志'

    @admin.action(description='标记为已完成')
    def mark_completed(self, request, queryset):
        from django.utils import timezone
        queryset.update(status=Task.Status.COMPLETED, completed_at=timezone.now())

    @admin.action(description='取消任务')
    def cancel_tasks(self, request, queryset):
        queryset.update(status=Task.Status.CANCELLED)


# ═══════════════════════════════════════════════
# ExecutionLog
# ═══════════════════════════════════════════════

@admin.register(ExecutionLog)
class ExecutionLogAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'task_link', 'agent', 'level_colored',
        'message_preview', 'duration_ms', 'created_at',
    ]
    list_filter = ['level', 'agent']
    search_fields = ['message', 'task__title']
    readonly_fields = ['task', 'agent', 'level', 'message', 'quality_gate', 'duration_ms', 'created_at']
    raw_id_fields = ['task', 'agent']

    def task_link(self, obj):
        from django.urls import reverse
        url = reverse('admin:agents_task_change', args=[obj.task_id])
        return format_html('<a href="{}">#{}</a>', url, obj.task_id)
    task_link.short_description = '任务'

    def level_colored(self, obj):
        colors = {'info': '#3b82f6', 'warning': '#f59e0b', 'error': '#ef4444', 'debug': '#94a3b8'}
        return status_badge(obj.level, color_map=colors)
    level_colored.short_description = '级别'

    def message_preview(self, obj):
        return obj.message[:100]
    message_preview.short_description = '消息'


# ═══════════════════════════════════════════════
# KnowledgeEntry
# ═══════════════════════════════════════════════

@admin.register(KnowledgeEntry)
class KnowledgeEntryAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'entry_type_colored', 'visibility',
        'relevance_score', 'view_count', 'useful_count',
        'source_agent', 'created_at',
    ]
    list_filter = ['entry_type', 'visibility', 'source_agent']
    search_fields = ['title', 'content', 'tags']
    readonly_fields = ['view_count', 'useful_count', 'created_at', 'updated_at']
    raw_id_fields = ['source_task', 'source_agent']
    filter_horizontal = ['related_skills']
    fieldsets = (
        ('基本信息', {
            'fields': ('title', 'content', 'entry_type')
        }),
        ('来源', {
            'fields': ('source_task', 'source_agent')
        }),
        ('关联', {
            'fields': ('related_skills', 'tags')
        }),
        ('可见性 & 评分', {
            'fields': ('visibility', 'relevance_score')
        }),
        ('统计', {
            'fields': ('view_count', 'useful_count'),
            'classes': ('collapse',),
        }),
        ('时间戳', {
            'fields': ('created_at', 'updated_at'),
        }),
    )

    def entry_type_colored(self, obj):
        colors = {
            'solution': '#3b82f6', 'pitfall': '#ef4444',
            'best_practice': '#22c55e', 'snippet': '#8b5cf6', 'lesson': '#f59e0b',
        }
        return status_badge(obj.entry_type, color_map=colors)
    entry_type_colored.short_description = '类型'
    entry_type_colored.admin_order_field = 'entry_type'
