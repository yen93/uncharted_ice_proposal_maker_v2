"""Reads the unprocessed-proposal queue and marks rows done.

The API trigger drains `proposal_demo_notes_email_logs`:
    select * from proposal_demo_notes_email_logs
    where is_processed is null or is_processed = false
    order by created_at desc

Each row carries `demo_notes_link` (a Drive link to the notes file) and
`additional_notes` (extra typed context). Rows are marked processed regardless of
outcome so a bad row is never retried forever; `status` records the outcome.
"""

from datetime import datetime, timezone
from typing import Optional

from supabase import Client, create_client

import config


def get_client() -> Client:
    config.require("SUPABASE_URL", "SUPABASE_SERVICE_KEY")
    return create_client(config.SUPABASE_URL, config.SUPABASE_SERVICE_KEY)


def list_unprocessed(client: Client) -> list[dict]:
    """Returns unprocessed rows (newest first) as
    [{id, demo_notes_link, additional_notes}, ...]."""
    resp = (
        client.table(config.SUPABASE_LOG_TABLE)
        .select("id, demo_notes_link, additional_notes, created_at")
        .or_("is_processed.is.null,is_processed.eq.false")
        .order("created_at", desc=True)
        .execute()
    )
    return resp.data or []


def mark_row_processed(
    client: Client,
    row_id: str,
    status: str,
    error_message: Optional[str] = None,
    proposal_link: Optional[str] = None,
    has_fathom_notes: Optional[bool] = None,
    tag: Optional[str] = None,
) -> None:
    """Marks a specific row processed (by primary key). `status` is one of
    'success' | 'needs_review' | 'error'. `has_fathom_notes`/`tag` record whether
    matching Fathom meeting notes were found and folded into the proposal; they are
    only written when provided (None leaves the existing value untouched)."""
    fields = {
        "is_processed": True,
        "status": status,
        "error_message": error_message,
        "proposal_link": proposal_link,
        "processed_at": datetime.now(timezone.utc).isoformat(),
    }
    if has_fathom_notes is not None:
        fields["has_fathom_notes"] = has_fathom_notes
    if tag is not None:
        fields["tag"] = tag
    client.table(config.SUPABASE_LOG_TABLE).update(fields).eq("id", row_id).execute()
