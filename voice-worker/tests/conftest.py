"""Test bootstrap: provide dummy env so `import worker` succeeds in CI
without a real kin-backend deployment or LiveKit credentials."""
import os

os.environ.setdefault("KIN_BACKEND_URL", "https://backend.example.test")
os.environ.setdefault("FUNCTION_SECRET", "test-function-secret")
os.environ.setdefault("LIVEKIT_URL", "wss://example.livekit.cloud")
os.environ.setdefault("LIVEKIT_API_KEY", "test-livekit-key")
os.environ.setdefault("LIVEKIT_API_SECRET", "test-livekit-secret")
