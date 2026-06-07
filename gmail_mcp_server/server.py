"""MCP server exposing a single tool: ``gmail_modify_labels``.

Anthropic's hosted Gmail MCP connector at ``gmail.mcp.claude.com`` provides
read tools and ``gmail_create_draft`` but cannot modify message labels, which
blocks every inbox-management workflow (archive, mark read/unread, star,
trash, categorize). Tracked in
https://github.com/anthropics/claude-code/issues/36547.

This server fills that single gap. Run it alongside the hosted connector:
the hosted one handles reads, this one handles label modifications.

CLI:
  gmail-modify-mcp                run the MCP server on stdio (default)
  gmail-modify-mcp serve          same as above
  gmail-modify-mcp auth           run the OAuth consent flow once
  gmail-modify-mcp status         print the authenticated account profile
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from googleapiclient.errors import HttpError
from mcp.server.fastmcp import FastMCP

from gmail_mcp_server.auth import (
    CREDENTIALS_PATH,
    TOKEN_PATH,
    get_service,
    save_client_config,
)

mcp = FastMCP("gmail-modify")


@mcp.tool()
def gmail_modify_labels(
    message_id: str,
    add_label_ids: list[str] | None = None,
    remove_label_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Add and/or remove Gmail labels on a single message.

    Wraps the Gmail API ``users.messages.modify`` endpoint. At least one of
    ``add_label_ids`` or ``remove_label_ids`` should be non-empty.

    Common system label IDs:
      INBOX, UNREAD, STARRED, IMPORTANT, TRASH, SPAM, SENT, DRAFT.

    Custom user label IDs look like ``Label_1234567890123456789`` and can be
    discovered with the hosted connector's ``gmail_list_labels`` tool.

    Examples:
      Archive a message:        remove_label_ids=["INBOX"]
      Mark as read:             remove_label_ids=["UNREAD"]
      Mark as unread:           add_label_ids=["UNREAD"]
      Star:                     add_label_ids=["STARRED"]
      Move to trash:            add_label_ids=["TRASH"]
      Apply custom label:       add_label_ids=["Label_1234567890"]

    Args:
      message_id: The Gmail message ID (NOT the thread ID).
      add_label_ids: Label IDs to add. Defaults to none.
      remove_label_ids: Label IDs to remove. Defaults to none.

    Returns:
      The updated message resource (id, threadId, labelIds) on success, or
      a dict ``{"error": ...}`` on failure.
    """
    add = add_label_ids or []
    remove = remove_label_ids or []

    if not add and not remove:
        return {
            "error": (
                "No labels to change. Provide at least one of add_label_ids "
                "or remove_label_ids."
            )
        }

    try:
        service = get_service()
        result = (
            service.users()
            .messages()
            .modify(
                userId="me",
                id=message_id,
                body={"addLabelIds": add, "removeLabelIds": remove},
            )
            .execute()
        )
        return {
            "id": result.get("id"),
            "threadId": result.get("threadId"),
            "labelIds": result.get("labelIds", []),
        }
    except HttpError as e:
        return {
            "error": f"Gmail API error ({e.status_code}): {e.reason}",
            "details": getattr(e, "error_details", None),
        }
    except FileNotFoundError as e:
        return {"error": str(e)}
    except Exception as e:  # pragma: no cover - defensive
        return {"error": f"{type(e).__name__}: {e}"}


