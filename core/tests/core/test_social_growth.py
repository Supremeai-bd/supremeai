from datetime import UTC, datetime

import pytest

from core.social_growth import DraftStatus, SocialDraft, SocialGrowthCircle, SocialPlatform


def test_social_growth_requires_approval_before_publish_state():
    circle = SocialGrowthCircle()
    draft = circle.create_draft(
        SocialDraft(
            tenant_id="tenant-a",
            author_id="user-a",
            platform=SocialPlatform.FACEBOOK,
            body="A reviewed community update",
            scheduled_for=datetime.now(UTC),
        )
    )

    assert draft.status is DraftStatus.DRAFT
    approved = circle.approve(draft.id, "tenant-a", "approver-a")
    assert approved.status is DraftStatus.APPROVED
    assert approved.approved_by == "approver-a"


def test_social_growth_is_tenant_scoped():
    circle = SocialGrowthCircle()
    draft = circle.create_draft(
        SocialDraft(
            tenant_id="tenant-a",
            author_id="user-a",
            platform=SocialPlatform.INSTAGRAM,
            body="Tenant-owned draft",
        )
    )

    with pytest.raises(KeyError):
        circle.approve(draft.id, "tenant-b", "user-b")


def test_pause_blocks_new_social_drafts():
    circle = SocialGrowthCircle()
    circle.pause("tenant-a")

    with pytest.raises(PermissionError):
        circle.create_draft(
            SocialDraft(
                tenant_id="tenant-a",
                author_id="user-a",
                platform=SocialPlatform.FACEBOOK,
                body="Should not publish",
            )
        )
