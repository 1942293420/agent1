from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views, sse, task_api

router = DefaultRouter()
router.register(r'agents', views.AgentViewSet)
router.register(r'capabilities', views.CapabilityTagViewSet)
router.register(r'skills', views.SkillViewSet)
router.register(r'tasks', views.TaskViewSet)
router.register(r'knowledge', views.KnowledgeEntryViewSet)
router.register(r'cron-executions', views.CronExecutionViewSet)
router.register(r'cron-jobs', views.CronJobViewSet)
router.register(r'conversations', views.ConversationViewSet)
router.register(r'messages', views.MessageViewSet)

app_name = 'agents'

urlpatterns = [
    path('', include(router.urls)),
    path('events/', sse.event_stream, name='event-stream'),
    path('system/workers/', views.system_workers, name='system-workers'),
    path('system/pipeline-status/', views.system_pipeline, name='system-pipeline'),
    # 多Agent协同 — 任务状态机
    path('parent-tasks/', task_api.parent_task_create, name='parent-task-create'),
    path('parent-tasks/<int:pk>/', task_api.parent_task_update, name='parent-task-update'),
    path('child-tasks/', task_api.child_task_create, name='child-task-create'),
    path('child-tasks/<int:pk>/', task_api.child_task_update, name='child-task-update'),
    path('child-tasks/<int:pk>/heartbeat/', task_api.child_task_heartbeat, name='child-task-heartbeat'),
]
