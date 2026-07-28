import json
from typing import Any

from openai import OpenAI

from config import Config


class MedicalSummaryError(Exception):
    """진료 요약 생성 실패."""

#이부분이 질문 중요도 점수 의논하거나 여러번 봐야할듯
QUESTION_LIMIT = 3
QUESTION_MIN_SCORE = 50
CATEGORY_BONUS: dict[str, int] = {
    "재방문": 15,
    "약": 15,
    "치료": 10,
    "검사": 25,
    "증상": 10,
    "생활관리": 5,
    "기타": 0,
    "꼭": 20,
    "명심": 20,
    "다시": 15,
}


def _get_client() -> OpenAI:
    if not Config.OPENAI_API_KEY:
        raise MedicalSummaryError(
            "OPENAI_API_KEY 환경변수가 설정되지 않았습니다."
        )

    return OpenAI(api_key=Config.OPENAI_API_KEY)


def _normalize_string_list(value: Any) -> list[str]:
    """GPT 배열을 공백과 중복이 제거된 문자열 목록으로 정리합니다."""
    if not isinstance(value, list):
        return []

    normalized: list[str] = []
    seen: set[str] = set()

    for item in value:
        text = str(item).strip()
        comparable = " ".join(text.split())

        if text and comparable not in seen:
            normalized.append(text)
            seen.add(comparable)

    return normalized


