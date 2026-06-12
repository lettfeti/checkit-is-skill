# checkit-is-skill

A small command line tool and Claude skill for managing accounts on a checkit.is tenant. It registers people, disables them, and reports who is on the system. It is meant for a partner operator who looks after their own group of people.

The tool uses only the Python standard library. The operator signs in with rafraen skilriki in their own browser, and the tool reads the session token from a request the operator copies out of the browser. The tool does not handle the login itself and does not store a password.

## What it does

- `login` reads a session token from a cURL command copied out of the browser.
- `whoami` shows who the stored token belongs to.
- `list` compares your roster against the tenant. Read only.
- `add` creates the people on your roster who are missing, and attaches a kennitala login to each.
- `disable` deactivates one person from your roster by name or kennitala.

## Safety model

- The roster file is a closed allow-list. The tool only creates or disables people listed in it. It never touches any other account.
- The operator account is protected and cannot be disabled by the tool.
- Writes are a dry run by default. You pass `--commit` to apply them.
- Kennitala numbers are checked against their checksum before any write.
- People are matched by kennitala when possible. A name with more than one match is reported and skipped rather than guessed.
- Credentials live in `.checkit.secrets.json`, which is git-ignored. Your roster lives in `roster.json`, which is also git-ignored. Neither belongs in the repository.

## Requirements

Python 3.8 or newer. No third-party packages.

## Setup

```
git clone <your-fork-url>
cd checkit-is-skill
cp roster.example.json roster.json
```

Edit `roster.json` and add your people. Each entry needs a name and a kennitala. Email is optional and is not sent to the API.

## Logging in

The operator signs in. The tool only reads the token afterwards.

1. Open your tenant, for example `https://your-tenant.checkit.is`, and sign in with rafraen skilriki. Approve the request on your phone.
2. Open DevTools, go to the Network tab, click any request to `api.checkit.is`, and choose Copy as cURL.
3. Save it to a file and load it:

```
python3 -m checkit login --from-curl request.curl
```

On macOS you can pipe straight from the clipboard:

```
pbpaste | python3 -m checkit login --from-curl -
```

The output shows the role, account id, and customer for the token. For account management the role needs to be `partner`. Tokens expire, so repeat this step when a command reports an auth error.

## Usage

Check the current state. This makes no changes.

```
python3 -m checkit list
```

Add the missing people. The first run is a dry run that prints the plan. The second run applies it.

```
python3 -m checkit add
python3 -m checkit add --commit
```

Disable one person. Pass a name or a kennitala that is on your roster.

```
python3 -m checkit disable "Full Name"
python3 -m checkit disable 010100-2080 --commit
```

## How registration works

Creating a person is two API calls in order:

1. `POST /accounts` with `{"account": {"name": NAME, "role": "customer", "status": "active"}, "customer": null}`. The response returns the new account id.
2. `POST /accounts/{id}/logins` with `{"accountId": id, "ssn": KENNITALA}`. This attaches an electronic-ID login.

The account list at `GET /accounts?include=customer` does not return each person's kennitala, so the tool matches people by name there and reads logins from `GET /accounts/{id}/logins` to confirm. Authentication uses a bearer token plus an `x-api-key` header, both read from the browser during login.

Disabling a person is a `PUT /accounts/{id}` that sets `status` to `deleted`. The platform treats this as a soft delete. To restore someone, add them again.

## Using it as a Claude skill

`SKILL.md` describes the workflow for an assistant: log in, check state, add with a dry run and confirmation, and disable one person at a time within the allow-list. Point your assistant at this directory, or copy it into your skills folder.

## Tenant configuration

The API base is `https://api.checkit.is`. The tenant URL, such as `https://your-tenant.checkit.is`, is stored with the token during login and sent as the origin. Other tenants work by logging in against their own URL.

## License

MIT. See `LICENSE`.
