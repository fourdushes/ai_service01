import hmac
import logging
import os
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
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    def is_authorized() -> bool:
        expected_key = Config.AI_SERVICE_API_KEY

        # 개발환경에서는 API 키가 없으면 인증을 생략합니다.
        if not expected_key:
            return True

        received_key = request.headers.get(
            "X-AI-Service-Key",
            "",
        )

        return hmac.compare_digest(
            received_key,
            expected_key,
        )

    @app.get("/health")
    def health():
        return jsonify({
            "success": True,
            "service": "HearO AI Server",
        }), 200

    @app.post("/api/final-report")
    def final_report():
        if not is_authorized():
            return jsonify({
                "success": False,
                "message": "AI 서버 인증에 실패했습니다.",
            }), 401

        body: dict[str, Any] = request.get_json(silent=True) or {}

        ward_user_id = body.get("wardUserId")
        ward_user_name = body.get("wardUserName")
        archive_id = body.get("archiveId")
        all_chat_text = body.get("allChatText")

        if not isinstance(ward_user_id, str) or not ward_user_id.strip():
            return jsonify({
                "success": False,
                "message": "wardUserId가 필요합니다.",
            }), 400

        if not isinstance(ward_user_name, str) or not ward_user_name.strip():
            return jsonify({
                "success": False,
                "message": "wardUserName이 필요합니다.",
            }), 400

        # Python에서는 bool도 int로 처리되므로 bool은 제외합니다.
        if (
            not isinstance(archive_id, int)
            or isinstance(archive_id, bool)
        ):
            return jsonify({
                "success": False,
                "message": "archiveId는 Long(Integer) 타입이어야 합니다.",
            }), 400

        if not isinstance(all_chat_text, str) or not all_chat_text.strip():
            return jsonify({
                "success": False,
                "message": "allChatText가 필요합니다.",
            }), 400

        ward_user_id = ward_user_id.strip()
        ward_user_name = ward_user_name.strip()
        all_chat_text = all_chat_text.strip()

        try:
            report = summarize_conversation(all_chat_text)

            return jsonify({
                "success": True,
                "wardUserId": ward_user_id,
                "wardUserName": ward_user_name,
                "archiveId": archive_id,
                "allChatText": all_chat_text,
                **report,
            }), 200

        except MedicalSummaryError as error:
            app.logger.warning(
                "진료 요약 실패: %s",
                error,
            )

            return jsonify({
                "success": False,
                "wardUserId": ward_user_id,
                "wardUserName": ward_user_name,
                "archiveId": archive_id,
                "message": str(error),
            }), 422

        except Exception:
            app.logger.exception(
                "예상하지 못한 서버 오류",
            )

            return jsonify({
                "success": False,
                "wardUserId": ward_user_id,
                "wardUserName": ward_user_name,
                "archiveId": archive_id,
                "message": "요약 처리 중 서버 오류가 발생했습니다.",
            }), 500

    return app


app = create_app()


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "5000")),
        debug=False,
    )
