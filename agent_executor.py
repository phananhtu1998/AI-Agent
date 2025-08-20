import inspect
import os
from uuid import uuid4

from a2a.types import (  # type: ignore[import-not-found]
    Message,
    Role,
    TaskState,
    TaskStatus,
    TaskStatusUpdateEvent,
    TextPart,
)

try:
    # Optional: load .env if present
    from dotenv import load_dotenv  # type: ignore[import-not-found]

    load_dotenv()
except Exception:
    pass

_gemini_model = None


class HelloWorldAgentExecutor:
    """Gemini-backed Agent.

    Uses Google Gemini (e.g., gemini-2.5-flash) to generate responses based on
    the user's input extracted from the RequestContext.
    """

    async def invoke(self) -> str:
        # Fallback text if invoked without context (should not happen in server flow)
        return 'Hello from Gemini Agent'

    async def execute(self, context, event_queue) -> None:
        global _gemini_model

        # Extract user text input
        try:
            user_text = context.get_user_input() if hasattr(context, 'get_user_input') else ''
        except Exception:
            user_text = ''
        if not user_text:
            user_text = 'Hello'

        # Configure Gemini model lazily
        if _gemini_model is None:
            try:
                import google.generativeai as genai  # type: ignore[import-not-found]

                api_key = os.environ.get('GOOGLE_API_KEY') or os.environ.get('GEMINI_API_KEY')
                if not api_key:
                    raise RuntimeError('Missing GOOGLE_API_KEY (or GEMINI_API_KEY)')
                genai.configure(api_key=api_key)
                model_name = os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash')
                _gemini_model = genai.GenerativeModel(model_name)
            except Exception as e:
                # On configuration error, emit a friendly message
                text = f"Gemini configuration error: {e}"
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
                return

        # Call Gemini
        try:
            # Prefer async API if available
            response_text = None
            try:
                generate_content_async = getattr(_gemini_model, 'generate_content_async', None)
                if callable(generate_content_async):
                    resp = await generate_content_async(user_text)
                    response_text = getattr(resp, 'text', None) if resp else None
                else:
                    # Fallback to sync call in a thread if async not available
                    import asyncio

                    loop = asyncio.get_running_loop()
                    resp = await loop.run_in_executor(None, _gemini_model.generate_content, user_text)
                    response_text = getattr(resp, 'text', None) if resp else None
            except Exception as e:
                response_text = f"Gemini call failed: {e}"

            if not response_text:
                response_text = 'No response from Gemini.'

            msg = Message(
                messageId=str(uuid4()),
                role=Role.agent,
                parts=[TextPart(text=response_text)],
                taskId=getattr(context, 'task_id', None),
                contextId=getattr(context, 'context_id', None),
            )
            maybe_awaitable = event_queue.enqueue_event(msg)
            if inspect.isawaitable(maybe_awaitable):
                await maybe_awaitable

        except Exception as e:
            # Emit a failure message
            msg = Message(
                messageId=str(uuid4()),
                role=Role.agent,
                parts=[TextPart(text=f'Error: {e}')],
                taskId=getattr(context, 'task_id', None),
                contextId=getattr(context, 'context_id', None),
            )
            maybe_awaitable = event_queue.enqueue_event(msg)
            if inspect.isawaitable(maybe_awaitable):
                await maybe_awaitable

    async def cancel(self, context, event_queue) -> None:
        # Emit a canceled status update per A2A contract
        task_id = getattr(context, 'task_id', None)
        context_id = getattr(context, 'context_id', None) or ''
        status = TaskStatus(state=TaskState.canceled)
        evt = TaskStatusUpdateEvent(
            taskId=task_id or '',
            contextId=context_id,
            status=status,
            final=True,
        )
        maybe_awaitable = event_queue.enqueue_event(evt)
        if inspect.isawaitable(maybe_awaitable):
            await maybe_awaitable