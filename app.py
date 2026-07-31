import sys
import os

# Ensure hacktrack module directory is on sys.path
hacktrack_dir = os.path.join(os.path.dirname(__file__), 'hacktrack')
if hacktrack_dir not in sys.path:
    sys.path.insert(0, hacktrack_dir)

from app import app

if __name__ == "__main__":
    app.run()
