"""Compatibility entry point for Liara configurations that run `python3 main.py`.

The canonical WSGI application is `app:app`; delegate to Gunicorn so the
production server handles requests instead of Flask's development server.
"""
import os


def main() -> None:
    port = os.environ.get("PORT", "8000")
    os.execvp(
        "gunicorn",
        [
            "gunicorn",
            "--bind",
            f"0.0.0.0:{port}",
            "--workers",
            os.environ.get("WEB_CONCURRENCY", "2"),
            "--access-logfile",
            "-",
            "--error-logfile",
            "-",
            "app:app",
        ],
    )


if __name__ == "__main__":
    main()
