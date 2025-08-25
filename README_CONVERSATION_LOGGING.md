# Hệ thống Conversation Logging

Hệ thống tự động lưu thông tin conversation khi agent sinh ra kết quả, sử dụng PostgreSQL và Redis.

## 🚀 Cài đặt và Khởi chạy

### 1. Tạo bảng database
```bash
python initialize/create_tables.py
```

### 2. Khởi chạy ứng dụng
```bash
python main.py
```

## 📊 Cấu trúc Database

### Bảng `conversations`
```sql
CREATE TABLE conversations (
    conversation_id UUID PRIMARY KEY,
    session_id VARCHAR(255) NOT NULL,
    user_message TEXT NOT NULL,
    agent_response TEXT NOT NULL,
    skill_used VARCHAR(100),
    processing_time DECIMAL(10,3),
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

## 🔧 API Endpoints

### Health Routes
```http
GET /health/                    # Health check
GET /health/ping                # Simple ping
GET /health/status              # Detailed system status
```

### Conversation Routes
```http
GET /conversation/test-log      # Test log conversation
GET /conversation/history/{session_id}?limit=10  # Lấy conversation history
GET /conversation/summary/{session_id}           # Lấy session summary
POST /conversation/log          # Log conversation thủ công
GET /conversation/stats         # Lấy thống kê tổng quan
```

### Chat Routes
```http
POST /chat/                    # Chat với agent
GET /chat/session/{session_id} # Lấy thông tin session chat
DELETE /chat/session/{session_id} # Xóa session chat
```

## 💻 Cách sử dụng trong code

### 1. Chat với agent qua API
```python
import requests

# Chat với agent
response = requests.post("http://localhost:9999/chat/", json={
    "message": "Xin chào, bạn có thể giúp tôi không?",
    "session_id": "user_123",  # Optional
    "user_id": "user_123",     # Optional
    "metadata": {              # Optional
        "source": "web",
        "platform": "mobile"
    }
})

print(response.json())
```

### 2. Log conversation thủ công
```python
from agent import log_agent_response

success = await log_agent_response(
    session_id="user_123",
    user_message="Xin chào",
    agent_response="Chào bạn!",
    skill_used="chat",
    processing_time=1.5,
    metadata={"source": "web", "user_id": "123"}
)
```

### 3. Lấy conversation history
```python
from agent import get_conversation_history

history = await get_conversation_history("user_123", limit=10)
```

### 4. Lấy session summary
```python
from agent import get_session_summary

summary = await get_session_summary("user_123")
```

## 🔄 Tự động Logging

Hệ thống tự động log conversation thông qua `AgentExecutorWrapper`:

```python
# Trong agent/app_factory.py
def create_request_handler() -> DefaultRequestHandler:
    original_executor = IntentRouterAgentExecutor()
    wrapped_executor = wrap_agent_executor(original_executor)  # Tự động log
    
    return DefaultRequestHandler(
        agent_executor=wrapped_executor,
        task_store=InMemoryTaskStore(),
    )
```

## 📈 Tính năng

- ✅ **Tự động logging**: Không cần thêm code vào agent executor
- ✅ **Performance tracking**: Đo thời gian xử lý
- ✅ **Skill tracking**: Theo dõi skill được sử dụng
- ✅ **Caching**: Redis cache cho performance
- ✅ **Error logging**: Log cả lỗi nếu có
- ✅ **Metadata**: Lưu thông tin bổ sung
- ✅ **Session management**: Quản lý theo session

## 🗄️ Database Operations

### PostgreSQL
- Lưu trữ conversation chính
- Indexes cho performance
- JSONB cho metadata linh hoạt

### Redis
- Cache conversation gần đây
- Session summary
- Performance optimization

## 🔍 Monitoring

### Logs
- File: `app.log`
- Console với colors
- UTF-8 encoding

### Metrics
- Processing time
- Skill usage
- Error rates
- Session statistics

## 🛠️ Troubleshooting

### Lỗi kết nối database
```bash
# Kiểm tra PostgreSQL
psql -h localhost -U admin -d chatbot

# Kiểm tra Redis
redis-cli ping
```

### Lỗi import
```bash
# Cài đặt dependencies
pip install asyncpg redis colorama
```

## 📝 Ví dụ Response

### Conversation History
```json
{
  "session_id": "user_123",
  "conversations": [
    {
      "conversation_id": "uuid-here",
      "user_message": "Xin chào",
      "agent_response": "Chào bạn!",
      "skill_used": "chat",
      "processing_time": 1.5,
      "created_at": "2024-01-01T12:00:00Z"
    }
  ],
  "count": 1
}
```

### Session Summary
```json
{
  "session_id": "user_123",
  "summary": {
    "total_conversations": 5,
    "avg_processing_time": 1.2,
    "last_conversation_at": "2024-01-01T12:00:00Z",
    "first_conversation_at": "2024-01-01T11:00:00Z"
  }
}
```

## 🎯 Use Cases

1. **Analytics**: Phân tích hiệu suất agent
2. **Debugging**: Debug khi có lỗi
3. **User Experience**: Theo dõi trải nghiệm người dùng
4. **Performance**: Tối ưu hiệu suất
5. **Audit**: Kiểm tra lịch sử conversation

## 🔧 Configuration

### Environment Variables
```bash
# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=admin
POSTGRES_PASSWORD=123
POSTGRES_DB=chatbot

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_DB=0
```

### Logging Configuration
- Level: INFO
- File: app.log
- Console: Colored output
- Encoding: UTF-8
