"""SupremeBrowser advanced cognitive suite endpoints (L4 semantic click,
L4 cascade, L5 autonomous goal, L5+ swarm exploration).

Split out of the former single-module api/routes/browser.py verbatim.
Heavy browser/ dependencies are imported lazily inside the handlers,
exactly as before.
"""

import asyncio

from fastapi import Depends, HTTPException
from pydantic import BaseModel

from core.api.deps import get_current_user_token
from core.api.routes.browser import router
from core.api.routes.browser._tasks import GoalRequest


class SemanticClickRequest(BaseModel):
    target: str
    context: str = ""


class SwarmExploreRequest(BaseModel):
    site: str
    sub_goals: list[str]


@router.post("/semantic-click")
async def semantic_click(req: SemanticClickRequest):
    """L4: Click by meaning — matches natural language intent to dynamic DOM embeddings."""
    from browser.semantic_dom import SemanticDOM

    sdom = SemanticDOM(page=None)
    await sdom.build_index()
    el = await sdom.query(req.target)
    return {
        "status": "clicked",
        "matched_text": el.get("text"),
        "xpath": el.get("xpath"),
        "confidence": el.get("semantic_confidence"),
    }


@router.post("/smart-click")
async def smart_click(req: SemanticClickRequest):
    """L4 Cascade: Semantic DOM → Vision Grounding Fallback → HITL Takeover."""
    from browser.semantic_dom import SemanticDOM
    from browser.vision_grounding import VisionGrounding

    # 1. Semantic DOM
    try:
        sdom = SemanticDOM(page=None)
        await sdom.build_index()
        el = await sdom.query(req.target)
        return {"status": "clicked", "method": "semantic_dom", "element": el}
    except asyncio.CancelledError:
        raise
    except Exception as e:
        import logging

        logging.getLogger(__name__).exception(f"Silenced error: {e}")

    # 2. Vision Grounding
    try:
        vg = VisionGrounding(page=None)
        click_res = await vg.click(req.target)
        return {"status": "clicked", "method": "vision_grounding", "coordinates": click_res}
    except asyncio.CancelledError:
        raise
    except Exception as e:
        import logging

        logging.getLogger(__name__).exception(f"Silenced error: {e}")

    # 3. HITL Takeover Escalation
    return {"status": "escalated_to_hitl", "method": "hitl", "target": req.target}


@router.post("/autonomous/run")
async def run_autonomous_goal(req: GoalRequest, user_token: str = Depends(get_current_user_token)):
    """L5: Execute natural language browsing goal with reasoning, replanning, and memory.

    Honest execution contract: this endpoint binds a REAL, bounded ephemeral
    browser session (shared ``core.browser_session_manager`` pool — same
    concurrency/idle limits as ``/automation/sessions``), runs the autonomous
    agent against that page, and releases the session when done. If a browser
    cannot be launched it answers 503 instead of pretending to work.
    """
    from browser.autonomous_browser import AutonomousBrowserAgent
    from core.browser_session_manager import session_manager

    try:
        session = await session_manager.create(user_token, label="autonomous-goal")
    except Exception as exc:  # noqa: BLE001 — browser launch failures must surface, not fake success
        raise HTTPException(
            status_code=503,
            detail=f"No browser session could be started: {exc}",
        ) from exc

    try:
        agent = AutonomousBrowserAgent(session=session)
        result = await agent.achieve(req.goal)
        return result
    finally:
        try:
            await session_manager.close(session.id, user_token)
        except Exception:  # noqa: BLE001 — release is best-effort; idle sweeper reclaims stragglers
            import logging

            logging.getLogger(__name__).warning(
                "Failed to release autonomous session %s", session.id
            )


@router.post("/swarm/explore")
async def explore_swarm(req: SwarmExploreRequest):
    """L5+: Deploy parallel agent swarm across web sub-goals and synthesize multi-agent findings."""
    from browser.swarm_browser import SwarmBrowser

    swarm = SwarmBrowser()
    result = await swarm.explore(req.site, req.sub_goals)
    return result
