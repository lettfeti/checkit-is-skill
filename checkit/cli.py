"""Command line interface for managing checkit.is accounts."""

import argparse
import json
import sys
from pathlib import Path

from .capture import parse_curl
from .client import CheckitClient, CheckitError, DEFAULT_API_BASE, decode_jwt
from .kennitala import normalize as kennitala_normalize
from .kennitala import validate as kennitala_validate
from .roster import index_by_name, load_roster, normalize_name

SECRETS_DEFAULT = ".checkit.secrets.json"
ROSTER_DEFAULT = "roster.json"


def load_secrets(path):
    secrets_path = Path(path)
    if not secrets_path.exists():
        sys.exit(f"No credentials at {path}. Run 'checkit login' first.")
    return json.loads(secrets_path.read_text())


def make_client(args):
    secrets = load_secrets(args.secrets)
    return CheckitClient(
        secrets["bearer"],
        secrets.get("x_api_key", ""),
        secrets.get("api_base", DEFAULT_API_BASE),
        secrets.get("app_base"),
    )


def cmd_login(args):
    if args.from_curl is not None:
        text = sys.stdin.read() if args.from_curl == "-" else Path(args.from_curl).read_text()
        info = parse_curl(text)
        if not info["bearer"]:
            sys.exit("No Bearer token found in that cURL command.")
    elif args.token:
        info = {"bearer": args.token, "x_api_key": args.x_api_key, "app_base": args.app_base}
    else:
        sys.exit("Pass --from-curl FILE (or - for stdin) or --token TOKEN.")

    secrets = {
        "api_base": args.api_base,
        "app_base": info.get("app_base") or args.app_base,
        "bearer": info["bearer"],
        "x_api_key": info.get("x_api_key") or args.x_api_key or "",
    }
    Path(args.secrets).write_text(json.dumps(secrets, indent=2) + "\n")
    claims = decode_jwt(info["bearer"])
    print(f"Saved credentials to {args.secrets}")
    print(f"role={claims.get('role')} accountId={claims.get('accountId')} customer={claims.get('customer')}")
    if claims.get("role") != "partner":
        print("Warning: this token is not a partner token. Some actions may be refused by the API.")


def cmd_whoami(args):
    print(json.dumps(make_client(args).whoami(), indent=2))


def cmd_list(args):
    client = make_client(args)
    people = load_roster(args.roster)
    accounts = client.fetch_accounts("active")
    index = index_by_name(accounts)
    print(f"{len(accounts)} active accounts. Roster has {len(people)} people.\n")
    present = missing = 0
    for person in people:
        ok, message = kennitala_validate(person["kennitala"])
        flag = "" if ok else f"  [bad kennitala: {message}]"
        matches = index.get(normalize_name(person["name"]), [])
        if not matches:
            missing += 1
            print(f"  missing    {person['name']}{flag}")
        elif len(matches) > 1:
            print(f"  ambiguous  {person['name']} ({len(matches)} matches){flag}")
        else:
            present += 1
            print(f"  present    {person['name']} ({matches[0]['status']}){flag}")
    print(f"\n{present} present, {missing} missing.")


def _plan_add(client, people):
    accounts = client.fetch_accounts("active")
    index = index_by_name(accounts)
    plan = []
    for person in people:
        ok, message = kennitala_validate(person["kennitala"])
        if not ok:
            plan.append(("blocked", person, message))
            continue
        matches = index.get(normalize_name(person["name"]), [])
        if len(matches) > 1:
            plan.append(("ambiguous", person, None))
        elif len(matches) == 1:
            account = matches[0]
            has_login = any(
                login.get("ssn") == person["kennitala"]
                for login in client.get_logins(account["id"])
            )
            plan.append(("present" if has_login else "attach", person, account))
        else:
            plan.append(("create", person, None))
    return plan


