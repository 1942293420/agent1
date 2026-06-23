"""
Multi-Agent Collaboration Platform — 数据模型

7 张核心表：
  agents          → 飞书机器人（Agent 实例）
  capability_tags → 能力标签（标签体系）
  skill_registry  → 技能注册表（统一知识库）
  agent_skill_assignments → Agent↔Skill 分配关系
  tasks           → 任务（含 SPEC 契约、依赖链）
  execution_logs  → 执行日志（含质量门禁结果）
  knowledge_entries → 知识沉淀（Agent 经验归档）

设计原则：
  - Agent 无状态：不预装 Skill，按需从 skill_registry 动态拉取
  - Fat models, thin views（ah-django-developer 标准）
  - Composite indexes on hot query paths
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator

User = get_user_model()


# ═══════════════════════════════════════════════
# 1. CapabilityTag — 能力标签
# ═══════════════════════════════════════════════

class CapabilityTag(models.Model):
    """Agent 的能力标签（如：代码生成、文档撰写、飞书消息处理）"""
    name = models.CharField(max_length=64, unique=True, db_index=True)
    slug = models.SlugField(max_length=64, unique=True)
    description = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'capability_tags'
        verbose_name = '能力标签'
        verbose_name_plural = verbose_name
        ordering = ['name']

    def __str__(self):
        return self.name


# 2. Agent — 飞书机器人实例
# ═══════════════════════════════════════════════

class Agent(models.Model):
    class Status(models.TextChoices):
        ONLINE = 'online', '在线'
        OFFLINE = 'offline', '离线'
        BUSY = 'busy', '忙碌'
        ERROR = 'error', '异常'

    name = models.CharField(max_length=128, db_index=True)
    feishu_app_id = models.CharField(
        max_length=128, unique=True,
        help_text='飞书应用 App ID'
    )
    webhook_url = models.URLField(
        max_length=512, blank=True, default='',
        help_text='Agent 回调 webhook'
    )

    # 能力标签（多对多，不加 through 以保持简单查询）
    capabilities = models.ManyToManyField(
        CapabilityTag, blank=True,
        related_name='agents',
    )

    status = models.CharField(
        max_length=16, choices=Status.choices,
        default=Status.OFFLINE, db_index=True,
    )
    last_heartbeat = models.DateTimeField(null=True, blank=True)
    secret_key = models.CharField(
        max_length=64, unique=True, db_index=True, null=True, blank=True, default=None,
        help_text='HMAC-SHA256 签名密钥（Agent 注册时自动生成）'
    )
    version = models.CharField(max_length=32, blank=True, default='')
    metadata = models.JSONField(default=dict, blank=True)

    # 人物画像 — 描述 Agent 的性格、特长、角色定位
    portrait = models.TextField(blank=True, default='', help_text='人物画像：性格、特长、角色定位')

    # 加密配置 — 存储 API Key、Secret 等敏感信息（AES 加密后 JSON）
    config_encrypted = models.TextField(blank=True, default='', help_text='AES 加密后的配置 JSON（含 API Key 等敏感信息）')
    # 明文配置（仅非敏感字段，前端可直接展示）
    config_public = models.JSONField(default=dict, blank=True, help_text='公开配置：端口、域名、模型等非敏感信息')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'agents'
        verbose_name = 'Agent'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'last_heartbeat']),
        ]

    def __str__(self):
        return f'{self.name} ({self.get_status_display()})'


# ═══════════════════════════════════════════════
# 3. Skill — 技能注册表（统一知识库核心）
# ═══════════════════════════════════════════════

class Skill(models.Model):
    class Source(models.TextChoices):
        MEYO = 'meyo', 'Meyo 社区'
        LOCAL = 'local', '本地开发'
        THIRD_PARTY = 'third_party', '第三方'

    class Status(models.TextChoices):
        ACTIVE = 'active', '启用'
        DEPRECATED = 'deprecated', '已弃用'
        DRAFT = 'draft', '草稿'

    name = models.CharField(max_length=128, db_index=True)
    slug = models.SlugField(max_length=128, unique=True)
    version = models.CharField(max_length=32, default='1.0.0')
    description = models.TextField(blank=True, default='')

    # 技能原始文件内容（Markdown 全文）
    content = models.TextField(blank=True, default='', help_text='SKILL.md 原始 Markdown 内容')

    # 技能文件
    file_url = models.URLField(max_length=512, blank=True, default='')
    file_hash = models.CharField(
        max_length=64, blank=True, default='',
        help_text='SHA256 校验值'
    )
    file_size = models.PositiveIntegerField(default=0, help_text='字节数')

    # 元信息
    source = models.CharField(max_length=16, choices=Source.choices, default=Source.LOCAL)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    category = models.CharField(max_length=64, blank=True, default='')
    tags = models.JSONField(default=list, blank=True)

    # Meyo 同步
    meyo_skill_id = models.CharField(max_length=64, blank=True, default=None, unique=True, null=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'skill_registry'
        verbose_name = '技能'
        verbose_name_plural = verbose_name
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['status', 'category']),
            models.Index(fields=['source']),
        ]

    def __str__(self):
        return f'{self.name} v{self.version}'


# ═══════════════════════════════════════════════
# 4. AgentSkill — Agent↔Skill 分配关系
# ═══════════════════════════════════════════════

class AgentSkill(models.Model):
    """记录某个 Skill 被分配给某个 Agent 的历史"""
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name='skill_assignments')
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name='agent_assignments')

    assigned_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='skill_assignments',
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = 'agent_skill_assignments'
        verbose_name = 'Agent 技能分配'
        verbose_name_plural = verbose_name
        unique_together = ['agent', 'skill']
        indexes = [
            models.Index(fields=['agent', 'is_active']),
        ]

    def __str__(self):
        return f'{self.agent.name} ← {self.skill.name}'


# ═══════════════════════════════════════════════
# 5. Task — 任务（含 SPEC 契约）
# ═══════════════════════════════════════════════

class Task(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', '待分配'
        ASSIGNED = 'assigned', '已分配'
        IN_PROGRESS = 'in_progress', '执行中'
        RUNNING = 'running', '执行中(旧)'
        COMPLETED = 'completed', '已完成'
        FAILED = 'failed', '失败'
        CANCELLED = 'cancelled', '已取消'

    class Priority(models.TextChoices):
        LOW = 'low', '低'
        MEDIUM = 'medium', '中'
        HIGH = 'high', '高'
        CRITICAL = 'critical', '紧急'

    title = models.CharField(max_length=256)
    description = models.TextField(blank=True, default='')

    # SPEC 契约（agent-collaboration-protocol 要求的 API 路径 / 数据模型 / 共享常量）
    contract = models.JSONField(
        default=dict, blank=True,
        help_text='SPEC 契约：定义 Agent 间通信的 API 路径、数据模型、共享常量'
    )

    # 分配
    agent = models.ForeignKey(
        Agent, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='tasks',
    )
    assigned_skills = models.ManyToManyField(
        Skill, blank=True,
        related_name='tasks',
    )

    # 依赖
    parent_task = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='subtasks',
        help_text='父任务（依赖链）'
    )

    # 上下文
    context = models.JSONField(default=dict, blank=True)
    knowledge_refs = models.JSONField(
        default=list, blank=True,
        help_text='引用的 knowledge_entries ID 列表'
    )

    # 状态
    status = models.CharField(
        max_length=16, choices=Status.choices,
        default=Status.PENDING, db_index=True,
    )
    priority = models.CharField(
        max_length=16, choices=Priority.choices,
        default=Priority.MEDIUM, db_index=True,
    )
    source = models.CharField(
        max_length=16,
        choices=[('user', '用户派发'), ('cron', '定时触发'), ('agent', 'Agent自发'), ('web', 'Web Chat'), ('feishu', '飞书')],
        default='user', db_index=True,
    )

    # 时间
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    deadline = models.DateTimeField(null=True, blank=True)

    # 结果
    result = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'tasks'
        verbose_name = '任务'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'priority']),
            models.Index(fields=['agent', 'status']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f'#{self.id} {self.title} ({self.get_status_display()})'

    def save(self, *args, **kwargs):
        from django.utils import timezone
        if self.status in (self.Status.COMPLETED, self.Status.FAILED, self.Status.CANCELLED):
            if not self.completed_at:
                self.completed_at = timezone.now()
        super().save(*args, **kwargs)


# ═══════════════════════════════════════════════
# 6. ExecutionLog — 执行日志
# ═══════════════════════════════════════════════

class ExecutionLog(models.Model):
    class Level(models.TextChoices):
        INFO = 'info', '信息'
        WARNING = 'warning', '警告'
        ERROR = 'error', '错误'
        DEBUG = 'debug', '调试'

    task = models.ForeignKey(
        Task, on_delete=models.CASCADE,
        related_name='execution_logs',
    )
    agent = models.ForeignKey(
        Agent, on_delete=models.SET_NULL, null=True,
        related_name='execution_logs',
    )

    level = models.CharField(
        max_length=16, choices=Level.choices,
        default=Level.INFO, db_index=True,
    )
    message = models.TextField()

    # 质量门禁（gen-code 5 道门禁结果）
    quality_gate = models.JSONField(
        default=dict, blank=True,
        help_text='{complexity, security, null_safety, design_consistency, health_score}'
    )

    duration_ms = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'execution_logs'
        verbose_name = '执行日志'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['task', 'created_at']),
        ]

    def __str__(self):
        return f'[{self.get_level_display()}] Task#{self.task_id} — {self.message[:80]}'


# ═══════════════════════════════════════════════
# 7. KnowledgeEntry — 知识沉淀
# ═══════════════════════════════════════════════

class KnowledgeEntry(models.Model):
    class Visibility(models.TextChoices):
        PUBLIC = 'public', '所有 Agent 可见'
        TEAM = 'team', '同团队可见'
        PRIVATE = 'private', '仅当前 Agent'

    class EntryType(models.TextChoices):
        SOLUTION = 'solution', '解决方案'
        PITFALL = 'pitfall', '踩坑记录'
        BEST_PRACTICE = 'best_practice', '最佳实践'
        SNIPPET = 'snippet', '代码片段'
        LESSON = 'lesson', '经验教训'

    title = models.CharField(max_length=256, db_index=True)
    content = models.TextField()
    entry_type = models.CharField(
        max_length=32, choices=EntryType.choices,
        default=EntryType.SOLUTION, db_index=True,
    )

    # 来源
    source_task = models.ForeignKey(
        Task, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='knowledge_entries',
    )
    source_agent = models.ForeignKey(
        Agent, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='knowledge_entries',
    )

    # 关联技能
    related_skills = models.ManyToManyField(Skill, blank=True, related_name='knowledge_entries')

    # 标签 & 搜索
    tags = models.JSONField(default=list, blank=True)
    visibility = models.CharField(
        max_length=16, choices=Visibility.choices,
        default=Visibility.PUBLIC, db_index=True,
    )
    relevance_score = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
    )

    # 统计
    view_count = models.PositiveIntegerField(default=0)
    useful_count = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'knowledge_entries'
        verbose_name = '知识条目'
        verbose_name_plural = verbose_name
        ordering = ['-relevance_score', '-created_at']
        indexes = [
            models.Index(fields=['entry_type', 'visibility']),
            models.Index(fields=['relevance_score']),
        ]

    def calculate_relevance(self) -> float:
        """
        自动计算相关性评分 (0.0 - 1.0)

        算法：
          1. 类型权重 (40%): best_practice=0.8, solution=0.7, pitfall=0.6, snippet=0.5, lesson=0.4
          2. 流行度 (30%): useful_count / max(1, view_count)
          3. 时效性 (30%): 30天内=1.0，180天后降到0.5
        """
        type_weights = {
            'best_practice': 0.8,
            'solution': 0.7,
            'pitfall': 0.6,
            'snippet': 0.5,
            'lesson': 0.4,
        }
        type_score = type_weights.get(self.entry_type, 0.5)

        # 流行度
        if self.view_count > 0:
            popularity = self.useful_count / max(1, self.view_count)
        else:
            popularity = 0.0

        # 时效性：越新权重越高
        from django.utils import timezone
        now = timezone.now()
        age_days = (now - self.created_at).days
        if age_days <= 30:
            freshness = 1.0
        elif age_days >= 180:
            freshness = 0.5
        else:
            freshness = 0.5 + 0.5 * (180 - age_days) / 150

        score = type_score * 0.4 + popularity * 0.3 + freshness * 0.3
        return round(min(max(score, 0.0), 1.0), 4)

    def save(self, *args, **kwargs):
        # 如果未手动设置 relevance_score，自动计算
        if not getattr(self, '_manual_relevance', False):
            if self.pk is not None:
                self.relevance_score = self.calculate_relevance()
            # 新建时不自动计算，等 view_count / useful_count 稳定
        super().save(*args, **kwargs)


# ═══════════════════════════════════════════════
# 8. CronExecution — 定时任务执行记录
# ═══════════════════════════════════════════════

class CronExecution(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', '等待中'
        RUNNING = 'running', '执行中'
        OK = 'ok', '成功'
        ERROR = 'error', '失败'

    job_id = models.CharField(max_length=32, db_index=True)
    name = models.CharField(max_length=128, db_index=True)
    agent = models.ForeignKey(
        Agent, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='cron_executions',
    )
    source = models.CharField(
        max_length=16,
        choices=[('user', '用户派发'), ('cron', '定时触发'), ('agent', 'Agent自发')],
        default='cron', db_index=True,
    )
    skill = models.CharField(max_length=64, blank=True, default='')
    schedule = models.CharField(max_length=64, blank=True, default='')  # e.g. "25 9 * * *"
    status = models.CharField(
        max_length=16, choices=Status.choices,
        default=Status.PENDING, db_index=True,
    )
    result = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'cron_executions'
        verbose_name = '定时任务执行'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['job_id', '-created_at']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f'{self.name} [{self.get_status_display()}]'


# ═══════════════════════════════════════════════
# 9. CronJob — 定时任务定义
# ═══════════════════════════════════════════════

class CronJob(models.Model):
    job_id = models.CharField(max_length=32, unique=True, db_index=True)
    name = models.CharField(max_length=128, db_index=True)
    agent = models.ForeignKey(
        Agent, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='cron_jobs',
    )
    schedule = models.CharField(max_length=64)  # cron expr
    skill = models.CharField(max_length=64, blank=True, default='')
    enabled = models.BooleanField(default=True)
    last_run_at = models.DateTimeField(null=True, blank=True)
    last_status = models.CharField(max_length=16, blank=True, default='')
    next_run_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'cron_jobs'
        verbose_name = '定时任务'
        verbose_name_plural = verbose_name
        ordering = ['name']

    def __str__(self):
        return f'{self.name} [{self.schedule}]'


# ═══════════════════════════════════════════════
# 10. Conversation — Agent 对话
# ═══════════════════════════════════════════════

class Conversation(models.Model):
    title = models.CharField(max_length=256, default='新对话')
    agent = models.ForeignKey(
        Agent, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='conversations',
    )
    feishu_chat_id = models.CharField(
        max_length=128, null=True, blank=True, db_index=True,
        help_text='飞书会话ID，用于跨平台对话关联',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'conversations'
        verbose_name = '对话'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.title} [{self.agent.name if self.agent else "—"}]'


# ═══════════════════════════════════════════════
# 11. Message — 对话消息
# ═══════════════════════════════════════════════

class Message(models.Model):
    class Role(models.TextChoices):
        USER = 'user', '用户'
        AGENT = 'agent', 'Agent'
        SYSTEM = 'system', '系统'

    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE,
        related_name='messages',
    )
    role = models.CharField(max_length=16, choices=Role.choices, db_index=True)
    content = models.TextField()
    task = models.ForeignKey(
        Task, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='messages',
    )
    source = models.CharField(
        max_length=16, choices=[('feishu', '飞书'), ('web', 'Web')],
        default='web', db_index=True, help_text='消息来源',
    )
    processed = models.BooleanField(default=False, db_index=True, help_text='Hermes 是否已处理')
    metadata = models.JSONField(default=dict, blank=True, help_text='富文本HTML、附件信息等元数据')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'messages'
        verbose_name = '消息'
        verbose_name_plural = verbose_name
        ordering = ['created_at']

    def __str__(self):
        return f'[{self.get_role_display()}] {self.content[:60]}'
