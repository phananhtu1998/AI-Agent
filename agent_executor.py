import inspect
import os
from uuid import uuid4
from typing import Optional

import httpx  # type: ignore[import-not-found]
from a2a.server.agent_execution import (  # type: ignore[import-not-found]
    AgentExecutor,
    RequestContext,
)
from a2a.server.events import EventQueue  # type: ignore[import-not-found]
from a2a.types import (  # type: ignore[import-not-found]
    Message,
    Role,
    TaskState,
    TaskStatus,
    TaskStatusUpdateEvent,
    TextPart,
)
import re
import unicodedata

try:
    # Optional: load .env if present
    from dotenv import load_dotenv  # type: ignore[import-not-found]

    load_dotenv()
except Exception:
    pass

_gemini_model = None


class GeminiAgentExecutor(AgentExecutor):
    """Gemini-backed Agent.

    Uses Google Gemini (e.g., gemini-2.5-flash) to generate responses based on
    the user's input extracted from the RequestContext.
    """

    async def invoke(self) -> str:
        # Fallback text if invoked without context (should not happen in server flow)
        return 'Hello from Gemini Agent'

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
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

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
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


class WeatherAgentExecutor(AgentExecutor):
    """Simple weather agent using Open-Meteo geocoding and forecast APIs.

    Expects the user input to include a province/city. If missing or not
    found by geocoding, responds asking the user to provide the location.
    """

    GEOCODE_URL = 'https://geocoding-api.open-meteo.com/v1/search'
    WEATHER_URL = 'https://api.open-meteo.com/v1/forecast'

    def _strip_diacritics(self, s: str) -> str:
        nfkd = unicodedata.normalize('NFKD', s)
        return ''.join(ch for ch in nfkd if not unicodedata.combining(ch))

    async def _extract_location(self, text: str) -> Optional[str]:
        original = (text or '').strip()
        if not original:
            return None
        lowered = original.lower()

        # Take text after the last weather keyword if present
        candidate = original
        for kw in ['thời tiết', 'thoi tiet', 'weather', 'nhiệt độ', 'nhiet do']:
            if kw in lowered:
                idx = lowered.rfind(kw)
                candidate = original[idx + len(kw):]
                break

        # Remove punctuation
        candidate = re.sub(r'[\.,!?;:]+', ' ', candidate)
        candidate = candidate.strip()

        # Remove leading Vietnamese admin/location stopwords repeatedly
        stop_leading = [
            'của', 'o', 'ở', 'tai', 'tại', 'tinh', 'tỉnh', 'thanh pho', 'thành phố',
            'tp', 'tp.', 'quan', 'quận', 'huyen', 'huyện', 'thi xa', 'thị xã',
            'thi tran', 'thị trấn', 'xa', 'xã', 'phuong', 'phường'
        ]
        while True:
            changed = False
            for sw in stop_leading:
                pattern = r'^(?:' + re.escape(sw) + r')\s+'
                if re.match(pattern, candidate, flags=re.IGNORECASE):
                    candidate = re.sub(pattern, '', candidate, flags=re.IGNORECASE).strip()
                    changed = True
                    break
            if not changed:
                break

        # Remove common trailing time words
        candidate = re.sub(r'\b(hôm nay|hom nay|hiện tại|hien tai)\b', '', candidate, flags=re.IGNORECASE).strip()

        return candidate or None

    async def _geocode(self, location: str) -> Optional[tuple[float, float, str]]:
        # Try multiple variants: original, without diacritics
        queries = [location]
        no_diac = self._strip_diacritics(location)
        if no_diac and no_diac != location:
            queries.append(no_diac)

        async with httpx.AsyncClient(timeout=10) as client:
            for q in queries:
                params = {
                    'name': q,
                    'count': 5,
                    'language': 'vi',
                    'format': 'json',
                }
                r = await client.get(self.GEOCODE_URL, params=params)
                if r.status_code != 200:
                    continue
                data = r.json()
                results = data.get('results') or []
                if not results:
                    continue
                # Prefer Vietnam results
                vn = next((it for it in results if (it.get('country_code') or '').upper() == 'VN'), None)
                item = vn or results[0]
                try:
                    return (
                        float(item.get('latitude')),
                        float(item.get('longitude')),
                        item.get('name') or location,
                    )
                except Exception:
                    continue
        return None

    async def _get_weather(self, lat: float, lon: float) -> Optional[str]:
        params = {
            'latitude': lat,
            'longitude': lon,
            'current': 'temperature_2m,weather_code',
        }
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(self.WEATHER_URL, params=params)
            if r.status_code != 200:
                return None
            j = r.json()
            cur = (j or {}).get('current') or {}
            temp = cur.get('temperature_2m')
            code = cur.get('weather_code')
            # Map a few common codes; otherwise show code number
            codes = {
                0: 'Trời quang',
                1: 'Trời quang phần lớn',
                2: 'Có mây rải rác',
                3: 'Nhiều mây',
                45: 'Sương mù',
                51: 'Mưa phùn nhẹ',
                61: 'Mưa nhẹ',
                63: 'Mưa vừa',
                65: 'Mưa to',
                71: 'Tuyết nhẹ',
                80: 'Mưa rào nhẹ',
                95: 'Dông',
            }
            desc = codes.get(code, f'Mã thời tiết {code}')
            if temp is None:
                return None
            return f'Nhiệt độ hiện tại: {temp}°C — {desc}.'

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        user_text = ''
        try:
            user_text = context.get_user_input() or ''
        except Exception:
            pass

        location_query = await self._extract_location(user_text)
        if not location_query or len(location_query.split()) < 1:
            reply = 'Bạn muốn xem thời tiết ở tỉnh/thành nào? Vui lòng nêu rõ địa danh.'
        else:
            loc = await self._geocode(location_query)
            if not loc:
                reply = 'Không tìm thấy địa danh. Vui lòng cung cấp tên tỉnh/thành cụ thể.'
            else:
                lat, lon, place = loc
                weather = await self._get_weather(lat, lon)
                if weather:
                    reply = f'Thời tiết tại {place}: {weather}'
                else:
                    reply = 'Không lấy được dữ liệu thời tiết. Vui lòng thử lại sau.'

        msg = Message(
            messageId=str(uuid4()),
            role=Role.agent,
            parts=[TextPart(text=reply)],
            taskId=getattr(context, 'task_id', None),
            contextId=getattr(context, 'context_id', None),
        )
        maybe_awaitable = event_queue.enqueue_event(msg)
        if inspect.isawaitable(maybe_awaitable):
            await maybe_awaitable

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
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


class RouterAgentExecutor(AgentExecutor):
    """Routes requests to Weather or Gemini executors based on user input."""

    def __init__(self) -> None:
        self.weather = WeatherAgentExecutor()
        self.chat = GeminiAgentExecutor()

    def _is_weather_query(self, text: str) -> bool:
        t = (text or '').lower()
        return any(kw in t for kw in ['thời tiết', 'thoi tiet', 'weather', 'nhiệt độ'])

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        text = ''
        try:
            text = context.get_user_input() or ''
        except Exception:
            pass
        if self._is_weather_query(text):
            await self.weather.execute(context, event_queue)
        else:
            await self.chat.execute(context, event_queue)

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        # Attempt cancel on both
        try:
            await self.weather.cancel(context, event_queue)
        except Exception:
            pass
        try:
            await self.chat.cancel(context, event_queue)
        except Exception:
            pass


# Backwards compatibility if imported elsewhere
HelloWorldAgentExecutor = GeminiAgentExecutor