import os
import sys
import tempfile
from pathlib import Path

os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="livechat_test_")
os.environ["BLOG_URL"] = "https://bdjobsinfo.com"
os.environ["GEMINI_API_KEY"] = "test"
os.environ["ADMIN_TOKEN"] = "secret"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
