"""Wait for API migrations and the OAuth provider, without exposing configuration."""

import http.client
import time
import urllib.error
import urllib.request

URLS = (
    "http://localhost:8080/api/health",
    "http://localhost:8080/auth/realms/family/.well-known/openid-configuration",
)


def wait_for_app(
    timeout=240,
    *,
    open_url=urllib.request.urlopen,
    now=time.monotonic,
    sleep=time.sleep,
):
    deadline = now() + timeout
    while now() < deadline:
        try:
            for url in URLS:
                with open_url(url, timeout=3) as response:
                    if response.status != 200:
                        raise urllib.error.URLError("not ready")
            return True
        except (OSError, http.client.HTTPException):
            # Includes URL errors, timeouts, resets and incomplete HTTP startup responses.
            sleep(min(2, max(0, deadline - now())))
    return False


def main():
    if not wait_for_app():
        raise SystemExit("Application did not start in 240 seconds. Check: docker compose logs")
    print("API and OAuth provider ready: http://localhost:8080")


if __name__ == "__main__":
    main()
