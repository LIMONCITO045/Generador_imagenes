"""
Lanzador de escritorio para la app de Streamlit.
Este archivo es el que se compila con PyInstaller (NO app.py directamente).
Arranca un servidor Streamlit local y abre el navegador apuntando a él.
"""
import os
import sys
import threading
import time
import webbrowser

from streamlit.web import cli as stcli


def resource_path(relative_path):
    """Encuentra archivos empaquetados, funcione en modo normal o ya compilado (.exe)."""
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


def open_browser():
    time.sleep(3)  # da tiempo a que el servidor levante
    webbrowser.open("http://localhost:8501")


if __name__ == "__main__":
    threading.Thread(target=open_browser, daemon=True).start()

    app_path = resource_path("app.py")
    sys.argv = [
        "streamlit",
        "run",
        app_path,
        "--global.developmentMode=false",
        "--server.headless=true",
        "--server.port=8501",
        "--browser.gatherUsageStats=false",
    ]
    sys.exit(stcli.main())
