# === /agent/query_handler.py ===
from flask import request, jsonify
from agent.agent_core import run_agent

def ask_agent_handler():
    user_query = request.json.get("query")
    if not user_query:
        return jsonify({"status": "error", "message": "Query is required"}), 400

    user_info = {
        "phone": getattr(request, "phone", None),
        "user_role": getattr(request, "user_role", None),
    }

    try:
        answer, suggestions = run_agent(user_query, user_info)
        return jsonify({"status": "success", "answer": answer, "suggestions": suggestions})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
