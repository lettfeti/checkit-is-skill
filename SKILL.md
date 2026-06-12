---
name: checkit-is
description: Register and disable partner and customer accounts on a checkit.is tenant. Use when someone asks to add people, remove or disable people, or check who is registered on a checkit.is site such as your-tenant.checkit.is. The operator signs in with rafraen skilriki in their own browser, and the skill reads the resulting session token. Actions run against a roster allow-list with a dry run first and confirmation before any write.
---

# checkit-is

Manage accounts on a checkit.is tenant through its account API. Built for a partner operator who registers and disables their own group of people (customers).

## Ground rules

1. The roster file is a closed allow-list. Only create or disable people on it. Never touch any other account, including other customers on the same tenant.
2. The operator account is protected. Never disable it.
3. Every write runs as a dry run first. Show the operator the plan and get explicit confirmation before running with `--commit`.
4. Match people by kennitala when possible, and by name otherwise. If a name is ambiguous (more than one match), stop and ask rather than guess.
5. Validate every kennitala before a write. Skip and report any that fail.
6. The session token is a secret. It lives in `.checkit.secrets.json`, which is git-ignored. Never print it in full and never commit it.

## Setup

Run commands from the repo directory with `python3 -m checkit ...`.

1. Copy `roster.example.json` to `roster.json` and fill in the operator's people. `roster.json` is git-ignored.

## Step 1: log in

The operator signs in themselves. The skill does not perform the rafraen skilriki login.

1. Ask the operator to open their tenant, for example `https://your-tenant.checkit.is`, and sign in with rafraen skilriki, approving on their phone.
2. Ask them to open DevTools, go to the Network tab, click any request to `api.checkit.is`, and choose Copy as cURL.
3. Save that into a file and run:

   ```
   python3 -m checkit login --from-curl request.curl
   ```

   Or pipe it: `pbpaste | python3 -m checkit login --from-curl -`

4. Confirm the result shows `role=partner`. If it does not, the token will not be able to manage accounts.

Tokens expire. If a command returns an auth error, repeat this step.

## Step 2: check the current state

```
python3 -m checkit list
```

This is read only. It shows which roster people are present, missing, or ambiguous.

## Step 3: add people

```
python3 -m checkit add            # dry run, shows the plan
python3 -m checkit add --commit   # applies after you confirm
```

Adding a person is two API calls: create the account, then attach a kennitala login. Email and password are not used. The command is idempotent, so it skips anyone already present and re-checks logins.

## Step 4: disable a person

```
python3 -m checkit disable "Full Name"        # dry run
python3 -m checkit disable 010100-2080 --commit
```

Disable takes one name or kennitala that is on the roster. It refuses anyone not on the roster and refuses the operator account. On this platform, disable sets the account status to deleted, which is a soft delete. To bring a person back, add them again.

## Notes for the assistant

- Always run the dry run and report the plan before suggesting `--commit`.
- When the operator asks to remove someone, disable one person at a time and confirm each.
- If `list` shows a roster person as ambiguous, ask the operator which account is correct instead of acting.