def cmd_add(args):
    client = make_client(args)
    people = load_roster(args.roster)
    plan = _plan_add(client, people)

    for action, person, _ in plan:
        print(f"  {action:<10} {person['name']}")
    counts = {key: sum(action == key for action, _, _ in plan) for key in
              ("create", "attach", "present", "blocked", "ambiguous")}
    print(
        f"\n{counts['create']} to create, {counts['attach']} to attach a login, "
        f"{counts['present']} already complete, "
        f"{counts['blocked'] + counts['ambiguous']} skipped."
    )

    todo = [item for item in plan if item[0] in ("create", "attach")]
    if not args.commit:
        print("\nDry run. Re-run with --commit to apply.")
        return
    if not todo:
        print("\nNothing to do.")
        return

    print("\nApplying:")
    for action, person, account in todo:
        try:
            if action == "create":
                account_id = client.create_account(person["name"])
                client.attach_login(account_id, person["kennitala"])
            else:
                account_id = account["id"]
                client.attach_login(account_id, person["kennitala"])
            attached = any(
                login.get("ssn") == person["kennitala"]
                for login in client.get_logins(account_id)
            )
            print(f"  {'ok  ' if attached else 'FAIL'} {person['name']} ({account_id})")
        except CheckitError as exc:
            print(f"  FAIL {person['name']}: {exc}")


def cmd_disable(args):
    client = make_client(args)
    people = load_roster(args.roster)
    roster_names = {normalize_name(p["name"]) for p in people}

    target_digits = kennitala_normalize(args.who)
    if len(target_digits) == 10:
        person = next((p for p in people if p["kennitala"] == target_digits), None)
        if not person:
            sys.exit("Refusing: that kennitala is not on the roster.")
        target_name = normalize_name(person["name"])
    else:
        target_name = normalize_name(args.who)
        if target_name not in roster_names:
            sys.exit("Refusing: that name is not on the roster.")

    accounts = client.fetch_accounts("active")
    matches = index_by_name(accounts).get(target_name, [])
    operator_id = client.whoami().get("accountId")

    if not matches:
        sys.exit("No active account with that name.")
    if any(m["id"] == operator_id for m in matches):
        sys.exit("Refusing: that is the operator account.")
    if len(matches) > 1:
        sys.exit(f"Refusing: {len(matches)} active accounts share that name. Disable by hand to avoid a mistake.")

    account = matches[0]
    print(f"Target: {account['name']} ({account['id']}) status={account['status']}")
    if not args.commit:
        print("Dry run. Re-run with --commit to disable. This sets status=deleted on the platform.")
        return
    detail = client.get_account(account["id"])
    client.disable_account(detail)
    print(f"Disabled {account['name']} ({account['id']}).")


def build_parser():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--secrets", default=SECRETS_DEFAULT, help="path to the credentials file")
    common.add_argument("--roster", default=ROSTER_DEFAULT, help="path to the roster file")

    parser = argparse.ArgumentParser(prog="checkit", description="Manage checkit.is partner and customer accounts.")
    sub = parser.add_subparsers(dest="command", required=True)

    login = sub.add_parser("login", parents=[common], help="store a session token read from the browser")
    login.add_argument("--from-curl", help="file with a copied cURL command, or - for stdin")
    login.add_argument("--token", help="paste a bearer token directly")
    login.add_argument("--x-api-key", help="x-api-key header value")
    login.add_argument("--app-base", help="tenant URL, for example https://your-tenant.checkit.is")
    login.add_argument("--api-base", default=DEFAULT_API_BASE)
    login.set_defaults(func=cmd_login)

    sub.add_parser("whoami", parents=[common], help="show who the stored token belongs to").set_defaults(func=cmd_whoami)
    sub.add_parser("list", parents=[common], help="compare the roster against the tenant").set_defaults(func=cmd_list)

    add = sub.add_parser("add", parents=[common], help="create roster people who are missing")
    add.add_argument("--commit", action="store_true", help="apply changes instead of a dry run")
    add.set_defaults(func=cmd_add)

    disable = sub.add_parser("disable", parents=[common], help="disable one roster person by name or kennitala")
    disable.add_argument("who", help="name or kennitala of a person on the roster")
    disable.add_argument("--commit", action="store_true", help="apply the change instead of a dry run")
    disable.set_defaults(func=cmd_disable)

    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
