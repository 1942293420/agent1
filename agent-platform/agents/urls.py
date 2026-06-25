from django.urls import path, include
from django.views.decorators.csrf import csrf_exempt
from rest_framework.routers import DefaultRouter
from . import views
from . import sse_views, sse, task_api

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
    path('parent-tasks/', task_api.parent_task_list, name='parent-task-list'),
    path('parent-tasks/list/', task_api.parent_task_list, name='parent-task-list2'),
    path('parent-tasks/create/', task_api.parent_task_create, name='parent-task-create'),
    path('parent-tasks/<int:pk>/', task_api.parent_task_update, name='parent-task-update'),
    path('child-tasks/', task_api.child_task_create, name='child-task-create'),
    path('child-tasks/<int:pk>/', task_api.child_task_update, name='child-task-update'),
    path('child-tasks/<int:pk>/heartbeat/', task_api.child_task_heartbeat, name='child-task-heartbeat'),
    # 任务节点可视化
    path('parent-tasks/<int:pk>/graph/', views.parent_task_graph, name='parent-task-graph'),
    path('parent-tasks/<int:pk>/stop/', views.stop_parent_task, name='stop-parent-task'),
    path('parent-tasks/<int:pk>/stream/', sse_views.parent_task_progress_stream, name='parent-task-stream'),
    path('parent-tasks/<int:pk>/progress/', sse_views.parent_task_progress_snapshot, name='parent-task-progress'),
    # Auth
    path('auth/login/', views.login_view, name='auth-login'),
    path('auth/logout/', views.logout_view, name='auth-logout'),
    path('auth/whoami/', views.whoami_view, name='auth-whoami'),
    path('auth/register/', views.register_view, name='auth-register'),
    # Admin — 用户管理
    path('admin/users/', views.admin_list_users, name='admin-list-users'),
    path('admin/users/add/', csrf_exempt(views.admin_add_user), name='admin-add-user'),
    path('admin/users/<int:user_id>/approve/', csrf_exempt(views.admin_approve_user), name='admin-approve-user'),
    path('admin/users/<int:user_id>/reject/', csrf_exempt(views.admin_reject_user), name='admin-reject-user'),
    path('admin/users/<int:user_id>/reset-password/', csrf_exempt(views.admin_reset_password), name='admin-reset-password'),
    path('admin/users/<int:user_id>/delete/', views.admin_delete_user, name='admin-delete-user'),
    path('admin/users/<int:user_id>/decrypt-password/', views.admin_decrypt_password, name='admin-decrypt-password'),
]
