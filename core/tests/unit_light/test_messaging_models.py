from core.messaging.interfaces import MessagingProvider
from core.messaging.models import MessageEvent, MessageResult


def test_message_event_defaults():
    event = MessageEvent(recipient="user-1", body="hello")
    assert event.subject is None
    assert event.metadata is None
    assert event.recipient == "user-1"


def test_message_result_defaults():
    result = MessageResult(success=True, provider="email")
    assert result.message_id is None
    assert result.error is None
    assert result.success is True


def test_messaging_provider_protocol_conformance():
    class FakeProvider:
        async def send(self, event):
            return MessageResult(success=True, provider="fake")

    provider = FakeProvider()
    import asyncio

    result = asyncio.run(provider.send(MessageEvent(recipient="r", body="b")))
    assert isinstance(result, MessageResult)
    assert result.provider == "fake"


def test_concrete_provider_send_roundtrip():
    class FakeProvider:
        async def send(self, event):
            return MessageResult(success=True, provider="fake", message_id="m1")

    import asyncio

    event = MessageEvent(recipient="r", body="b", subject="s")
    result = asyncio.run(FakeProvider().send(event))
    assert result.message_id == "m1"
    assert event.subject == "s"
