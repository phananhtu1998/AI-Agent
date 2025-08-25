from a2a.types import AgentCapabilities, AgentCard
from .skills import get_all_skills

def create_public_agent_card() -> AgentCard:
    """Tạo public-facing agent card"""
    return AgentCard(
        name='Router Agent',
        description='Điều phối giữa chat (Gemini) và thời tiết',
        url='http://localhost:9999/',
        version='1.0.0',
        default_input_modes=['text'],
        default_output_modes=['text'],
        capabilities=AgentCapabilities(streaming=True),
        skills=get_all_skills(),
        supports_authenticated_extended_card=True,
    )

def create_extended_agent_card() -> AgentCard:
    """Tạo authenticated extended agent card"""
    public_card = create_public_agent_card()
    return public_card.model_copy(
        update={
            'name': 'Router Agent - Extended',
            'description': 'Phiên bản đầy đủ cho người dùng xác thực',
            'version': '1.0.1',
            'skills': get_all_skills(),
        }
    )
