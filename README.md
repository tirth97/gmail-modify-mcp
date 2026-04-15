# gmail-modify-mcp

A tiny **Model Context Protocol** server that adds **one** tool to any MCP client (Claude Code, Claude Code Desktop, Claude Desktop, and — with path A below — hosted Cowork):

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

### CLI reference

```
gmail-modify-mcp           run the MCP server on stdio (default; no subcommand needed)
gmail-modify-mcp serve     same as above, explicit
gmail-modify-mcp auth      run the OAuth consent flow once
gmail-modify-mcp status    print the authenticated account profile (sanity check)
```

---

## Two ways to use this

| | **Option A — Use a hosted instance** | **Option B — Run it yourself locally** |
|---|---|---|
| **Who runs the server?** | A public HTTPS endpoint (not yet deployed) | You, on your own machine |
| **Works with hosted Cowork (claude.ai web)?** | ✅ Yes (the only way) | ❌ No — Cowork runs in Anthropic's cloud and can't reach a local stdio process |
| **Works with Claude Code (CLI)?** | ✅ Yes | ✅ Yes |
| **Works with Claude Code Desktop / Claude Desktop (chat app)?** | ✅ Yes | ✅ Yes |
| **Your Gmail credentials leave your machine?** | Yes — to whatever machine runs the hosted instance | **No** — everything stays local |
| **Setup effort** | Paste one URL into Cowork's connector dialog | ~10 minutes, see below |
| **Status today** | Planned / not live | ✅ Working — instructions below |

> **Option A is not implemented yet.** Until that's built, everyone uses **Option B**.

---

## Option A — Use a hosted instance (planned)

*Not live yet.* When it is, the UX will be:

1. Visit `https://<hosted-instance>/authorize` once in your browser, grant Gmail access.
2. Open `claude.ai` → Settings → Connectors → **Add custom connector**.
3. URL: `https://<hosted-instance>/mcp`. Auth header: the bearer token you're given at the end of step 1.
4. Done — `gmail_modify_labels` appears alongside the hosted Gmail read tools in every Cowork session.

The architecture, security model, and phased task list are tracked separately and not in this repo yet.

---

## Option B — Run it yourself locally

Everything below is what's working **today**. All of it ran end-to-end on a Windows 11 machine in ~10 minutes.

### Prerequisites

- Python 3.11 or newer
- Git
- A Google account whose Gmail you want this to manage
- Access to the Google Cloud Console at <https://console.cloud.google.com/> (free)
- One of: Claude Code (CLI), Claude Code Desktop (ccd), or the legacy Claude Desktop installed

### Step 1 — Install the Python package

Pick **one** of these. Both produce the same `gmail-modify-mcp` command.

#### Step 1a — `pipx` (recommended, truly cross-OS, no venv to activate)

