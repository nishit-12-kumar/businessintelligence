"""Entry point runner for BusinessIntelligence.ai Flask Web Application.

Applies Windows SSL compatibility patches and starts the Flask WSGI development server.

To enable Werkzeug debug mode locally:
    set FLASK_DEBUG=1 && python run_app.py
Never run with debug=True in any environment reachable from outside localhost.
"""
import ssl_patch  # noqa: F401  — must be first import (patches ssl on Windows)
import sys
import os

from app import create_app

if __name__ == '__main__':
    app = create_app()
    port = int(os.environ.get('PORT', 5000))
    # Bug #2 fix: default to debug=False; require explicit opt-in via FLASK_DEBUG=1
    debug = os.environ.get('FLASK_DEBUG', '0') == '1'
    print(f"\n>>> BusinessIntelligence.ai running at http://127.0.0.1:{port}")
    if debug:
        print("[WARNING] Debug mode ON - do not expose this port outside localhost!")
    print()
    app.run(host='127.0.0.1', port=port, debug=debug)
