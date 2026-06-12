"""Read login credentials from a cURL command copied out of the browser.

The operator signs in with rafraen skilriki in their own browser. The skill
never performs the login. It only reads the session token that the browser
already holds, by parsing a request that the operator copies as cURL from the
DevTools Network tab.
"""

import re


def parse_curl(text):
    """Pull the bearer token, x-api-key, and origin out of a cURL command."""
    bearer = None
    x_api_key = None
    origin = None
    for pattern in (r"-H\s+'([^']*)'", r'-H\s+"([^"]*)"'):
        for match in re.finditer(pattern, text):
            header = match.group(1)
            if ":" not in header:
                continue
            name, _, value = header.partition(":")
            name = name.strip().lower()
            value = value.strip()
            if name == "authorization" and value.lower().startswith("bearer "):
                bearer = value.split(" ", 1)[1]
            elif name == "x-api-key":
                x_api_key = value
            elif name == "origin":
                origin = value
    return {"bearer": bearer, "x_api_key": x_api_key, "app_base": origin}
