import hmac
import logging
from typing import Any

from flask import Flask, jsonify, request

from config import Config
from services.medical_summarizer import (
    MedicalSummaryError,
    summarize_conversation,
)


def create_app() -> Flask:
    app = Flask(__name__)

    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s %(levelname)s "
            "%(name)s: %(message)s"
        ),
    )

    def is_authorized():
        expected_key = Config.AI_SERVICE_API_KEY

        # 개발 중 키가 비어 있으면 인증 생략
        if not expected_key:
            return True

        received_key = request.headers.get("X-AI-Service-Key", "")

        return hmac.compare_digest(
            received_key.encode("utf-8"),
            expected_key.encode("utf-8")
        )

    @app.get("/health")
    def health():
        return jsonify({
            "success": True,
            "service": "HearO AI Summary",
        })

    @app.post("/api/final-report")
    def final_report():
        if not is_authorized():
            return jsonify({
                "success": False,
                "message": "AI 서버 인증에 실패했습니다.",
            }), 401

        body: dict[str, Any] = (
            request.get_json(silent=True) or {}
        )

        conversation = body.get("conversation")

        if not isinstance(conversation, list):
            return jsonify({
                "success": False,
                "message": (
                    "conversation 필드는 배열이어야 합니다."
                ),
            }), 400

        try:
            report = summarize_conversation(conversation)

            return jsonify({
                "success": True,
                "report": report,
            })

        except MedicalSummaryError as error:
            app.logger.warning(
                "진료 요약 생성 실패: %s",
                error,
            )

            return jsonify({
                "success": False,
                "message": str(error),
            }), 422

        except Exception:
            app.logger.exception(
                "예상하지 못한 요약 서버 오류"
            )

            return jsonify({
                "success": False,
                "message": (
                    "요약 처리 중 서버 오류가 발생했습니다."
                ),
            }), 500

    return app


app = create_app()


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False,
    )