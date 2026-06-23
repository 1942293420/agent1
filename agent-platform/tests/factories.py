"""Factory Boy 测试工厂"""
import factory
from factory.django import DjangoModelFactory
from agents.models import Agent, Task, Conversation, Message

class AgentFactory(DjangoModelFactory):
    class Meta:
        model = Agent

    name = factory.Sequence(lambda n: f'TestAgent-{n}')
    feishu_app_id = factory.Sequence(lambda n: f'test_app_{n}')
    webhook_url = 'https://example.com/webhook'
    portrait = '你是一个测试Agent，用中文回复。'
    status = Agent.Status.ONLINE
    version = '1.0.0'

class ConversationFactory(DjangoModelFactory):
    class Meta:
        model = Conversation

    title = factory.Sequence(lambda n: f'TestConv-{n}')
    agent = factory.SubFactory(AgentFactory)

class MessageFactory(DjangoModelFactory):
    class Meta:
        model = Message

    conversation = factory.SubFactory(ConversationFactory)
    role = Message.Role.USER
    content = factory.Faker('sentence')
    source = 'web'

class TaskFactory(DjangoModelFactory):
    class Meta:
        model = Task

    title = factory.Sequence(lambda n: f'TestTask-{n}')
    status = Task.Status.PENDING
    priority = Task.Priority.MEDIUM
    agent = factory.SubFactory(AgentFactory)
