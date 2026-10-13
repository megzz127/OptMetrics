"""
OptMetrics Backend Server Entry Point.
"""

import os
from app import create_app

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    host = os.environ.get("HOST", "127.0.0.1")
    debug = os.environ.get("FLASK_DEBUG", "True").lower() in ("true", "1")

    print(f"🚀 Starting OptMetrics API server on http://{host}:{port}")
    app.run(host=host, port=port, debug=debug)
