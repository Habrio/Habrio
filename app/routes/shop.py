from flask import Blueprint
from app.version import API_PREFIX

shop_bp = Blueprint("shop", __name__, url_prefix=API_PREFIX)
