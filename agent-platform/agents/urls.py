from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views, sse

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
]
