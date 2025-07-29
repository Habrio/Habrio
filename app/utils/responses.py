from flask import jsonify


def ok(data=None, message="success", status=200):
    payload = {"status": "success", "message": message}
    if data is not None:
        payload["data"] = data
    return jsonify(payload), status


def error(message, status=400, code=None):
    return jsonify({
        "status": "error",
        "message": message,
        "code": code or status
    }), status


def error_response(message: str, status_code: int):
    return jsonify({"status": "error", "message": message}), status_code


def internal_error_response():
    return error_response("An unexpected error occurred, please try again later", 500)
