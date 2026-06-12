"""Roster loading and name matching.

The roster is a closed allow-list. The tool only ever creates or disables
people who appear in it.
"""

import json
import unicodedata

from .kennitala import normalize as normalize_kennitala


def normalize_name(name):
    text = unicodedata.normalize("NFC", (name or "").strip())
    return " ".join(text.split()).casefold()


def load_roster(path):
    """Read a roster file into a list of {name, kennitala, email}."""
    data = json.loads(open(path, encoding="utf-8").read())
    people = []
    for entry in data.get("customers", []):
        people.append(
            {
                "name": entry["name"].strip(),
                "kennitala": normalize_kennitala(entry.get("kennitala", "")),
                "email": entry.get("email"),
            }
        )
    return people


def index_by_name(accounts):
    """Group accounts by normalized name for duplicate-safe lookups."""
    index = {}
    for account in accounts:
        index.setdefault(normalize_name(account.get("name")), []).append(account)
    return index
