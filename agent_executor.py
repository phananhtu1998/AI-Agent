import inspect
import os
from uuid import uuid4
from typing import Optional, Dict, List
import asyncio

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

try:
    # LangChain memory for conversation management
    from langchain.memory import ConversationBufferWindowMemory
    from langchain.schema import HumanMessage, AIMessage
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    print("LangChain not available, using fallback memory system")

_gemini_model = None

class FallbackMemory:
    """Fallback memory system khi không có LangChain."""
    
    def __init__(self, k: int = 5):
        self.k = k
        self.messages: List[Dict] = []
    
    def save_context(self, inputs: Dict, outputs: Dict):
        """Lưu context."""
        if 'input' in inputs:
            self.messages.append({
                'role': 'user',
                'content': inputs['input'],
                'timestamp': asyncio.get_event_loop().time()
            })
        
        if 'output' in outputs:
            self.messages.append({
                'role': 'assistant', 
                'content': outputs['output'],
                'timestamp': asyncio.get_event_loop().time()
            })
        
        # Giữ chỉ k tin nhắn gần nhất
        if len(self.messages) > self.k * 2:
            self.messages = self.messages[-self.k * 2:]
    
    def load_memory_variables(self, inputs: Dict) -> Dict:
        """Load memory variables."""
        if not self.messages:
            return {'history': ''}
        
        history_lines = []
        for msg in self.messages[-self.k * 2:]:
            role = "Người dùng" if msg['role'] == 'user' else "Assistant"
            history_lines.append(f"{role}: {msg['content']}")
        
        return {'history': '\n'.join(history_lines)}
    
    def clear(self):
        """Xóa memory."""
        self.messages.clear()

# Global memory store
_memory_store: Dict[str, any] = {}

