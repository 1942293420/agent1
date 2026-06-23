'''
SSE (Server-Sent Events) v2 — 实时事件流 + 消息推送
GET /api/events/?conversation_id=N
'''
import json, time
from datetime import timedelta
from django.http import StreamingHttpResponse
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
import redis as redis_lib
from .models import Agent, Task, CronJob, Message

REDIS_URL = "redis://" + "localhost" + ":" + "6379" + "/" + "0"


@api_view(['GET'])
@permission_classes([AllowAny])
def event_stream(request):
    conversation_id = request.GET.get('conversation_id')

    def generate():
        r = redis_lib.Redis.from_url(REDIS_URL)
        pubsub = r.pubsub()
        pubsub.subscribe('msg_updates')
        last_check = timezone.now() - timedelta(seconds=10)
        cycle = 0

        while True:
            cycle += 1

            for ag in Agent.objects.filter(updated_at__gt=last_check).values('id','name','status','last_heartbeat'):
                hb = ag['last_heartbeat'].isoformat() if ag['last_heartbeat'] else None
                yield _evt('agent-update', {'agent_id':ag['id'],'name':ag['name'],'status':ag['status'],'last_heartbeat':hb})

            for tk in Task.objects.filter(updated_at__gt=last_check).select_related('agent').values('id','title','status','priority','agent__name'):
                yield _evt('task-update', {'task_id':tk['id'],'title':tk['title'],'status':tk['status'],'priority':tk['priority'],'agent_name':tk['agent__name']})

            mq = Message.objects.filter(created_at__gt=last_check)
            if conversation_id:
                try: mq = mq.filter(conversation_id=int(conversation_id))
                except: pass
            for m in mq.values('id','conversation_id','role','content','source','created_at','processed').order_by('created_at'):
                yield _evt('message-update', {'id':m['id'],'conversation_id':m['conversation_id'],'role':m['role'],'content':m['content'][:200],'source':m['source'],'created_at':m['created_at'].isoformat(),'processed':m['processed']})

            if cycle % 15 == 0:
                for w in CronJob.objects.filter(name__icontains='Worker').values('job_id','name','schedule','agent__name','last_run_at','last_status','next_run_at','enabled'):
                    lr = w['last_run_at'].isoformat() if w['last_run_at'] else None
                    nr = w['next_run_at'].isoformat() if w['next_run_at'] else None
                    yield _evt('worker-pulse', {'job_id':w['job_id'],'name':w['name'],'schedule':w['schedule'],'agent_name':w['agent__name'],'last_run_at':lr,'last_status':w['last_status'],'next_run_at':nr,'enabled':w['enabled']})

            pm = pubsub.get_message()
            if pm and pm['type'] == 'message':
                try:
                    data = json.loads(pm['data'])
                    yield _evt('message-update', data)
                except: pass

            yield _evt('heartbeat', {'ts':timezone.now().isoformat(),'cycle':cycle})
            last_check = timezone.now()
            time.sleep(2)

    response = StreamingHttpResponse(generate(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    response['Access-Control-Allow-Origin'] = '*'
    return response


def _evt(event_type, data):
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
