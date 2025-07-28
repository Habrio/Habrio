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
