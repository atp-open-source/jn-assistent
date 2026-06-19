import logging
import os
from uuid import uuid4

from flask import Flask, jsonify, request

try:
    from flask_cors import CORS
except ModuleNotFoundError:  # pragma: no cover - local bootstrap fallback
    def CORS(app, *args, **kwargs):
        return app

try:
    from spark_core.config.base_config import Config
except ModuleNotFoundError:  # pragma: no cover - fallback if shim path changes
    try:
        from spark_core.config import Config  # type: ignore[attr-defined]
    except (ImportError, ModuleNotFoundError):
        from spark_core.config.base_config import Config  # type: ignore[no-redef]


DEFAULT_FRONTEND_ORIGIN = "http://localhost:5173"
DEFAULT_WEBSITE_PREFIX = "/website"


def _build_spark_config() -> Config:
    config_name = os.getenv("ENVIRONMENT") or os.getenv("NAME") or "local"

    try:
        return Config(config_name)
    except TypeError:
        try:
            return Config(name=config_name)
        except TypeError:
            config = Config()
            if not getattr(config, "NAME", None):
                config.NAME = config_name
            return config


def create_app() -> Flask:
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=os.getenv("LOG_LEVEL", "INFO").upper(),
            format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        )

    app = Flask(__name__)
    app.logger.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())

    spark_config = _build_spark_config()
    app.config["SPARK_config"] = spark_config
    app.config["SPARK_CONFIG"] = spark_config
    app.config["JN_INTERACTION_READ_AD"] = os.getenv("JN_INTERACTION_READ_AD", "")
    app.config["JN_INTERACTION_TITLE"] = os.getenv("JN_INTERACTION_TITLE", "JN-assistent")
    app.config["JN_NOTATER_READ_AD"] = os.getenv("JN_NOTATER_READ_AD", "")

    frontend_origin = (
        os.getenv("FRONTEND_ORIGIN")
        or os.getenv("FE_ORIGIN")
        or os.getenv("VITE_FRONTEND_ORIGIN")
        or os.getenv("VITE_FE_ORIGIN")
        or DEFAULT_FRONTEND_ORIGIN
    )
    CORS(app, resources={r"/api/*": {"origins": [frontend_origin]}})

    @app.before_request
    def attach_request_uid() -> None:
        request.uid = uuid4()

    @app.get("/healthz")
    def healthz() -> tuple[object, int]:
        return jsonify(status="ok"), 200

    with app.app_context():
        from leverance.components.interaction.webservice.blueprints.jn import bp
        from leverance.components.interaction.website.blueprints.jn import interaction_bp

    app.register_blueprint(bp, url_prefix="/api/jn")
    app.register_blueprint(bp, name="jn_interaction_legacy")
    app.register_blueprint(
        interaction_bp,
        url_prefix=os.getenv("JN_WEBSITE_URL_PREFIX", DEFAULT_WEBSITE_PREFIX),
    )

    app.logger.info("JN Flask app initialised")
    return app
