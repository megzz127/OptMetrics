"""
OptMetrics Flask Application Factory.
Configures CORS, routes, error handling, and database initialization.
"""

import os
from flask import Flask, jsonify, request
from flask_cors import CORS
from .models.database import init_db
from .routes import (
    profile_bp,
    document_bp,
    analyzer_bp,
    history_bp,
    analytics_bp,
    settings_bp
)


def create_app(test_config=None):
    """Create and configure an instance of the Flask application."""
    app = Flask(__name__)

    # Default configuration
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "optmetrics-dev-secret-key-change-in-prod"),
        MAX_CONTENT_LENGTH=15 * 1024 * 1024,  # 15 MB limit
    )

    if test_config:
        app.config.update(test_config)

    # Configure CORS for Vite frontend and Chrome extension
    CORS(app, resources={
        r"/api/*": {
            "origins": [
                "http://localhost:5173",
                "http://127.0.0.1:5173",
                "http://localhost:3000",
                "http://127.0.0.1:3000",
                "chrome-extension://*"
            ],
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"]
        }
    })

    # Initialize SQLite database tables
    with app.app_context():
        init_db()

    # Health check endpoint
    @app.route("/api/health", methods=["GET"])
    def health_check():
        return jsonify({
            "status": "healthy",
            "service": "OptMetrics API",
            "version": "1.0.0"
        }), 200

    # Register blueprints
    app.register_blueprint(profile_bp)
    app.register_blueprint(document_bp)
    app.register_blueprint(analyzer_bp)
    app.register_blueprint(history_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(settings_bp)

    # Standard error handlers
    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"error": "Bad request", "message": str(e)}), 400

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Resource not found"}), 404

    @app.errorhandler(413)
    def request_entity_too_large(e):
        return jsonify({"error": "File size exceeds server limit (15MB)"}), 413

    @app.errorhandler(500)
    def internal_server_error(e):
        return jsonify({"error": "Internal server error"}), 500

    return app
