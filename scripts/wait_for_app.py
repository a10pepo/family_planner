"""Wait for API migrations and the OAuth provider, without exposing configuration."""

import time
import urllib.error
import urllib.request

urls = [
    "http://localhost:8080/api/health",
    "http://localhost:8080/auth/realms/family/.well-known/openid-configuration",
]
deadline = time.monotonic() + 240
while time.monotonic() < deadline:
    try:
        for url in urls:
            with urllib.request.urlopen(url, timeout=3) as response:
                if response.status != 200:
                    raise urllib.error.URLError("not ready")
        print("API and OAuth provider ready: http://localhost:8080")
        break
    except (urllib.error.URLError, TimeoutError):
        time.sleep(2)
else:
    raise SystemExit("Application did not start in 240 seconds. Check: docker compose logs")
