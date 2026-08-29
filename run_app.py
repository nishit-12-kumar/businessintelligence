"""Entry point runner for BusinessIntelligence.ai Streamlit App.

Imports ssl_patch to ensure OpenSSL compatibility on Windows before starting Streamlit.
"""
import ssl_patch
import sys
import os

from streamlit.web import cli as stcli

if __name__ == '__main__':
    app_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app', 'streamlit_app.py')
    sys.argv = ["streamlit", "run", app_path]
    sys.exit(stcli.main())
