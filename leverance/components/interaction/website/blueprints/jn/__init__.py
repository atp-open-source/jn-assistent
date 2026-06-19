from flask import Blueprint

interaction_bp = Blueprint("jn_website", __name__)

from leverance.interaction import jn_website_interaction_component  # noqa: E402,F401
