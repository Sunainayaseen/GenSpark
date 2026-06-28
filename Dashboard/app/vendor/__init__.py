from flask import Blueprint
vendor_bp = Blueprint('vendor', __name__, template_folder='../../templates')
from app.vendor import routes
