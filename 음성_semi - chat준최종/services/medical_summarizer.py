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

    return OpenAI(api_key=Config.OPENAI_API_KEY)


def _normalize_conversation(
    conversation: list[dict[str, Any]],
) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []

    speaker_aliases = {
        "doctor": "doctor",
        "institution": "doctor",
        "institutions": "doctor",
        "medical": "doctor",
        "의사": "doctor",
        "의료기관": "doctor",

        "patient": "patient",
        "ward": "patient",
        "user": "patient",
        "환자": "patient",
        "피보호자": "patient",
    }

    for item in conversation:
        if not isinstance(item, dict):
            continue

        raw_speaker = str(
            item.get("speaker")
            or item.get("sender")
            or item.get("senderType")
            or item.get("role")
            or ""
        ).strip()

        text = str(
            item.get("text")
            or item.get("content")
            or item.get("message")
            or ""
        ).strip()

        speaker = speaker_aliases.get(raw_speaker.lower())

        if speaker is None or not text:
            continue

        normalized.append({
            "speaker": speaker,
            "text": text,
        })

    return normalized


def _conversation_to_text(
    conversation: list[dict[str, str]],
) -> str:
    speaker_names = {
        "doctor": "의사",
        "patient": "환자",
    }

    return "\n".join(
        f"{speaker_names[item['speaker']]}: {item['text']}"
        for item in conversation
    )


def _validate_report(report: Any) -> dict[str, Any]:
    if not isinstance(report, dict):
        raise MedicalSummaryError(
            "GPT 요약 결과가 JSON 객체가 아닙니다."
        )

    list_fields = [
        "mainSymptoms",
        "doctorOpinion",
        "examinations",
        "dailyCare",
        "mustRemember",
    ]

    normalized: dict[str, Any] = {}

    for field in list_fields:
        value = report.get(field, [])

        if not isinstance(value, list):
            value = []

        normalized[field] = [
            str(item).strip()
            for item in value
            if str(item).strip()
        ]

    questions = report.get("questions", [])
    normalized_questions: list[dict[str, Any]] = []

    if isinstance(questions, list):
        for question in questions:
            if not isinstance(question, dict):
                continue

            question_text = str(
                question.get("question", "")
            ).strip()

            answer = str(
                question.get("answer", "")
            ).strip()

            category = str(
                question.get("category", "기타")
            ).strip()

            try:
                importance = int(
                    question.get("importance", 50)
                )
            except (TypeError, ValueError):
                importance = 50

            importance = max(0, min(100, importance))

            if question_text:
                normalized_questions.append({
                    "question": question_text,
                    "answer": answer,
                    "importance": importance,
                    "category": category or "기타",
                })

    normalized["questions"] = normalized_questions

    medical_terms = report.get("medicalTerms", [])
    normalized_terms: list[dict[str, str]] = []

    if isinstance(medical_terms, list):
        for item in medical_terms:
            if not isinstance(item, dict):
                continue

            term = str(item.get("term", "")).strip()
            description = str(
                item.get("description", "")
            ).strip()

            if term and description:
                normalized_terms.append({
                    "term": term,
                    "description": description,
                })

    normalized["medicalTerms"] = normalized_terms

    normalized["summary"] = str(
        report.get("summary", "")
    ).strip()

    normalized["disclaimer"] = (
        "이 내용은 대화 기록을 이해하기 쉽게 정리한 것으로, "
        "의료진의 진단서나 처방전을 대신하지 않습니다."
    )

    return normalized


def summarize_conversation(
    conversation: list[dict[str, Any]],
) -> dict[str, Any]:
    normalized = _normalize_conversation(conversation)

    if not normalized:
        raise MedicalSummaryError(
            "요약할 수 있는 유효한 진료 대화가 없습니다."
        )

    if len(normalized) > Config.MAX_CONVERSATION_MESSAGES:
        raise MedicalSummaryError(
            "허용된 최대 대화 개수를 초과했습니다."
        )

    conversation_text = _conversation_to_text(normalized)

    if len(conversation_text) > Config.MAX_TEXT_LENGTH:
        raise MedicalSummaryError(
            "대화 내용이 허용된 최대 길이를 초과했습니다."
        )

    system_prompt = """
당신은 대면 진료 대화를 환자와 보호자가 이해하기 쉽게 정리하는
의료 대화 기록 보조 시스템입니다.

다음 원칙을 반드시 지키세요.

1. 대화에 실제로 나온 내용만 정리합니다.
2. 대화에 없는 질병, 진단, 검사, 처방을 추측하지 않습니다.
3. 확정되지 않은 내용은 확정된 진단처럼 표현하지 않습니다.
4. 증상, 의료진 의견, 검사 안내, 생활 관리, 중요사항을 구분합니다.
5. 환자의 질문과 의사의 답변을 가능한 범위에서 연결합니다.
6. 의학 용어는 환자가 이해하기 쉬운 말로 설명합니다.
7. 개인정보는 새로 만들어내지 않습니다.
8. 모든 내용은 한국어로 작성합니다.
9. 결과는 반드시 지정된 JSON 구조로만 반환합니다.

JSON 구조:
{
  "summary": "진료 내용을 2~4문장으로 정리",
  "mainSymptoms": ["주요 증상"],
  "doctorOpinion": ["의료진이 설명한 판단이나 가능성"],
  "examinations": ["검사 또는 확인이 필요한 사항"],
  "dailyCare": ["일상생활 관리 방법"],
  "mustRemember": ["재방문 조건 등 꼭 기억할 사항"],
  "questions": [
    {
      "question": "환자의 질문",
      "answer": "대화에서 확인되는 의료진 답변",
      "importance": 0,
      "category": "증상|검사|치료|약물|생활관리|재방문|기타"
    }
  ],
  "medicalTerms": [
    {
      "term": "대화에 나온 의료용어",
      "description": "쉽게 풀어쓴 설명"
    }
  ]
}

해당 항목의 근거가 대화에 없으면 빈 배열을 사용하세요.
답변이 확인되지 않은 질문은 answer를 빈 문자열로 작성하세요.
importance는 0부터 100 사이의 정수로 작성하세요.
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