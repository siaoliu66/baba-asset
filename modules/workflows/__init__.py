from flask import Blueprint

workflows_bp = Blueprint('workflows', __name__)

from . import routes