def _normalize_questions(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []

    normalized_questions: list[dict[str, Any]] = []
    seen_questions: set[str] = set()

    for item in value:
        if not isinstance(item, dict):
            continue

        question = str(item.get("question", "")).strip()
        answer = str(item.get("answer", "")).strip()
        category = str(item.get("category", "기타")).strip() or "기타"

        try:
            importance = int(item.get("importance", 50))
        except (TypeError, ValueError):
            importance = 50

        importance = max(0, min(100, importance))
        comparable = " ".join(question.split())

        if not question or comparable in seen_questions:
            continue

        normalized_questions.append({
            "question": question,
            "answer": answer,
            "importance": importance,
            "category": category,
        })
        seen_questions.add(comparable)

    return normalized_questions


def _normalize_medical_terms(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []

    normalized_terms: list[dict[str, str]] = []
    seen_terms: set[str] = set()

    for item in value:
        if not isinstance(item, dict):
            continue

        term = str(item.get("term", "")).strip()
        description = str(item.get("description", "")).strip()
        comparable = term.casefold()

        if not term or not description or comparable in seen_terms:
            continue

        normalized_terms.append({
            "term": term,
            "description": description,
        })
        seen_terms.add(comparable)

    return normalized_terms


def _join_lines(items: list[str]) -> str:
    """여기서 db등 넘겨줄 \n문자열로 변환"""
    return "\n".join(item.strip() for item in items if item.strip())


def _select_important_questions(
    questions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """위에서 적어둔 점수를 통해서 핵심 질문을 선정"""
    selected: list[dict[str, Any]] = []

    for item in questions:
        category = str(item.get("category", "기타"))
        answer = str(item.get("answer", "")).strip()
        base_score = int(item.get("importance", 50))

        final_score = base_score + CATEGORY_BONUS.get(category, 0)
        final_score += 5 if answer else -15
        final_score = max(0, min(100, final_score))

        if final_score < QUESTION_MIN_SCORE:
            continue

        selected.append({
            **item,
            "finalScore": final_score,
        })

    selected.sort(
        key=lambda item: (
            item["finalScore"],
            bool(item.get("answer")),
        ),
        reverse=True,
    )

    return selected[:QUESTION_LIMIT]


def _questions_to_text(questions: list[dict[str, Any]]) -> str:
    blocks: list[str] = []

    for item in questions:
        answer = str(item.get("answer", "")).strip()
        if not answer:
            answer = "대화에서 의료진의 답변을 확인하지 못했습니다."

        blocks.append(
            f"Q. {item['question']}\nA. {answer}"
        )

    return "\n\n".join(blocks)


def _medical_terms_to_text(terms: list[dict[str, str]]) -> str:
    return _join_lines([
        f"{item['term']}: {item['description']}"
        for item in terms
    ])


def _validate_report(report: Any) -> dict[str, str]:
    """GPT 구조를 검증한 뒤 모든 외부 응답 필드를 문자열로 변환합니다."""
    if not isinstance(report, dict):
        raise MedicalSummaryError(
            "GPT 요약 결과가 JSON 객체가 아닙니다."
        )

    main_symptoms = _normalize_string_list(
        report.get("mainSymptoms", [])
    )
    doctor_opinion = _normalize_string_list(
        report.get("doctorOpinion", [])
    )
    examinations = _normalize_string_list(
        report.get("examinations", [])
    )

    # 생활관리와 꼭 기억할 내용을 하나의 영역으로 합칩니다.
    remember_items = _normalize_string_list(
        report.get("dailyCare", [])
    ) + _normalize_string_list(
        report.get("mustRemember", [])
    )
    remember_items = _normalize_string_list(remember_items)

    questions = _normalize_questions(
        report.get("questions", [])
    )
    important_questions = _select_important_questions(questions)

    medical_terms = _normalize_medical_terms(
        report.get("medicalTerms", [])
    )

    return {
        "mainSymptoms": _join_lines(main_symptoms),
        "doctorOpinion": _join_lines(doctor_opinion),
        "examinations": _join_lines(examinations),
        "remember": _join_lines(remember_items),
        "questionAnswer": _questions_to_text(important_questions),
        "difficultWords": _medical_terms_to_text(medical_terms),
        "disclaimer": (
            "이 내용은 대화 기록을 이해하기 쉽게 정리한 것으로, "
            "의료진의 진단서나 처방전을 대신하지 않습니다."
        ),
    }


def summarize_conversation(all_chat_text: str) -> dict[str, str]:
    """Spring에서 받은 전체 채팅 문자열을 진료 기록 필드로 정리합니다."""
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
당신은 대면 진료 대화를 사용자가 이해하기 쉽게 정리하는 의료 대화 기록 보조 시스템입니다.

화자 표기:
- '기관'은 의사 또는 의료기관 담당자입니다.
- '나'는 진료를 받는 사용자입니다.

반드시 지킬 원칙:
1. 대화에 실제로 나온 내용만 정리합니다.
2. 대화에 없는 질병, 진단, 검사, 처방을 추측하지 않습니다.
3. 확정되지 않은 내용은 확정된 진단처럼 표현하지 않습니다.
4. 기관이 여러 질문을 연속해서 한 뒤 사용자가 한 번에 답할 수 있습니다.
5. 사용자 질문 여러 개에 기관이 한 번에 답할 수도 있으므로 대화 전체의 의미로 질문과 답변을 연결합니다.
6. questions에는 '나'가 기관에 물어본 질문만 포함하며, 기관이 사용자에게 한 문진 질문은 포함하지 않습니다.
7. 의학 용어는 사용자가 이해하기 쉬운 말로 설명합니다.
8. 같은 내용을 여러 항목에 반복하지 않습니다.
9. 모든 내용은 한국어로 작성합니다.
10. 결과는 반드시 지정된 JSON 구조로만 반환합니다.

JSON 구조:
{
  "mainSymptoms": [
    "사용자가 말한 주요 증상과 발생 시점"
  ],
  "doctorOpinion": [
    "기관이 설명한 판단, 원인 가능성, 치료 방향"
  ],
  "examinations": [
    "진행했거나 안내한 검사, 처치, 처방"
  ],
  "dailyCare": [
    "일상생활 관리 방법과 복약 방법"
  ],
  "mustRemember": [
    "주의사항, 재방문 조건, 반드시 기억할 내용"
  ],
  "questions": [
    {
      "question": "사용자인 '나'가 기관에 물어본 질문",
      "answer": "대화에서 확인되는 기관의 답변",
      "importance": 0,
      "category": "증상|검사|치료|약물|생활관리|재방문|기타"
    }
  ],
  "medicalTerms": [
    {
      "term": "대화에 실제로 나온 의료 용어",
      "description": "쉽게 풀어쓴 설명"
    }
  ]
}

작성 규칙:
- 각 항목은 한 줄만 읽어도 이해되는 짧고 완결된 문장으로 작성합니다.
- 근거가 없는 항목은 빈 배열을 사용합니다.
- questions의 답변이 확인되지 않으면 answer는 빈 문자열로 작성합니다.
- importance는 0~100 정수이며 치료 결정, 약물, 검사, 재방문과 관련될수록 높게 부여합니다.
- medicalTerms에는 대화에서 실제로 등장한 어려운 의료 용어만 포함합니다.
- JSON 이외의 설명, 코드 블록, 마크다운은 출력하지 않습니다.
"""

    client = _get_client()

    try:
        response = client.chat.completions.create(
            model=Config.OPENAI_MODEL,
            temperature=0.1,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": system_prompt.strip(),
                },
                {
                    "role": "user",
                    "content": (
                        "다음 진료 대화를 정리하세요.\n\n"
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