def get_or_create_memory(context_id: str):
    """Lấy hoặc tạo memory system."""
    if context_id not in _memory_store:
        if LANGCHAIN_AVAILABLE:
            # Sử dụng LangChain memory
            _memory_store[context_id] = ConversationBufferWindowMemory(
                k=5,  # Giữ 5 cặp Q&A
                return_messages=True,
                memory_key="history"
            )
        else:
            # Fallback memory
            _memory_store[context_id] = FallbackMemory(k=5)
    
    return _memory_store[context_id]


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

        # Lấy context cho phiên này
        context_id = getattr(context, 'context_id', 'default')
        memory = get_or_create_memory(context_id)
        
        # Không lưu tin nhắn người dùng nữa vì đã lưu trong router
        # Chỉ cần lưu phản hồi của bot sau khi xử lý

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

        # Call Gemini với context
        try:
            # Tạo prompt với context
            history_text = memory.load_memory_variables({"input": user_text})['history']
            if history_text:
                enhanced_prompt = f"""Ngữ cảnh trước đó:
{history_text}

Câu hỏi hiện tại: {user_text}

Hãy trả lời dựa trên ngữ cảnh và câu hỏi hiện tại."""
            else:
                enhanced_prompt = user_text

            # Prefer async API if available
            response_text = None
            try:
                generate_content_async = getattr(_gemini_model, 'generate_content_async', None)
                if callable(generate_content_async):
                    resp = await generate_content_async(enhanced_prompt)
                    response_text = getattr(resp, 'text', None) if resp else None
                else:
                    # Fallback to sync call in a thread if async not available
                    import asyncio

                    loop = asyncio.get_running_loop()
                    resp = await loop.run_in_executor(None, _gemini_model.generate_content, enhanced_prompt)
                    response_text = getattr(resp, 'text', None) if resp else None
            except Exception as e:
                response_text = f"Gemini call failed: {e}"

            if not response_text:
                response_text = 'No response from Gemini.'

            # Thêm phản hồi của bot vào context
            memory.save_context({"input": user_text}, {"output": response_text})

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
    
    # Class-level shared cache for Vietnam locations
    CLASS_LOCATIONS_CACHE: Dict[str, tuple] = {}
    CLASS_CACHE_TIMESTAMP: float = 0.0
    CLASS_CACHE_DURATION: float = 24 * 60 * 60  # 24 hours

    def __init__(self):
        super().__init__()
        # Instance-level references (mirror class cache)
        self._vietnam_locations_cache = None
        self._cache_timestamp = 0
        self._cache_duration = self.CLASS_CACHE_DURATION
        self._initialization_task = None
        
        # Fallback coordinates for major cities (backup)
        self.MAJOR_CITIES_FALLBACK = {
            'hà nội': (21.0285, 105.8542, 'Hà Nội'),
            'ha noi': (21.0285, 105.8542, 'Hà Nội'),
            'hồ chí minh': (10.8231, 106.6297, 'Hồ Chí Minh'),
            'ho chi minh': (10.8231, 106.6297, 'Hồ Chí Minh'),
            'tp hcm': (10.8231, 106.6297, 'Hồ Chí Minh'),
            'đà nẵng': (16.0544, 108.2022, 'Đà Nẵng'),
            'da nang': (16.0544, 108.2022, 'Đà Nẵng'),
            'hải phòng': (20.8449, 106.6881, 'Hải Phòng'),
            'hai phong': (20.8449, 106.6881, 'Hải Phòng'),
            'cần thơ': (10.0452, 105.7469, 'Cần Thơ'),
            'can tho': (10.0452, 105.7469, 'Cần Thơ'),
            'quảng nam': (15.5394, 108.0191, 'Quảng Nam'),
            'quang nam': (15.5394, 108.0191, 'Quảng Nam'),
            'thừa thiên huế': (16.4637, 107.5909, 'Thừa Thiên Huế'),
            'thua thien hue': (16.4637, 107.5909, 'Thừa Thiên Huế'),
            'huế': (16.4637, 107.5909, 'Thừa Thiên Huế'),
            'hue': (16.4637, 107.5909, 'Thừa Thiên Huế'),
            'khánh hòa': (12.2388, 109.1967, 'Khánh Hòa'),
            'khanh hoa': (12.2388, 109.1967, 'Khánh Hòa'),
            'nha trang': (12.2388, 109.1967, 'Nha Trang'),
            'lâm đồng': (11.9404, 108.4583, 'Lâm Đồng'),
            'lam dong': (11.9404, 108.4583, 'Lâm Đồng'),
            'đà lạt': (11.9404, 108.4583, 'Đà Lạt'),
            'da lat': (11.9404, 108.4583, 'Đà Lạt'),
            'bình dương': (11.1696, 106.6667, 'Bình Dương'),
            'binh duong': (11.1696, 106.6667, 'Bình Dương'),
            'đồng nai': (10.9574, 106.8426, 'Đồng Nai'),
            'dong nai': (10.9574, 106.8426, 'Đồng Nai'),
            'bà rịa vũng tàu': (10.5411, 107.2420, 'Bà Rịa Vũng Tàu'),
            'ba ria vung tau': (10.5411, 107.2420, 'Bà Rịa Vũng Tàu'),
            'vũng tàu': (10.3459, 107.0843, 'Vũng Tàu'),
            'vung tau': (10.3459, 107.0843, 'Vũng Tàu'),
        }
        
        # Start initialization in background only if class cache is empty
        if not type(self).CLASS_LOCATIONS_CACHE:
            self._start_initialization()

    def _start_initialization(self):
        """Start background initialization of Vietnam locations."""
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            self._initialization_task = loop.create_task(self._initialize_vietnam_locations())
            print("DEBUG: Started background initialization of Vietnam locations")
        except Exception as e:
            print(f"DEBUG: Failed to start initialization: {e}")

    async def _initialize_vietnam_locations(self):
        """Initialize Vietnam locations in background."""
        try:
            await self._fetch_vietnam_provinces()
            print("DEBUG: Background initialization completed")
        except Exception as e:
            print(f"DEBUG: Background initialization failed: {e}")

    async def _fetch_vietnam_provinces(self) -> Dict[str, tuple]:
        """Lấy danh sách tỉnh/thành Việt Nam từ API."""
        print("DEBUG: Fetching Vietnam provinces from API...")
        
        try:
            # Sử dụng Open-Meteo geocoding API để lấy danh sách tỉnh/thành
            async with httpx.AsyncClient(timeout=30) as client:
                # Query cho các tỉnh/thành chính của Việt Nam
                vietnam_queries = [
                    "Hà Nội", "Hồ Chí Minh", "Đà Nẵng", "Hải Phòng", "Cần Thơ",
                    "Quảng Nam", "Thừa Thiên Huế", "Khánh Hòa", "Lâm Đồng", 
                    "Bình Dương", "Đồng Nai", "Bà Rịa Vũng Tàu", "Vũng Tàu",
                    "Nghệ An", "Thanh Hóa", "Quảng Ninh", "Bắc Ninh", "Hải Dương",
                    "Vĩnh Phúc", "Thái Nguyên", "Lào Cai", "Yên Bái", "Tuyên Quang",
                    "Phú Thọ", "Bắc Giang", "Quảng Bình", "Quảng Trị", "Quảng Ngãi",
                    "Bình Định", "Phú Yên", "Bình Thuận", "Ninh Thuận", "Bình Phước",
                    "Tây Ninh", "Long An", "Tiền Giang", "Bến Tre", "Trà Vinh",
                    "Vĩnh Long", "Đồng Tháp", "An Giang", "Kiên Giang", "Cà Mau",
                    "Bạc Liêu", "Sóc Trăng", "Hậu Giang", "Bình Phước", "Tây Ninh"
                ]
                
                locations = {}
                
                for query in vietnam_queries:
                    try:
                        params = {
                            'name': query,
                            'count': 5,
                            'language': 'vi',
                            'format': 'json',
                        }
                        
                        r = await client.get(self.GEOCODE_URL, params=params)
                        if r.status_code == 200:
                            data = r.json()
                            results = data.get('results') or []
                            
                            # Tìm kết quả Việt Nam
                            vn_result = next((it for it in results if (it.get('country_code') or '').upper() == 'VN'), None)
                            if vn_result:
                                try:
                                    lat = float(vn_result.get('latitude'))
                                    lon = float(vn_result.get('longitude'))
                                    name = vn_result.get('name') or query
                                    
                                    # Tạo multiple keys cho tên địa danh
                                    keys = [
                                        name.lower(),
                                        self._strip_diacritics(name).lower(),
                                        query.lower(),
                                        self._strip_diacritics(query).lower()
                                    ]
                                    
                                    for key in keys:
                                        if key and key not in locations:
                                            locations[key] = (lat, lon, name)
                                    
                                    print(f"DEBUG: Added {name} ({lat}, {lon})")
                                    
                                except (ValueError, TypeError) as e:
                                    print(f"DEBUG: Error parsing coordinates for {query}: {e}")
                                    continue
                        
                        # Thêm delay nhỏ để tránh rate limiting
                        await asyncio.sleep(0.1)
                        
                    except Exception as e:
                        print(f"DEBUG: Error fetching {query}: {e}")
                        continue
                
                # Merge với fallback cities
                all_locations = {**self.MAJOR_CITIES_FALLBACK, **locations}
                
                # Update class-level cache and instance mirror
                now_ts = asyncio.get_event_loop().time()
                type(self).CLASS_LOCATIONS_CACHE = all_locations
                type(self).CLASS_CACHE_TIMESTAMP = now_ts
                self._vietnam_locations_cache = all_locations
                self._cache_timestamp = now_ts
                
                print(f"DEBUG: Successfully fetched {len(all_locations)} locations")
                return all_locations
                
        except Exception as e:
            print(f"DEBUG: Error fetching Vietnam provinces: {e}")
            # Fallback to static mapping
            now_ts = asyncio.get_event_loop().time()
            type(self).CLASS_LOCATIONS_CACHE = self.MAJOR_CITIES_FALLBACK
            type(self).CLASS_CACHE_TIMESTAMP = now_ts
            self._vietnam_locations_cache = self.MAJOR_CITIES_FALLBACK
            self._cache_timestamp = now_ts
            return self.MAJOR_CITIES_FALLBACK

    async def _get_vietnam_locations(self) -> Dict[str, tuple]:
        """Lấy danh sách tỉnh/thành Việt Nam (cached)."""
        current_time = asyncio.get_event_loop().time()
        
        # Prefer class-level cache first
        if (type(self).CLASS_LOCATIONS_CACHE and
            current_time - type(self).CLASS_CACHE_TIMESTAMP < type(self).CLASS_CACHE_DURATION):
            print("DEBUG: Using cached Vietnam locations (class-level)")
            return type(self).CLASS_LOCATIONS_CACHE

        # Fallback to instance cache
        if (self._vietnam_locations_cache is not None and 
            current_time - self._cache_timestamp < self._cache_duration):
            print("DEBUG: Using cached Vietnam locations (instance-level)")
            return self._vietnam_locations_cache
        
        # Nếu cache expired hoặc chưa có, fetch từ API
        print("DEBUG: Cache expired or not available, fetching from API...")
        return await self._fetch_vietnam_provinces()

    @classmethod
    async def preload_locations(cls) -> Dict[str, tuple]:
        """Preload Vietnam locations into class-level cache (call at app startup)."""
        tmp = cls()
        return await tmp._fetch_vietnam_provinces()

    async def _refresh_locations_cache(self):
        """Refresh cache manually."""
        print("DEBUG: Manually refreshing locations cache...")
        self._vietnam_locations_cache = None
        self._cache_timestamp = 0
        await self._fetch_vietnam_provinces()

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

        # Remove common trailing time words
        candidate = re.sub(r'\b(hôm nay|hom nay|hiện tại|hien tai)\b', '', candidate, flags=re.IGNORECASE).strip()

        print(f"DEBUG: Extracted location: '{candidate}' from '{original}'")
        return candidate or None

    async def _normalize_location_with_llm(self, location: str) -> str:
        """Sử dụng LLM để chuẩn hóa tên địa danh."""
        if not location.strip():
            return location
            
        global _gemini_model
        if _gemini_model is None:
            print(f"DEBUG: No Gemini model available, returning original: '{location}'")
            return location
            
        try:
            prompt = f"""
Bạn là chuyên gia về địa danh Việt Nam. Hãy chuẩn hóa tên địa danh sau:

Input: "{location}"

Yêu cầu:
1. Trả về tên địa danh chuẩn, không cần thêm "tỉnh", "thành phố"
2. Giữ nguyên dấu tiếng Việt
3. Nếu là tên viết tắt, viết đầy đủ
4. Chỉ trả về tên địa danh, không giải thích

Ví dụ:
- "TP HCM" → "Hồ Chí Minh"
- "Đà Lạt" → "Đà Lạt"
- "Quảng Nam" → "Quảng Nam"
- "Hà Nội" → "Hà Nội"

Tên địa danh chuẩn:
"""
            
            # Prefer async API if available
            response_text = None
            try:
                generate_content_async = getattr(_gemini_model, 'generate_content_async', None)
                if callable(generate_content_async):
                    resp = await generate_content_async(prompt)
                    response_text = getattr(resp, 'text', None) if resp else None
                else:
                    # Fallback to sync call in a thread if async not available
                    import asyncio
                    loop = asyncio.get_running_loop()
                    resp = await loop.run_in_executor(None, _gemini_model.generate_content, prompt)
                    response_text = getattr(resp, 'text', None) if resp else None
            except Exception as e:
                print(f"DEBUG: LLM normalization failed: {e}")
                return location

            if response_text:
                normalized = response_text.strip().strip('"').strip("'")
                print(f"DEBUG: LLM normalized '{location}' → '{normalized}'")
                return normalized
            else:
                print(f"DEBUG: LLM returned empty response for '{location}'")
                
        except Exception as e:
            print(f"DEBUG: LLM normalization error: {e}")
            
        return location

    def _test_fallback_mapping(self):
        """Test fallback mapping functionality."""
        print("=== TESTING FALLBACK MAPPING ===")
        test_cases = ["Quảng Nam", "QUảng Nam", "quảng nam", "QUANG NAM"]
        
        # Use fallback cities for testing
        locations = self.MAJOR_CITIES_FALLBACK
        
        for test in test_cases:
            location_lower = test.lower().strip()
            print(f"Test: '{test}' → '{location_lower}'")
            if location_lower in locations:
                lat, lon, name = locations[location_lower]
                print(f"  ✅ Found: {name} at ({lat}, {lon})")
            else:
                print(f"  ❌ Not found")
                # Check if it's a substring match
                for key in locations.keys():
                    if location_lower in key or key in location_lower:
                        print(f"  🔍 Similar key found: '{key}'")
        print("=== END TEST ===")

    async def _geocode(self, location: str) -> Optional[tuple[float, float, str]]:
        print(f"DEBUG: Geocoding location: '{location}'")
        
        # Test fallback mapping first
        self._test_fallback_mapping()
        
        # Chuẩn hóa tên địa danh bằng LLM
        normalized_location = await self._normalize_location_with_llm(location)
        print(f"DEBUG: After LLM normalization: '{normalized_location}'")
        
        # Lấy danh sách locations động
        vietnam_locations = await self._get_vietnam_locations()
        
        # Check fallback mapping first
        location_lower = normalized_location.lower().strip()
        print(f"DEBUG: Checking dynamic locations for: '{location_lower}'")
        print(f"DEBUG: Available keys: {list(vietnam_locations.keys())[:10]}...")  # Show first 10 keys
        
        if location_lower in vietnam_locations:
            lat, lon, name = vietnam_locations[location_lower]
            print(f"DEBUG: Found in dynamic locations: {name} at ({lat}, {lon})")
            return (lat, lon, name)
        else:
            print(f"DEBUG: Not found in dynamic locations")
            # Try fuzzy matching
            for key in vietnam_locations.keys():
                if location_lower in key or key in location_lower:
                    lat, lon, name = vietnam_locations[key]
                    print(f"DEBUG: Fuzzy match found: '{key}' → {name} at ({lat}, {lon})")
                    return (lat, lon, name)
        
        # Try multiple variants: original, normalized, without diacritics
        queries = [normalized_location]
        if normalized_location != location:
            queries.append(location)  # Keep original as backup
            
        no_diac = self._strip_diacritics(normalized_location)
        if no_diac and no_diac != normalized_location:
            queries.append(no_diac)
        
        print(f"DEBUG: Trying queries: {queries}")

        async with httpx.AsyncClient(timeout=10) as client:
            for q in queries:
                params = {
                    'name': q,
                    'count': 10,  # Tăng số lượng kết quả
                    'language': 'vi',
                    'format': 'json',
                }
                print(f"DEBUG: Querying with: {q}")
                r = await client.get(self.GEOCODE_URL, params=params)
                if r.status_code != 200:
                    print(f"DEBUG: HTTP {r.status_code} for query '{q}'")
                    continue
                data = r.json()
                results = data.get('results') or []
                print(f"DEBUG: Found {len(results)} results for '{q}'")
                
                if not results:
                    continue
                
                # Log all results for debugging
                for i, result in enumerate(results[:3]):  # Log first 3 results
                    print(f"DEBUG: Result {i+1}: {result.get('name')} ({result.get('country_code')})")
                
                # Prefer Vietnam results
                vn = next((it for it in results if (it.get('country_code') or '').upper() == 'VN'), None)
                item = vn or results[0]
                try:
                    coords = (
                        float(item.get('latitude')),
                        float(item.get('longitude')),
                        item.get('name') or normalized_location,
                    )
                    print(f"DEBUG: Selected: {coords[2]} at ({coords[0]}, {coords[1]})")
                    return coords
                except Exception as e:
                    print(f"DEBUG: Error parsing result: {e}")
                    continue
        
        print(f"DEBUG: No results found for '{location}'")
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


