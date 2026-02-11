import requests
from typing import Any, Dict, Optional


def proxy_api_request(
    base_url: str,
    api_path: str,
    method: str = "GET",
    body: Optional[Dict[str, Any]] = None,
    query: Optional[Dict[str, Any]] = None,
    authorization: Optional[str] = None,
    timeout: int = 30,
) -> requests.Response:
    if not base_url:
        raise ValueError("PROXY_API_URL must be set")

    url = base_url.rstrip("/") + api_path
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if authorization:
        headers["Authorization"] = authorization

    return requests.request(
        method=method.upper(),
        url=url,
        headers=headers,
        params=query,
        json=body if body else None,
        timeout=timeout,
    )
