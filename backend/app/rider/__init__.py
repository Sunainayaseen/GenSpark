from flask import Blueprint
rider_bp = Blueprint('rider', __name__, template_folder='../../templates')
from app.rider import routes  # noqa: E402,F401
