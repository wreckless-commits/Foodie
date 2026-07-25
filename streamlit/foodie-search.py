import os
import sys
root = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, root)                      # .../Foodie
sys.path.insert(0, os.path.join(root, "Data")) # .../Foodie/Data
from streamlit.web import cli
if __name__ == "__main__":
    port = os.environ.get("PORT", "8000")
    sys.argv = ["streamlit", "run", os.path.join(os.path.dirname(__file__), "app.py"),
                "--server.port", port, "--server.headless", "true"]
    cli.main()