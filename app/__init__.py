from flask import Flask

from app.db import init_db
from app.routes import register_routes


def create_app():
    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static",
    )

    init_db()
    register_routes(app)

    return app