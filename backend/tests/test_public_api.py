"""Regression test for the public_api.py bad-import bug: get_capabilities
used `import notifications as _notify` (a bare top-level import that only
resolves if plugins/ itself is on sys.path, which it isn't at app startup),
so GET /api/capabilities raised ModuleNotFoundError on every call. Fixed to
`from plugins import notifications as _notify`, matching every other call
site in this codebase."""
import main
from fastapi.testclient import TestClient

from app.core.deps import require_user


def test_capabilities_endpoint_does_not_raise_module_not_found_error():
    main.app.dependency_overrides[require_user] = lambda: {
        "id": "test-user-id",
        "auth_user_id": "test-auth-user-id",
    }
    try:
        client = TestClient(main.app)
        r = client.get("/api/capabilities")
        assert r.status_code == 200
        assert "onesignal_configured" in r.json()
        assert isinstance(r.json()["onesignal_configured"], bool)
    finally:
        main.app.dependency_overrides.pop(require_user, None)
