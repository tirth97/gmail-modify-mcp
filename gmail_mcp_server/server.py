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

from gmail_mcp_server.auth import CREDENTIALS_PATH, TOKEN_PATH, get_service

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
        print(
            f"ERROR: OAuth client secrets not found at {CREDENTIALS_PATH}.\n"
            "  1. Create a Desktop OAuth client in Google Cloud Console.\n"
            "  2. Save the downloaded JSON at the path above.\n"
            "  3. Re-run: gmail-modify-mcp auth",
            file=sys.stderr,
        )
        return 2
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
