from a2a.types import AgentSkill

def create_chat_skill() -> AgentSkill:
    """Tạo skill chat tổng quát sử dụng Gemini"""
    return AgentSkill(
        id='chat',
        name='Chat tổng quát (Gemini)',
        description='Trả lời câu hỏi chung qua Gemini',
        tags=['chat', 'gemini'],
        examples=['Xin chào', 'giải thích về AI'],
    )

def create_weather_skill() -> AgentSkill:
    """Tạo skill thời tiết theo tỉnh/thành"""
    return AgentSkill(
        id='weather',
        name='Thời tiết theo tỉnh/thành',
        description='Hỏi thời tiết; yêu cầu nêu rõ tỉnh/thành',
        tags=['weather', 'thời tiết'],
        examples=['Thời tiết Hà Nội', 'Thời tiết ở Đà Nẵng hôm nay'],
    )

def get_all_skills() -> list[AgentSkill]:
    """Lấy tất cả các skill có sẵn"""
    return [create_chat_skill(), create_weather_skill()]
