"""
CodePulse Flask Application Entry Point
Real-Time Developer Intelligence Platform
"""

import os
import sys
import logging
from flask import Flask, render_template

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.database import init_db
from backend.routes.api import api

# Configure paths
TEMPLATE_FOLDER = os.path.join(PROJECT_ROOT, 'frontend', 'templates')
STATIC_FOLDER = os.path.join(PROJECT_ROOT, 'frontend', 'static')

# Create Flask application
app = Flask(__name__, template_folder=TEMPLATE_FOLDER, static_folder=STATIC_FOLDER)

# Enable CORS (allow all origins)
try:
    from flask_cors import CORS
    CORS(app, resources={r"/*": {"origins": "*"}})
except ImportError:
    @app.after_request
    def enable_cors(response):
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-Requested-With'
        return response

# Register Blueprint
app.register_blueprint(api, url_prefix='/api')


@app.route('/')
def index():
    """Main route serving frontend index.html"""
    return render_template('index.html')


@app.route('/health')
def root_health():
    """Top-level health check shortcut"""
    from flask import jsonify
    from datetime import datetime
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()}), 200


def create_app():
    """Factory helper to initialize DB and return configured app"""
    init_db()
    return app


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    init_db()
    print("""
    ============================================================
      CODEPULSE BACKEND SERVER
      Developer Intelligence Platform

      Web UI:   http://localhost:5000/
      REST API: http://localhost:5000/api/health

      Press Ctrl+C to stop
    ============================================================
    """)
    app.run(host='0.0.0.0', port=5000, debug=True)
