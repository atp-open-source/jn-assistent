import os

from leverance.app import create_app

app = create_app()


if __name__ == "__main__":
    app.run(
        host=os.getenv("FLASK_RUN_HOST", "0.0.0.0"),  # noqa: S104 - bind til alle interfaces er bevidst i container
        port=int(os.getenv("FLASK_RUN_PORT", "5000")),
    )
