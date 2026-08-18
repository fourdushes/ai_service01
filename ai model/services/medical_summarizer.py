import json
from typing import Any

from openai import OpenAI

from config import Config


class MedicalSummaryError(Exception):
    """진료 요약 생성 실패."""


def _get_client() -> OpenAI:
    if not Config.OPENAI_API_KEY:
        raise MedicalSummaryError(
            "OPENAI_API_KEY 환경변수가 설정되지 않았습니다."
        )

    return OpenAI(
        api_key=Config.OPENAI_API_KEY,
    )


def _normalize_string(value: Any) -> str:
    """
    AI 응답값을 문자열로 정리합니다.

    값이 없으면 '없음'이라는 문구를 만들지 않고
    빈 문자열을 반환합니다.
    """
    if value is None:
        return ""

    if isinstance(value, list):
        normalized_items: list[str] = []
        seen: set[str] = set()

        for item in value:
            text = str(item).strip()
            comparable = " ".join(text.split())

            if text and comparable not in seen:
                normalized_items.append(text)
                seen.add(comparable)

        return "\n".join(normalized_items)

    if not isinstance(value, str):
        return ""

    return value.strip()


def _validate_report(report: Any) -> dict[str, str]:
    """
    AI 응답이 올바른 JSON 객체인지 검사하고
    외부로 전달할 두 필드만 반환합니다.
    """
    if not isinstance(report, dict):
        raise MedicalSummaryError(
            "GPT 요약 결과가 JSON 객체가 아닙니다."
        )

    medical_opinion = _normalize_string(
        report.get("medicalOpinion")
    )

    prescription_care = _normalize_string(
        report.get("prescriptionCare")
    )

    return {
        "medicalOpinion": medical_opinion,
        "prescriptionCare": prescription_care,
    }


def summarize_conversation(
    all_chat_text: str,
) -> dict[str, str]:
    """
    전체 진료 대화에서 의료진 의견과
    처방·생활 관리 내용만 추출합니다.
    """
    if not isinstance(all_chat_text, str):
        raise MedicalSummaryError(
            "allChatText는 문자열이어야 합니다."
        )

    conversation_text = all_chat_text.strip()

    if not conversation_text:
        raise MedicalSummaryError(
            "요약할 진료 대화가 없습니다."
        )

    if len(conversation_text) > Config.MAX_TEXT_LENGTH:
        raise MedicalSummaryError(
            "대화 내용이 허용된 최대 길이를 초과했습니다."
        )

    system_prompt = """
당신은 대면 진료 대화를 정리하는 의료 대화 기록 보조 시스템입니다.

화자 표기:
- '기관' 또는 '의사'는 의사나 의료기관 담당자입니다.
- '나' 또는 '환자'는 진료를 받는 사용자입니다.

진료 대화에서 다음 두 항목만 추출합니다.

1. medicalOpinion
- 의료진이 말한 진단, 판단, 의심되는 질환, 원인 가능성,
  검사 필요성 및 치료 방향을 정리합니다.
- 의료진이 실제로 말하지 않은 내용은 추가하지 않습니다.
- 사용자가 말한 증상만 있고 의료진의 판단이나 의견이 없으면
  빈 문자열을 반환합니다.

2. prescriptionCare
- 의료진이 안내한 약, 처방, 복약 방법, 처치,
  생활 관리, 주의사항 및 재방문 조건을 정리합니다.
- 의료진이 실제로 안내하지 않은 내용은 추가하지 않습니다.
- 관련 내용이 없으면 빈 문자열을 반환합니다.

반드시 지킬 원칙:
1. 대화에 실제로 나온 내용만 사용합니다.
2. 대화에 없는 질병, 진단, 검사, 처방을 추측하지 않습니다.
3. 가능성이나 의심으로 말한 내용은 확정된 진단처럼 쓰지 않습니다.
4. 같은 내용을 반복하지 않습니다.
5. 환자의 주요 증상, 질문과 답변, 어려운 의료 용어는 별도 항목으로 만들지 않습니다.
6. 간결하고 이해하기 쉬운 한국어 문장으로 작성합니다.
7. 값이 없는 항목에는 '없음', '해당 없음' 등의 문구를 넣지 말고 빈 문자열을 사용합니다.
8. 결과는 반드시 아래 JSON 구조로만 반환합니다.
9. JSON 이외의 설명, 마크다운, 코드 블록은 출력하지 않습니다.

JSON 구조:
{
  "medicalOpinion": "의료진의 의견을 정리한 내용",
  "prescriptionCare": "처방과 생활 관리 내용을 정리한 내용"
}
"""

    client = _get_client()

    try:
        response = client.chat.completions.create(
            model=Config.OPENAI_MODEL,
            temperature=0.1,
            response_format={
                "type": "json_object",
            },
            messages=[
                {
                    "role": "system",
                    "content": system_prompt.strip(),
                },
                {
                    "role": "user",
                    "content": (
                        "다음 진료 대화에서 의료진 의견과 "
                        "처방·생활 관리 내용만 정리하세요.\n\n"
                        f"{conversation_text}"
                    ),
                },
            ],
        )

    except Exception as error:
        raise MedicalSummaryError(
            "OpenAI 요약 요청에 실패했습니다."
        ) from error

    if not response.choices:
        raise MedicalSummaryError(
            "OpenAI에서 요약 결과를 반환하지 않았습니다."
        )

    content = response.choices[0].message.content

    if not content:
        raise MedicalSummaryError(
            "OpenAI에서 빈 요약 결과를 반환했습니다."
        )

    try:
        parsed = json.loads(content)

    except json.JSONDecodeError as error:
        raise MedicalSummaryError(
            "OpenAI 응답을 JSON으로 해석하지 못했습니다."
        ) from error

    return _validate_report(parsed)