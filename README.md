# AI Agent với Conversation Memory

Hệ thống AI Agent thông minh với khả năng lưu trữ và quản lý ngữ cảnh cuộc trò chuyện.

## Tính năng chính

- 🤖 **Intent Classification**: Tự động phân loại ý định người dùng (chat vs weather)
- 💬 **Conversation Memory**: Lưu trữ ngữ cảnh cuộc trò chuyện
- 🌤️ **Weather API**: Hỗ trợ tra cứu thời tiết theo địa danh
- 🔄 **Context Awareness**: Bot nhớ được những gì đã nói trước đó

## Cài đặt

### 1. Cài đặt dependencies cơ bản

```bash
pip install -r requirements.txt
```

### 2. Cài đặt thư viện memory (tùy chọn)

#### LangChain Memory (Khuyến nghị)
```bash
pip install langchain langchain-community
```

#### Redis Memory (Cho production)
```bash
pip install redis
# Cài đặt Redis server: https://redis.io/download
```

#### SQL Memory (Cho database)
```bash
pip install sqlalchemy
```

#### Vector Memory (Cho AI-powered search)
```bash
pip install scikit-learn numpy
```

### 3. Cấu hình API Key

Tạo file `.env`:
```env
GOOGLE_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-1.5-flash
```

## Sử dụng

### Chạy server

```bash
python main.py
```

Server sẽ chạy tại `http://localhost:9999`

### Truy cập chat interface

- **Chat UI**: `http://localhost:9999/chat`
- **API Endpoint**: `http://localhost:9999/`

### Demo memory systems

```bash
python memory_demo.py
```

## Các hệ thống Memory

### 1. **Basic Memory** (Mặc định)
- Đơn giản, không cần thư viện bổ sung
- Lưu trữ trong memory, mất khi restart
- Phù hợp cho development và testing

### 2. **LangChain Memory** (Khuyến nghị)
- Chuyên nghiệp, nhiều tính năng
- Hỗ trợ nhiều loại memory khác nhau
- Tích hợp tốt với AI/ML workflows

### 3. **Redis Memory**
- Persistent storage
- Scalable, real-time
- Phù hợp cho production với nhiều user

### 4. **SQL Memory**
- Structured storage
- Queryable, reliable
- Phù hợp cho analytics và reporting

### 5. **Vector Memory**
- Semantic search
- AI-powered similarity
- Phù hợp cho tìm kiếm thông minh

## Cấu trúc code

```
project/
├── main.py                    # Entry point với FastAPI app
├── agent/                     # Core agent logic
│   ├── __init__.py           # Package exports
│   ├── skills.py             # Skill definitions
│   ├── cards.py              # Agent card definitions
│   ├── app_factory.py        # A2A server factory
│   ├── agent_executor_wrapper.py # Wrapper với logging
│   ├── database.py           # Database operations
│   └── routes.py             # HTML routes
├── service/                   # Business logic layer
│   ├── __init__.py           # Service exports
│   └── conversation_service.py # Conversation business logic
├── router/                    # API endpoints
│   ├── __init__.py           # Router exports
│   ├── chat_routes.py        # Chat API endpoints
│   ├── conversation_routes.py # Conversation management
│   └── health_routes.py      # Health checks
├── middleware/                # Middleware
│   └── cors/                 # CORS middleware
│       └── cors.py           # CORS configuration
└── initialize/                # Service initialization
    ├── __init__.py           # Init exports
    └── run.py                # Database connections
```

```
HTTP Request → Router → Service → Agent → Database
     ↑           ↓        ↓        ↓        ↓
Response ← Router ← Service ← Agent ← Database
```

## Ví dụ sử dụng

### Chat với context

1. **Người dùng**: "Tôi tên là Nam"
2. **Bot**: "Xin chào Nam! Rất vui được gặp bạn."
3. **Người dùng**: "Bạn nhớ tên tôi không?"
4. **Bot**: "Có, bạn tên Nam!" (nhớ được từ context)

### Weather query

1. **Người dùng**: "Thời tiết Hà Nội hôm nay"
2. **Bot**: "Thời tiết tại Hà Nội: Nhiệt độ hiện tại: 25°C — Trời quang."

## Troubleshooting

### Lỗi "LangChain not available"
```bash
pip install langchain langchain-community
```

### Lỗi "Redis connection failed"
- Cài đặt Redis server
- Hoặc sử dụng Basic Memory (mặc định)

### Lỗi "Gemini API key missing"
- Tạo file `.env` với `GOOGLE_API_KEY`
- Hoặc set environment variable

## Đóng góp

1. Fork repository
2. Tạo feature branch
3. Commit changes
4. Push to branch
5. Tạo Pull Request

## License

MIT License - xem file LICENSE để biết thêm chi tiết.