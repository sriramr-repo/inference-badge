"""Vercel ASGI adapter for the existing Streamlit application.

The product source remains in ``app.py``.  This module only exposes
Streamlit's built-in Starlette server as the ASGI entrypoint Vercel expects.
"""

from pathlib import Path

from streamlit.web.server.server import Server
from streamlit.web.server.starlette import create_starlette_app


_APP_SCRIPT = str(Path(__file__).resolve().parents[1] / "app.py")
_STREAMLIT_SERVER = Server(main_script_path=_APP_SCRIPT, is_hello=False)

# Vercel detects this ASGI application and routes the deployment through the
# same Streamlit server used by `streamlit run app.py`.
app = create_starlette_app(_STREAMLIT_SERVER._runtime)
