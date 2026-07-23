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

    @app.get("/health")
    def health():
        return jsonify({
            "success": True,
            "service": "HearO AI Summary",
        })

    @app.post("/api/final-report")
    def final_report():
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
