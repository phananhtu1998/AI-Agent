import inspect
from uuid import uuid4
from a2a.types import Message, TextPart, Role  # type: ignore[import-not-found]


class HelloWorldAgentExecutor:
    """Hello World Agent."""

    async def invoke(self) -> str:
        return 'Hello World'

    async def execute(self, context, event_queue) -> None:
        text = await self.invoke()
        # Build a proper A2A Message event so the server can aggregate it
        msg = Message(
            messageId=str(uuid4()),
            role=Role.agent,
            parts=[TextPart(text=text)],
            taskId=getattr(context, 'task_id', None),
            contextId=getattr(context, 'context_id', None),
        )

        maybe_awaitable = event_queue.enqueue_event(msg)
        if inspect.isawaitable(maybe_awaitable):
            await maybe_awaitable