"""HTTP client for the checkit.is account API."""

import base64
import json
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_API_BASE = "https://api.checkit.is"


def decode_jwt(token):
    """Return the JWT payload as a dict, or an empty dict if it cannot be read."""
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload))
    except Exception:
        return {}


class CheckitError(Exception):
    pass


class CheckitClient:
    def __init__(self, bearer, x_api_key="", api_base=DEFAULT_API_BASE, app_base=None):
        self.bearer = bearer
        self.x_api_key = x_api_key
        self.api_base = (api_base or DEFAULT_API_BASE).rstrip("/")
        self.app_base = (app_base or "").rstrip("/")

    def _request(self, path, method="GET", payload=None):
        url = self.api_base + path
        data = None
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("accept", "application/json, text/plain, */*")
        req.add_header("authorization", "Bearer " + self.bearer)
        if self.x_api_key:
            req.add_header("x-api-key", self.x_api_key)
        if self.app_base:
            req.add_header("origin", self.app_base)
            req.add_header("referer", self.app_base + "/")
        if payload is not None:
            req.add_header("content-type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read().decode()
                return json.loads(body) if body else {}
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode()[:300]
            raise CheckitError(f"HTTP {exc.code} on {method} {path}: {detail}") from None

    def get(self, path):
        return self._request(path, "GET")

    def post(self, path, payload):
        return self._request(path, "POST", payload)

    def put(self, path, payload):
        return self._request(path, "PUT", payload)

    def whoami(self):
        return decode_jwt(self.bearer)

    def fetch_accounts(self, status="active"):
        """Return all accounts, following the cursor across pages."""
        accounts, seen, cursor, pages = [], set(), None, 0
        base = "/accounts?include=customer" + (f"&status={status}" if status else "")
        while True:
            path = base + (f"&cursor={urllib.parse.quote(cursor)}" if cursor else "")
            page = self.get(path)
            fresh = [a for a in page.get("data", []) if a.get("id") not in seen]
            for a in fresh:
                seen.add(a["id"])
            accounts.extend(fresh)
            pages += 1
            cursor = page.get("next")
            if not cursor or not fresh or pages > 200:
                break
        return accounts

    def get_account(self, account_id):
        return self.get(f"/accounts/{account_id}?include=customer")

    def get_logins(self, account_id):
        try:
            return self.get(f"/accounts/{account_id}/logins")
        except CheckitError:
            return []

    def create_account(self, name, role="customer"):
        """Step one of account creation. Returns the new account id."""
        result = self.post(
            "/accounts",
            {"account": {"name": name, "role": role, "status": "active"}, "customer": None},
        )
        return result.get("id")

    def attach_login(self, account_id, kennitala):
        """Step two of account creation. Adds an electronic-ID login."""
        return self.post(
            f"/accounts/{account_id}/logins",
            {"accountId": account_id, "ssn": kennitala},
        )

    def disable_account(self, account):
        """Deactivate an account. The platform marks it deleted."""
        body = dict(account)
        body["status"] = "deleted"
        body["customerId"] = "remove"
        return self.put(f"/accounts/{account['id']}", body)