class IntentRouterAgentExecutor(AgentExecutor):
    """Router sử dụng intent classification thay vì rule-based."""

    def __init__(self) -> None:
        self.weather = WeatherAgentExecutor()
        self.chat = GeminiAgentExecutor()
        self._intent_model = None  # Có thể cache Gemini hoặc model khác
        # Lưu intent gần nhất để wrapper có thể đọc
        self.last_intent: str | None = None

    async def _classify_intent(self, text: str, context_id: str = 'default') -> str:
        """Phân loại intent bằng Gemini API với context."""
        if not text.strip():
            return "chat"

        global _gemini_model
        if _gemini_model is None:
            try:
                import google.generativeai as genai
                api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
                if not api_key:
                    return "chat"
                genai.configure(api_key=api_key)
                _gemini_model = genai.GenerativeModel("gemini-2.5-flash")
            except Exception:
                return "chat"

        # Lấy memory context cho phiên này
        memory = get_or_create_memory(context_id)
        history_text = memory.load_memory_variables({"input": text})['history']

        # Tạo prompt với context
        if history_text:
            prompt = f"""
Bạn là bộ phân loại intent thông minh.

Ngữ cảnh trước đó:
{history_text}

Câu hỏi hiện tại: "{text}"

Intent hợp lệ: [weather, chat]

Quy tắc phân loại:
- Nếu câu hỏi liên quan đến thời tiết, nhiệt độ, khí hậu, dự báo, mưa, nắng, gió, bão → trả "weather"
- Nếu câu hỏi về địa danh, tỉnh, thành phố mà có thể liên quan đến thời tiết → trả "weather"
- Nếu câu hỏi chung chung, không liên quan thời tiết → trả "chat"
- Nếu câu hỏi tiếp tục cuộc trò chuyện trước đó → trả "chat"

Chỉ trả đúng 1 từ (weather hoặc chat).
"""
        else:
            prompt = f"""
Bạn là bộ phân loại intent. 
Người dùng vừa nói: "{text}".
Intent hợp lệ: [weather, chat].
Nếu câu hỏi liên quan đến thời tiết, nhiệt độ, khí hậu, dự báo → trả "weather".
Nếu không → trả "chat".
Chỉ trả đúng 1 từ (weather hoặc chat).
"""

        try:
            # Prefer async API if available
            response_text = None
            try:
                generate_content_async = getattr(_gemini_model, 'generate_content_async', None)
                if callable(generate_content_async):
                    resp = await generate_content_async(prompt)
                    response_text = getattr(resp, 'text', None) if resp else None
                else:
                    # Fallback to sync call in a thread if async not available
                    import asyncio
                    loop = asyncio.get_running_loop()
                    resp = await loop.run_in_executor(None, _gemini_model.generate_content, prompt)
                    response_text = getattr(resp, 'text', None) if resp else None
            except Exception:
                response_text = None

            if response_text:
                raw = response_text.strip().lower()
                if "weather" in raw:
                    return "weather"
            return "chat"
        except Exception:
            return "chat"

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        text = ""
        try:
            text = context.get_user_input() or ""
        except Exception:
            pass

        # Lấy context_id cho phiên này
        context_id = getattr(context, 'context_id', 'default')
        
        # Lưu tin nhắn người dùng vào memory trước khi phân loại intent
        memory = get_or_create_memory(context_id)
        memory.save_context({"input": text}, {"output": ""})

        # Phân loại intent với context
        intent = await self._classify_intent(text, context_id)
        print(f"Intent: {intent} (Context ID: {context_id})")
        # Ghi lại intent để bên ngoài có thể đọc
        self.last_intent = intent
        
        if intent == "weather":
            await self.weather.execute(context, event_queue)
        else:
            await self.chat.execute(context, event_queue)

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        # Huỷ trên cả 2 agent
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