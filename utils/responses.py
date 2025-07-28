from flask import jsonify


def error_response(message: str, status_code: int):
    return jsonify({"status": "error", "message": message}), status_code


def internal_error_response():
    return error_response("An unexpected error occurred, please try again later", 500)