@mcp.tool()
def gmail_setup(
    client_id: str,
    client_secret: str,
    auth_uri: str | None = None,
    token_uri: str | None = None,
    redirect_uris: list[str] | None = None,
) -> dict[str, Any]:
    """One-time setup: save Google OAuth credentials and complete the consent flow.

    A browser window will open for Google consent. Complete it there.

    Create a Desktop OAuth client at:
    https://console.cloud.google.com/apis/credentials

    Args:
        client_id: OAuth 2.0 Client ID (ends in .apps.googleusercontent.com).
        client_secret: OAuth 2.0 Client Secret (starts with GOCSPX-).
        auth_uri: Google auth endpoint. Leave empty for the default.
        token_uri: Google token endpoint. Leave empty for the default.
        redirect_uris: OAuth redirect URIs. Leave empty for the default.

    Returns:
        Status dict with authorized email on success.
    """
    if TOKEN_PATH.exists():
        try:
            service = get_service()
            profile = service.users().getProfile(userId="me").execute()
            return {
                "status": "already_configured",
                "email": profile.get("emailAddress"),
                "message": "Gmail is already authorized. No setup needed.",
            }
        except Exception:
            pass

    if not client_id or not client_secret:
        return {"error": "Both client_id and client_secret are required."}

    try:
        save_client_config(
            client_id, client_secret,
            auth_uri=auth_uri, token_uri=token_uri, redirect_uris=redirect_uris,
        )
        service = get_service()
        profile = service.users().getProfile(userId="me").execute()
        return {
            "status": "authorized",
            "email": profile.get("emailAddress"),
            "message": f"Setup complete! Authorized as {profile.get('emailAddress')}.",
        }
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


# --------------------------------------------------------------------------- #
# CLI                                                                          #
# --------------------------------------------------------------------------- #

def _cmd_serve(_args: argparse.Namespace) -> int:
    """Run the MCP server on stdio. Default subcommand."""
    mcp.run()
    return 0


def _cmd_auth(_args: argparse.Namespace) -> int:
    """Run the OAuth consent flow once and cache the token."""
    if not CREDENTIALS_PATH.exists():
        if not sys.stdin.isatty():
            print(
                f"ERROR: OAuth client secrets not found at {CREDENTIALS_PATH}.\n"
                "Run 'gmail-modify-mcp auth' from an interactive terminal,\n"
                "or set GMAIL_MCP_CREDENTIALS to point to your credentials.json.",
                file=sys.stderr,
            )
            return 2

        print("OAuth client secrets not found. Let's set them up.\n")
        print("You need a Google Cloud OAuth client ID (Desktop type).")
        print("Create one at: https://console.cloud.google.com/apis/credentials\n")

        client_id = input("Paste your Client ID: ").strip()
        client_secret = input("Paste your Client Secret: ").strip()
        if not client_id or not client_secret:
            print("ERROR: Both Client ID and Client Secret are required.", file=sys.stderr)
            return 2

        auth_uri = input("Auth URI (press Enter for default): ").strip() or None
        token_uri = input("Token URI (press Enter for default): ").strip() or None
        redirect_uri = input("Redirect URI (press Enter for default): ").strip()
        redirect_uris = [redirect_uri] if redirect_uri else None

        path = save_client_config(
            client_id, client_secret,
            auth_uri=auth_uri, token_uri=token_uri, redirect_uris=redirect_uris,
        )
        print(f"\nCredentials saved to: {path}")

    try:
        service = get_service()
        profile = service.users().getProfile(userId="me").execute()
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    print(f"Authorized as: {profile.get('emailAddress')}")
    print(f"Token cached at: {TOKEN_PATH}")
    return 0


def _cmd_status(_args: argparse.Namespace) -> int:
    """Print the authenticated account profile (read-only sanity check)."""
    if not TOKEN_PATH.exists():
        print(
            f"Not authenticated. Token file missing at {TOKEN_PATH}.\n"
            "Run: gmail-modify-mcp auth",
            file=sys.stderr,
        )
        return 2
    try:
        profile = get_service().users().getProfile(userId="me").execute()
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    print(
        f"Authorized as : {profile.get('emailAddress')}\n"
        f"Messages total: {profile.get('messagesTotal')}\n"
        f"Threads total : {profile.get('threadsTotal')}"
    )
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gmail-modify-mcp",
        description=(
            "Local MCP server exposing gmail_modify_labels (archive, "
            "mark read/unread, star, trash, categorize) for Claude Code."
        ),
    )
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    p_serve = sub.add_parser("serve", help="run the MCP server on stdio (default)")
    p_serve.set_defaults(func=_cmd_serve)

    p_auth = sub.add_parser("auth", help="run the OAuth consent flow once")
    p_auth.set_defaults(func=_cmd_auth)

    p_status = sub.add_parser("status", help="print the authenticated profile")
    p_status.set_defaults(func=_cmd_status)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        # No subcommand → default to running the server.
        return _cmd_serve(args)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
