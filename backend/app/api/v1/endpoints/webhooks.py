# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""Webhook subscriptions: where to send changes, and what happened to each send.

ORG_ADMIN only, for the reason the change feed is: a webhook carries whole
bookings, purpose included, to somewhere outside. docs/webhooks.md is the
design; services/webhooks.py does the work.
"""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core import clock
from app.core.config import get_settings
from app.core.database import get_db
from app.core.errors import ChronosError, ErrorCode
from app.core.pagination import Page
from app.core.security import require_roles
from app.models.db import WebhookAttempt, WebhookDelivery, WebhookSubscription
from app.schemas.webhooks import (
    WebhookCreate,
    WebhookDeliveryResponse,
    WebhookResponse,
    WebhookUpdate,
    WebhookWithSecret,
)
from app.services import webhooks

router = APIRouter()

FEED_OFF = (
    "webhooks are sent from the change feed, which is off. Set CHANGE_FEED_ENABLED=true first."
)


def _view(row: WebhookSubscription) -> dict:
    now = clock.now()
    return {
        "id": row.id,
        "url": row.url,
        "event_types": row.event_types.split(","),
        "active": row.active,
        "paused_at": row.paused_at,
        "consecutive_failures": row.consecutive_failures,
        "previous_secret_expires_at": (
            row.previous_secret_expires_at if webhooks.previous_secret_live(row, now) else None
        ),
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def _delivery_view(db: Session, row: WebhookDelivery) -> dict:
    attempts = (
        db.query(WebhookAttempt)
        .filter(WebhookAttempt.delivery_id == row.id)
        .order_by(WebhookAttempt.id)
        .all()
    )
    return {
        "id": row.id,
        "subscription_id": row.subscription_id,
        "event_id": row.event_id,
        "event_type": row.event_type,
        "entity_kind": row.entity_kind,
        "entity_id": row.entity_id,
        "marker_id": row.marker_id,
        "status": row.status,
        "attempt_count": row.attempt_count,
        "next_attempt_at": row.next_attempt_at,
        "created_at": row.created_at,
        "completed_at": row.completed_at,
        "attempts": attempts,
    }


def _vetted(url: str) -> str:
    """The URL if it may be called now, else a 422 saying why not."""
    try:
        webhooks.vet(url)
    except webhooks.Refused as refused:
        raise ChronosError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"This URL cannot receive webhooks: {refused}.",
            code=ErrorCode.WEBHOOK_URL_REFUSED,
        ) from None
    return url


def _get(db: Session, subscription_id: int) -> WebhookSubscription:
    row = db.get(WebhookSubscription, subscription_id)
    if row is None:
        raise ChronosError(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Webhook {subscription_id} not found",
            code=ErrorCode.NOT_FOUND,
        )
    return row


@router.post(
    "/",
    operation_id="webhooks.create",
    response_model=WebhookWithSecret,
    status_code=status.HTTP_201_CREATED,
)
def create_webhook(
    payload: WebhookCreate,
    db: Session = Depends(get_db),
    _=Depends(require_roles("ORG_ADMIN")),
):
    """Start sending changes to a URL, from now on.

    The response holds the signing secret, the only time it is shown. The
    subscription starts at the newest change, so it hears about nothing that
    happened before it existed; read the rooms and the bookings once in full,
    as a change feed consumer does.

    503 while the change feed is off, since there would be nothing to send.
    """
    if not get_settings().change_feed_enabled:
        raise ChronosError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=FEED_OFF,
            code=ErrorCode.CHANGE_FEED_DISABLED,
        )
    secret = webhooks.new_secret()
    row = WebhookSubscription(
        url=_vetted(payload.url),
        event_types=",".join(payload.event_types),
        active=payload.active,
        consecutive_failures=0,
        cursor=webhooks.latest_marker_id(db),
        secret=secret,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {**_view(row), "secret": secret}


@router.get("/", operation_id="webhooks.list", response_model=list[WebhookResponse])
def list_webhooks(db: Session = Depends(get_db), _=Depends(require_roles("ORG_ADMIN"))):
    return [_view(row) for row in db.query(WebhookSubscription).order_by(WebhookSubscription.id)]


@router.get("/{subscription_id}", operation_id="webhooks.get", response_model=WebhookResponse)
def get_webhook(
    subscription_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_roles("ORG_ADMIN")),
):
    return _view(_get(db, subscription_id))


@router.patch("/{subscription_id}", operation_id="webhooks.update", response_model=WebhookResponse)
def update_webhook(
    subscription_id: int,
    payload: WebhookUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_roles("ORG_ADMIN")),
):
    """Change the URL, the event types, or whether it is active.

    New event types apply to changes fanned out from now on. Switched off, a
    subscription keeps its place and sends nothing; switched back on, it
    carries on from that place, so what happened in between is sent then.
    """
    row = _get(db, subscription_id)
    if payload.url is not None:
        row.url = _vetted(payload.url)
    if payload.event_types is not None:
        row.event_types = ",".join(payload.event_types)
    if payload.active is not None:
        row.active = payload.active
    db.commit()
    db.refresh(row)
    return _view(row)


@router.delete(
    "/{subscription_id}",
    operation_id="webhooks.delete",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_webhook(
    subscription_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_roles("ORG_ADMIN")),
):
    """Stop sending and forget the subscription, its deliveries and their attempts."""
    row = _get(db, subscription_id)
    deliveries = db.query(WebhookDelivery.id).filter(WebhookDelivery.subscription_id == row.id)
    db.query(WebhookAttempt).filter(WebhookAttempt.delivery_id.in_(deliveries)).delete(
        synchronize_session=False
    )
    db.query(WebhookDelivery).filter(WebhookDelivery.subscription_id == row.id).delete(
        synchronize_session=False
    )
    db.delete(row)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{subscription_id}/rotate-secret",
    operation_id="webhooks.rotateSecret",
    response_model=WebhookWithSecret,
)
def rotate_webhook_secret(
    subscription_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_roles("ORG_ADMIN")),
):
    """A new signing secret, shown this once, with the old one still signing for a day.

    Every send carries both signatures until the old secret expires or is
    removed, so receivers can move to the new one at their own pace. 409 while
    two are already live: remove the older one first.
    """
    row = _get(db, subscription_id)
    now = clock.now()
    if webhooks.previous_secret_live(row, now):
        raise ChronosError(
            status_code=status.HTTP_409_CONFLICT,
            detail="This webhook already has two live secrets. Remove the previous one first.",
            code=ErrorCode.WEBHOOK_SECRET_LIMIT,
        )
    secret = webhooks.new_secret()
    row.previous_secret = row.secret
    row.previous_secret_expires_at = now + webhooks.PREVIOUS_SECRET_LIFETIME
    row.secret = secret
    db.commit()
    db.refresh(row)
    return {**_view(row), "secret": secret}


@router.delete(
    "/{subscription_id}/previous-secret",
    operation_id="webhooks.removePreviousSecret",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_previous_webhook_secret(
    subscription_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_roles("ORG_ADMIN")),
):
    """Stop signing with the secret before the last rotation. Nothing to remove is not an error."""
    row = _get(db, subscription_id)
    row.previous_secret = None
    row.previous_secret_expires_at = None
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{subscription_id}/resume",
    operation_id="webhooks.resume",
    response_model=WebhookResponse,
)
def resume_webhook(
    subscription_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_roles("ORG_ADMIN")),
):
    """Start a paused subscription again, from where it stopped.

    Nothing is skipped: the changes made while it was paused are fanned out
    and sent, oldest first. Resuming one that is not paused changes nothing.
    """
    row = _get(db, subscription_id)
    row.paused_at = None
    row.consecutive_failures = 0
    db.commit()
    db.refresh(row)
    return _view(row)


@router.get(
    "/{subscription_id}/deliveries",
    operation_id="webhooks.listDeliveries",
    response_model=list[WebhookDeliveryResponse],
)
def list_webhook_deliveries(
    subscription_id: int,
    page: Page = Depends(),
    db: Session = Depends(get_db),
    _=Depends(require_roles("ORG_ADMIN")),
):
    """What was sent to this subscription and what came back, newest first."""
    _get(db, subscription_id)
    query = db.query(WebhookDelivery).filter(WebhookDelivery.subscription_id == subscription_id)
    return [_delivery_view(db, row) for row in page.rows(query, WebhookDelivery.id.desc())]


@router.post(
    "/{subscription_id}/deliveries/{delivery_id}/redeliver",
    operation_id="webhooks.redeliver",
    response_model=WebhookDeliveryResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def redeliver_webhook(
    subscription_id: int,
    delivery_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_roles("ORG_ADMIN")),
):
    """Send one delivery again, on the next pass of the worker.

    Same webhook-id and same body, with a new timestamp and signature, and a
    fresh set of retries. Later deliveries for the same row wait behind it, as
    they would have the first time.
    """
    _get(db, subscription_id)
    row = db.get(WebhookDelivery, delivery_id)
    if row is None or row.subscription_id != subscription_id:
        raise ChronosError(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Delivery {delivery_id} not found on webhook {subscription_id}",
            code=ErrorCode.NOT_FOUND,
        )
    webhooks.redeliver(row)
    db.commit()
    db.refresh(row)
    return _delivery_view(db, row)
