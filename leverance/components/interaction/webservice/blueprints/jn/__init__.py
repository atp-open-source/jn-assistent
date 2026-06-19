from flask import Blueprint

bp = Blueprint("jn_interaction", __name__)

from leverance.interaction import jn_interaction_component  # noqa: E402,F401
