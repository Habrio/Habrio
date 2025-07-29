from flask import Blueprint, request, jsonify
from app.utils import auth_required
from app.version import API_PREFIX
from agent.agent_core import run_agent

# Optional blueprint for AI assistant
agent_bp = Blueprint('agent', __name__, url_prefix=f'{API_PREFIX}/agent')

@agent_bp.route('/query', methods=['POST'])
@auth_required
def agent_query():
    """Handle AI assistant queries."""
    user_query = request.json.get('query') if request.is_json else None
    if not user_query:
        return jsonify({'status': 'error', 'message': 'Query is required'}), 400

    user_info = {
        'phone': getattr(request, 'phone', None),
        'user_role': getattr(request, 'user_role', None),
    }
    try:
        answer, suggestions = run_agent(user_query, user_info)
        return jsonify({'status': 'success', 'answer': answer, 'suggestions': suggestions})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
