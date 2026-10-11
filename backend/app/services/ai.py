"""GPT 호출. 업무 요약을 시스템 프롬프트에 넣어(컨텍스트 주입) 내 기록 기준으로 답하게 한다."""
from .. import config
from .summary import to_prompt_text

SYSTEM_TEMPLATE = """당신은 'ADHD를 위한 업무 비서'입니다.
사용자는 AXOLVE(영어 라이팅 교육)를 운영하면서 교재, 웹사이트, 인스타, 기출 정리 등 여러 일을 동시에 벌이는 사람입니다.
일이 흩어지고 무엇부터 할지 정하기 어려워하는 사용자를 돕습니다.

[사용자 업무 데이터 요약]
{summary}

[답변 규칙]
1. 위 데이터에 있는 숫자·날짜·프로젝트 이름만 근거로 답합니다. 데이터에 없으면 "기록에 없어요"라고 말합니다.
2. 짧게 답합니다. 할 일을 추천할 때는 반드시 3개 이하로 고릅니다. 사실을 묻는 질문(멈춘 프로젝트 목록 등)은 빠짐없이 한 줄씩 짧게 나열합니다.
3. "뭐부터 할까", "오늘 할 일" 같은 질문에는 [남은 할 일]의 NOW 항목에서 고릅니다. 최근 기록과 이어지는 일을 우선합니다.
4. 할 일을 물으면 마지막 줄에 "👉 지금 할 한 가지:"를 씁니다. 할 일 목록에 있는 실제 작업 하나를 15분 안에 시작할 수 있는 구체적인 행동으로 바꿔 씁니다. "계획 세우기"처럼 막연한 말은 쓰지 않습니다.
5. 멈춘 일을 탓하지 않습니다. 다시 시작할 수 있는 작은 첫 단계를 제안합니다.
6. 친근한 존댓말을 씁니다.
7. 의학적 진단이나 치료 조언은 하지 않습니다."""


class AIUnavailable(Exception):
    pass


def build_system_prompt(summary: dict) -> str:
    return SYSTEM_TEMPLATE.format(summary=to_prompt_text(summary))


def ask(summary: dict, history: list[dict], message: str) -> str:
    if not config.OPENAI_API_KEY:
        raise AIUnavailable("OPENAI_API_KEY가 설정되지 않았습니다")
    from openai import OpenAI, OpenAIError

    client = OpenAI(api_key=config.OPENAI_API_KEY, timeout=30)
    messages = [{"role": "system", "content": build_system_prompt(summary)}]
    messages += [{"role": m["role"], "content": m["content"]} for m in history[-config.CHAT_HISTORY_LIMIT:]]
    messages.append({"role": "user", "content": message})
    try:
        res = client.chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=messages,
            max_completion_tokens=config.OPENAI_MAX_TOKENS,
            temperature=0.4,
        )
    except OpenAIError as e:
        raise AIUnavailable(f"GPT 호출 실패: {e.__class__.__name__}") from e
    return (res.choices[0].message.content or "").strip()