[pipx](https://pipx.pypa.io/) installs Python CLIs into isolated venvs and exposes them on your global PATH. Same commands on macOS, Linux, and Windows.

```bash
# install pipx once
python -m pip install --user pipx && python -m pipx ensurepath

# install this tool straight from GitHub
pipx install git+https://github.com/tirth97/gmail-modify-mcp.git
```

After this, `gmail-modify-mcp` is a regular command on your PATH. Upgrade later with `pipx upgrade gmail-modify-mcp`. [`uv tool install git+https://github.com/tirth97/gmail-modify-mcp.git`](https://docs.astral.sh/uv/) works equivalently if you prefer uv.

#### Step 1b — Clone + editable install (best for hacking on the code)

```bash
git clone https://github.com/tirth97/gmail-modify-mcp.git
cd gmail-modify-mcp
python -m venv .venv

# macOS / Linux / WSL / Git Bash
./.venv/bin/python -m pip install -e .

# Windows PowerShell / cmd.exe
.\.venv\Scripts\python.exe -m pip install -e .
```

The `gmail-modify-mcp` entry-point now lives at `.venv/bin/gmail-modify-mcp` (POSIX) or `.venv\Scripts\gmail-modify-mcp.exe` (Windows). It's on PATH **only when the venv is activated**.

To skip venv activation, the repo ships two thin launcher scripts at the project root that forward to the venv entry point:

```bash
# macOS / Linux / WSL / Git Bash
./gmail-modify-mcp status

# Windows cmd.exe
gmail-modify-mcp status

# Windows PowerShell
.\gmail-modify-mcp status
```

These detect both `.venv/bin/` and `.venv/Scripts/` automatically and fail with a clear "venv not found" message if you skipped the install step.

### Step 2 — Create Google Cloud OAuth credentials

Manual, browser-only. Do **not** skip steps 3 and 4 or you'll get `Error 403: access_denied`.

1. Open <https://console.cloud.google.com/> and create (or pick) a project.
2. **APIs & Services → Library → Gmail API → Enable.**
3. **APIs & Services → OAuth consent screen** → choose **External**.
4. Under **Test users**, click **+ Add users** and add your own Gmail address.
5. **APIs & Services → Credentials → + Create credentials → OAuth client ID.**
6. Application type: **Desktop app**. Name it anything. Click **Create**.
7. Click **Download JSON** on the new client. The downloaded file will be named `client_secret_<long-id>.apps.googleusercontent.com.json`.
8. **Rename** it to `credentials.json`.
9. Move it to:
   - If you used **Step 1a (pipx)**: any directory you want (a project folder you'll launch from), or wherever you point `GMAIL_MCP_CREDENTIALS` to.
   - If you used **Step 1b (clone)**: the project root (`gmail-modify-mcp/credentials.json`). `.gitignore` already excludes it.

> ⚠️ **Top-level key check.** Open `credentials.json`. The first key must be `"installed"`, not `"web"`. If it's `"web"` you accidentally made a Web OAuth client instead of a Desktop one — delete it and re-do step 6 as **Desktop app**.

### Step 3 — First-run OAuth consent

Trigger the one-time consent flow. A browser window opens, you pick your Google account, grant the `gmail.modify` scope, and `token.json` gets written next to `credentials.json`.

```bash
gmail-modify-mcp auth
```

Expected output:

```
Authorized as: you@gmail.com
Token cached at: .../token.json
```

Then sanity check:

```bash
gmail-modify-mcp status
# Authorized as : you@gmail.com
# Messages total: 1341
# Threads total : 930
```

If you see the profile, you're done with the backend. Future runs refresh the token silently — you never have to `auth` again unless you delete `token.json` or change scopes.

### Step 4 — Wire it into your Claude client

Depending on which Claude you use, pick **one** (or more — they're independent).

#### Step 4a — Claude Code Desktop / Claude Desktop (the chat app)

Both the newer **Claude Code Desktop** (ccd) app and the legacy **Claude Desktop** app read MCP servers from the same config file:

| OS      | Path                                                                  |
| ------- | --------------------------------------------------------------------- |
| macOS   | `~/Library/Application Support/Claude/claude_desktop_config.json`     |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json`                         |
| Linux   | `~/.config/Claude/claude_desktop_config.json`                         |

Open it (create it if it doesn't exist) and add a `mcpServers` entry. **If the file already has other top-level keys** like `preferences`, preserve them — just add `mcpServers` alongside.

If you installed via **Step 1a (pipx)**:

```json
{
  "mcpServers": {
    "gmail-modify-mcp": {
      "command": "gmail-modify-mcp",
      "args": []
    }
  }
}
```

If you installed via **Step 1b (clone + venv)**, point at the absolute path of the entry script inside your venv:

```jsonc
{
  "mcpServers": {
    "gmail-modify-mcp": {
      // macOS / Linux
      "command": "/absolute/path/to/gmail-modify-mcp/.venv/bin/gmail-modify-mcp",
      // Windows
      // "command": "C:\\absolute\\path\\to\\gmail-modify-mcp\\.venv\\Scripts\\gmail-modify-mcp.exe",
      "args": []
    }
  }
}
```

Then **fully quit** the app (system tray → right-click → Quit on Windows, `⌘Q` on macOS — closing the window is not enough) and reopen it. In a new chat ask:

> What MCP tools do you have available?

`gmail_modify_labels` should be in the list.

#### Step 4b — Claude Code (CLI)

Two ways. Pick whichever fits your workflow.

**Project-scoped `.mcp.json`** — auto-discovered when Claude Code is launched from this directory. The repo ships `.mcp.json.example` with placeholder paths:

```bash
# macOS / Linux / WSL / Git Bash
cp .mcp.json.example .mcp.json
# Windows PowerShell
Copy-Item .mcp.json.example .mcp.json
```

Edit the new `.mcp.json` and replace `/absolute/path/to/gmail-modify-mcp` with your real clone path. The real `.mcp.json` is gitignored — your absolute paths never leak into a public commit.

**Globally via `claude mcp add`** — available everywhere, not tied to a directory:

```bash
# If installed via pipx
claude mcp add --scope user gmail-modify-mcp -- gmail-modify-mcp

# If installed via clone (point at the venv entry script)
claude mcp add --scope user gmail-modify-mcp -- \
  "/absolute/path/to/gmail-modify-mcp/.venv/bin/gmail-modify-mcp"
```

#### Step 4c — Hosted Cowork (claude.ai web)

**Not supported by Option B.** Cowork runs in Anthropic's cloud and can only connect to MCP servers that are reachable from Anthropic's public IP ranges over HTTPS. A local stdio server on your laptop is, by definition, not reachable. Use **Option A** (the hosted instance — not live yet) when you need Cowork support, or use **Claude Code / Claude Desktop** today.

### Step 5 — Verify end-to-end

In a chat/session with both this server **and** the hosted Gmail connector enabled:

> Find the most recent unread newsletter in my inbox and archive it.

Expected behavior: the model uses `gmail_search_messages` (hosted) to find a candidate → calls `gmail_modify_labels` (this server) with `remove_label_ids=["INBOX"]` → the message disappears from your inbox.

Or, for a harmless reversible test:

> Star the most recent email from GitHub.

Then ask it to remove the star:

> Unstar it again.

If both work, you're done.

---

## File layout

```
gmail-modify-mcp/
├── .gitattributes             line-ending policy (LF for shell, CRLF for .bat)
├── .gitignore                 excludes credentials.json, token.json, .venv, .claude/, .mcp.json
├── .mcp.json.example          template for Claude Code project-scoped registration
├── LICENSE                    MIT
├── pyproject.toml             package metadata + gmail-modify-mcp entry point
├── README.md                  this file
├── gmail-modify-mcp           POSIX launcher (Option 1b) — forwards to .venv/bin
├── gmail-modify-mcp.bat       Windows launcher (Option 1b) — forwards to .venv\Scripts
├── credentials.json           (you provide; gitignored)
├── token.json                 (auto-created on first auth; gitignored)
└── gmail_mcp_server/
    ├── __init__.py
    ├── auth.py                OAuth desktop flow + token refresh
    └── server.py              FastMCP server, gmail_modify_labels tool, CLI
```

## Environment variables

| Variable                | Default                       | Purpose                              |
| ----------------------- | ----------------------------- | ------------------------------------ |
| `GMAIL_MCP_CREDENTIALS` | `<project>/credentials.json`  | Override OAuth client secrets path.  |
| `GMAIL_MCP_TOKEN`       | `<project>/token.json`        | Override cached token path.          |

Useful if you want to keep secrets in `%APPDATA%` / `~/.config` instead of the project root.

## Security notes

- The OAuth scope used is `https://www.googleapis.com/auth/gmail.modify`. This grants read + label modification but **not** permanent delete. That's intentional.
- `credentials.json` and `token.json` are in `.gitignore`. Don't `git add -f` them. The gitignore also catches Google's default `client_secret*.json` download filename.
- Move-to-trash is supported via `add_label_ids=["TRASH"]`. The `TRASH` label is reversible — the message stays in Trash for 30 days before Google purges it.
- This server only exposes one tool. It cannot read messages, send mail, or change account settings.
- `.mcp.json` is gitignored because it contains absolute local paths. Always copy from `.mcp.json.example`.

## Troubleshooting

| Symptom                                                                | Fix                                                                                     |
| ---------------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| `OAuth client secrets not found`                                       | `credentials.json` is missing. Re-do Step 2.                                             |
| `Error 403: access_denied` in the consent browser                      | You weren't added as a **Test user** in the OAuth consent screen. Go back to Step 2.4.  |
| Top-level key in `credentials.json` is `"web"` instead of `"installed"`| You created a Web OAuth client. Make a **Desktop app** client instead and re-download.  |
| `invalid_grant` / scope errors                                         | Delete `token.json` and re-run `gmail-modify-mcp auth`.                                 |
| `HttpError 403: Insufficient Permission` from `modify`                 | Cached token has narrower scope. Delete `token.json` and re-consent.                    |
| Server "hangs" after launch                                            | Correct: stdio MCP servers wait for a client. Claude Code launches them on demand.      |
| `gmail-modify-mcp: command not found` in a fresh terminal (Option 1b)  | Your venv isn't activated. Either activate it or use the `./gmail-modify-mcp` launcher. |
| Restarted the chat app but tool still missing                          | You closed the window instead of fully quitting. System-tray Quit on Windows, `⌘Q` on macOS. |
| Want Cowork (claude.ai web) support                                    | Option B cannot do this. Wait for Option A, which requires a hosted HTTPS MCP endpoint. |

## Related issues

- [#36547](https://github.com/anthropics/claude-code/issues/36547) — `gmail_modify_labels` missing from hosted Gmail MCP (the reason this exists)
- [#32266](https://github.com/anthropics/claude-code/issues/32266) — `gmail_send_draft` missing from hosted Gmail MCP

## License

[MIT](./LICENSE)
