import sys
import os
from unittest.mock import MagicMock

# 1. Mock pgvector
print("Mocking pgvector...")
sys.modules["pgvector"] = MagicMock()
sys.modules["pgvector.sqlalchemy"] = MagicMock()

# 2. Add path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

# 3. Try import
try:
    print("Importing app.models...")
    from app.models import Notice, ServiceProfile
    print("Success!")
except Exception as e:
    print(f"Failed: {e}")
    import traceback
    traceback.print_exc()
