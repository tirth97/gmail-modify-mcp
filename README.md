# gmail-modify-mcp

A tiny self-hosted **Model Context Protocol** server that adds **one** tool to Claude Code / Cowork:

```
gmail_modify_labels(message_id, add_label_ids?, remove_label_ids?)
```

Why it exists: Anthropic's hosted Gmail MCP connector at `gmail.mcp.claude.com` supports reads and draft creation but **cannot modify message labels**, which blocks every inbox-management workflow — archive, mark read/unread, star, trash, categorize. Tracked upstream in [anthropics/claude-code#36547](https://github.com/anthropics/claude-code/issues/36547).

Run this server **alongside** the hosted connector. The hosted one handles all the read tools, this one handles label mutations.

## What it can do

| Action              | Call                                  |
| ------------------- | ------------------------------------- |
| Archive             | `remove_label_ids=["INBOX"]`          |
| Mark as read        | `remove_label_ids=["UNREAD"]`         |
| Mark as unread      | `add_label_ids=["UNREAD"]`            |
| Star                | `add_label_ids=["STARRED"]`           |
| Move to trash       | `add_label_ids=["TRASH"]`             |
| Apply custom label  | `add_label_ids=["Label_1234567890"]`  |

Permanent delete is intentionally **not** supported — the OAuth scope used (`gmail.modify`) does not grant it.

## Quick start (the entire flow is two commands)

After cloning and a one-time Google Cloud setup (below), the day-to-day surface is:

```bash
gmail-modify-mcp auth     # one-time browser consent → caches token.json
gmail-modify-mcp          # runs the MCP server on stdio (what Claude Code launches)
```

That's it.

### CLI reference

```
gmail-modify-mcp           run the MCP server on stdio (default; no subcommand needed)
gmail-modify-mcp serve     same as above, explicit
gmail-modify-mcp auth      run the OAuth consent flow once
gmail-modify-mcp status    print the authenticated account profile (sanity check)
```

## Install

```bash
git clone https://github.com/tirth97/gmail-modify-mcp.git
cd gmail-modify-mcp
python -m venv .venv
# Windows
.\.venv\Scripts\python.exe -m pip install -e .
# macOS / Linux
./.venv/bin/python -m pip install -e .
```

After `pip install -e .`, the `gmail-modify-mcp` entry-point script is on your venv's PATH (`.venv\Scripts\gmail-modify-mcp.exe` on Windows, `.venv/bin/gmail-modify-mcp` elsewhere).

## One-time Google Cloud setup

These steps you do yourself in a browser. They are *not* automated, by design — the server should never create cloud resources or accounts on your behalf.

1. Open <https://console.cloud.google.com/> and create (or pick) a project.
2. **APIs & Services → Library → Gmail API → Enable.**
3. **APIs & Services → OAuth consent screen** → External. Add your own Gmail address as a **Test user**.
4. **APIs & Services → Credentials → Create credentials → OAuth client ID → Desktop app.**
5. Download the JSON. Save it at the project root as `credentials.json`. (Already gitignored.)
6. Run the consent flow:

   ```bash
   gmail-modify-mcp auth
   ```

   A browser window opens, you grant the `gmail.modify` scope, and `token.json` is written next to `credentials.json`. Future runs are silent and refresh the token automatically.

7. Sanity check:

   ```bash
   gmail-modify-mcp status
   # Authorized as : you@gmail.com
   # Messages total: 1341
   # Threads total : 930
   ```

## Wire it into Claude Code

### Option A — project-scoped `.mcp.json`

A `.mcp.json` file is included in the repo. Launch Claude Code from this directory and it auto-discovers the server. Works without any global config.

### Option B — globally with `claude mcp add`

```bash
claude mcp add gmail-modify-mcp -- gmail-modify-mcp
```

(Yes, that's the literal command — once `pip install -e .` has put `gmail-modify-mcp` on your venv PATH, Claude Code launches it as a subprocess on stdio.)

If you want it available outside the venv, point `claude mcp add` at the absolute path of the entry-point script, e.g.:

```bash
claude mcp add gmail-modify-mcp -- "C:\Users\you\gmail-modify-mcp\.venv\Scripts\gmail-modify-mcp.exe"
```

## Try it

In a Claude Code session that has both this server **and** Anthropic's hosted Gmail connector enabled:

> Find the most recent unread newsletter in my inbox and archive it.

Expected behavior: the model uses `gmail_search_messages` (hosted) to find a candidate → calls `gmail_modify_labels` (this server) with `remove_label_ids=["INBOX"]` → the message disappears from your inbox.

## File layout

```
gmail-modify-mcp/
├── .mcp.json                 Claude Code project-scoped server registration
├── .gitignore                excludes credentials.json, token.json, .venv
├── LICENSE                   MIT
├── pyproject.toml            package metadata + gmail-modify-mcp entry point
├── README.md
├── credentials.json          (you provide; gitignored)
├── token.json                (auto-created on first auth; gitignored)
└── gmail_mcp_server/
    ├── __init__.py
    ├── auth.py               OAuth desktop flow + token refresh
    └── server.py             FastMCP server, gmail_modify_labels tool, CLI
```

## Environment variables

| Variable                | Default                       | Purpose                              |
| ----------------------- | ----------------------------- | ------------------------------------ |
| `GMAIL_MCP_CREDENTIALS` | `<project>/credentials.json`  | Override OAuth client secrets path.  |
| `GMAIL_MCP_TOKEN`       | `<project>/token.json`        | Override cached token path.          |

Useful if you want to keep secrets in `%APPDATA%` / `~/.config` instead of the project root.

## Security notes

- The OAuth scope used is `https://www.googleapis.com/auth/gmail.modify`. This grants read + label modification but **not** permanent delete. That's intentional.
- `credentials.json` and `token.json` are in `.gitignore`. Don't `git add -f` them.
- Move-to-trash is supported via `add_label_ids=["TRASH"]`. The `TRASH` label is reversible — the message stays in Trash for 30 days before Google purges it.
- This server only exposes one tool. It cannot read messages, send mail, or change account settings.

## Troubleshooting

| Symptom                                                                | Fix                                                                                     |
| ---------------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| `OAuth client secrets not found`                                       | `credentials.json` is missing. Re-do the Google Cloud setup step 1–5.                   |
| `Error 403: access_denied` in the consent browser                      | Add your email as a **Test user** under OAuth consent screen, then retry.               |
| Top-level key in `credentials.json` is `"web"` instead of `"installed"`| You created a Web OAuth client. Make a **Desktop app** client instead and re-download. |
| `invalid_grant` / scope errors                                         | Delete `token.json` and re-run `gmail-modify-mcp auth`.                                 |
| `HttpError 403: Insufficient Permission` from `modify`                 | Cached token has narrower scope. Delete `token.json` and re-consent.                    |
| Server "hangs" after launch                                            | Correct: stdio MCP servers wait for a client. Claude Code launches them on demand.      |

## Related issues

- [#36547](https://github.com/anthropics/claude-code/issues/36547) — `gmail_modify_labels` missing from hosted Gmail MCP (the reason this exists)
- [#32266](https://github.com/anthropics/claude-code/issues/32266) — `gmail_send_draft` missing from hosted Gmail MCP

## License

[MIT](./LICENSE)
