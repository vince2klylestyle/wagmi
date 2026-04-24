"""FastAPI server for TG Mini App.

Endpoints for:
- User auth (TG WebApp data)
- Posts (raids)
- Engagement tracking
- Leaderboard
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel

from .bagworker_api import db

app = FastAPI(title="Bagworker Platform")

# Allow TG Mini App origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ===== Request/Response Models =====

class AuthRequest(BaseModel):
    tg_id: int
    username: str
    first_name: str
    last_name: Optional[str] = None


class AuthResponse(BaseModel):
    tg_id: int
    username: str
    points: int
    rank: int


class PostRequest(BaseModel):
    text: str
    created_by_tg_id: int


class PostResponse(BaseModel):
    post_id: str
    text: str
    created_at: str
    raid_count: int


class EngagementRequest(BaseModel):
    post_id: str
    user_tg_id: int
    action_type: str  # "retweet", "like", "reply"
    image_id: str = ""
    image_brand: str = ""
    raid_id: str = ""


class EngagementResponse(BaseModel):
    points_earned: int
    user_points: int
    user_rank: int


class UserStats(BaseModel):
    tg_id: int
    username: str
    points: int
    rank: int
    retweets: int
    likes: int
    replies: int


class LeaderboardEntry(BaseModel):
    rank: int
    username: str
    points: int
    retweets: int
    likes: int
    replies: int


# ===== Endpoints =====

@app.post("/auth")
def auth(req: AuthRequest) -> AuthResponse:
    """Authenticate user via TG data."""
    user = db.user_get_or_create(
        tg_id=req.tg_id,
        username=req.username,
        first_name=req.first_name,
        last_name=req.last_name or "",
    )

    # Get user rank
    leaderboard = db.leaderboard(limit=1000)
    rank = next(
        (i + 1 for i, u in enumerate(leaderboard) if u["tg_id"] == req.tg_id),
        len(leaderboard) + 1,
    )

    return AuthResponse(
        tg_id=user["tg_id"],
        username=user["username"],
        points=user.get("points", 0),
        rank=rank,
    )


@app.get("/user/{tg_id}")
def get_user(tg_id: int) -> UserStats:
    """Get user stats."""
    user = db.user_get(tg_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    leaderboard = db.leaderboard(limit=1000)
    rank = next(
        (i + 1 for i, u in enumerate(leaderboard) if u["tg_id"] == tg_id),
        len(leaderboard) + 1,
    )

    return UserStats(
        tg_id=user["tg_id"],
        username=user["username"],
        points=user.get("points", 0),
        rank=rank,
        retweets=user.get("retweets", 0),
        likes=user.get("likes", 0),
        replies=user.get("replies", 0),
    )


@app.post("/post")
def create_post(req: PostRequest) -> PostResponse:
    """Create a new raid post."""
    post_id = f"post_{int(datetime.now().timestamp() * 1000)}"
    post = db.post_create(
        post_id=post_id,
        text=req.text,
        created_by_tg_id=req.created_by_tg_id,
    )
    return PostResponse(
        post_id=post["post_id"],
        text=post["text"],
        created_at=post["created_at"],
        raid_count=post.get("raid_count", 0),
    )


@app.get("/posts")
def get_posts(limit: int = 10) -> list[PostResponse]:
    """Get recent posts for raiding."""
    posts = db.posts_recent(limit=limit)
    return [
        PostResponse(
            post_id=p["post_id"],
            text=p["text"],
            created_at=p["created_at"],
            raid_count=p.get("raid_count", 0),
        )
        for p in posts
    ]


@app.post("/engage")
def record_engagement(req: EngagementRequest) -> EngagementResponse:
    """Record engagement (retweet, like, reply)."""
    # Validate action type
    if req.action_type not in ("retweet", "like", "reply"):
        raise HTTPException(status_code=400, detail="Invalid action type")

    # Record action with image tracking
    points = db.action_record(
        post_id=req.post_id,
        user_tg_id=req.user_tg_id,
        action_type=req.action_type,
        image_id=req.image_id,
        image_brand=req.image_brand,
        raid_id=req.raid_id or req.post_id,
    )

    # Get updated user stats
    user = db.user_get(req.user_tg_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    leaderboard = db.leaderboard(limit=1000)
    rank = next(
        (i + 1 for i, u in enumerate(leaderboard) if u["tg_id"] == req.user_tg_id),
        len(leaderboard) + 1,
    )

    return EngagementResponse(
        points_earned=points,
        user_points=user.get("points", 0),
        user_rank=rank,
    )


@app.get("/leaderboard")
def leaderboard(limit: int = 20) -> list[LeaderboardEntry]:
    """Get leaderboard."""
    users = db.leaderboard(limit=limit)
    return [
        LeaderboardEntry(
            rank=i + 1,
            username=u["username"],
            points=u.get("points", 0),
            retweets=u.get("retweets", 0),
            likes=u.get("likes", 0),
            replies=u.get("replies", 0),
        )
        for i, u in enumerate(users)
    ]


@app.get("/miniapp", response_class=HTMLResponse)
def serve_miniapp():
    """Serve Mini App HTML."""
    html_path = Path(__file__).parent / "bagworker_miniapp.html"
    if not html_path.exists():
        raise HTTPException(status_code=404, detail="Mini App not found")
    return html_path.read_text(encoding="utf-8")


@app.get("/gallery/{brand}")
def get_gallery(brand: str, limit: int = 20):
    """Get images for a brand gallery."""
    if brand not in ("kilroy", "spong", "motion"):
        raise HTTPException(status_code=400, detail="Invalid brand (kilroy/spong/motion)")

    from .config import PROJECTS_ROOT

    refs_dir = PROJECTS_ROOT / brand / "references"
    index_path = refs_dir / "index.json"

    if not index_path.exists():
        return []

    try:
        entries = json.loads(index_path.read_text(encoding="utf-8"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read index: {e}")

    entries.sort(key=lambda e: e.get("added_at", ""), reverse=True)
    entries = entries[:limit]

    result = []
    for e in entries:
        fname = e.get("filename") or e.get("id", "")
        img_path = refs_dir / fname
        if img_path.exists():
            result.append({
                "id": e["id"],
                "url": f"/images/{brand}/{fname}",
                "tags": e.get("tags", [])[:5],
                "notes": (e.get("notes") or "")[:80],
            })
    return result


@app.get("/images/{brand}/{filename}")
def serve_image(brand: str, filename: str):
    """Serve image file (prevent directory traversal)."""
    from .config import PROJECTS_ROOT

    safe_name = Path(filename).name
    img_path = PROJECTS_ROOT / brand / "references" / safe_name

    if not img_path.exists():
        raise HTTPException(status_code=404)

    return FileResponse(str(img_path))


@app.get("/raid/{raid_id}")
def get_raid(raid_id: str):
    """Get raid metadata for Mini App."""
    posts = db.posts_recent(limit=1000)
    post = next((p for p in posts if p["post_id"] == raid_id), None)
    if not post:
        raise HTTPException(status_code=404, detail="Raid not found")
    return post


@app.get("/tracker/{raid_id}")
def get_raid_tracker(raid_id: str):
    """Get tracker data: who clicked what in this raid."""
    actions = db._read_jsonl(db.actions_file)
    raid_actions = [a for a in actions if a.get("post_id") == raid_id or a.get("raid_id") == raid_id]

    if not raid_actions:
        return []

    # Group by user
    by_user = {}
    for a in raid_actions:
        uid = a["user_tg_id"]
        if uid not in by_user:
            user = db.user_get(uid)
            by_user[uid] = {
                "user_tg_id": uid,
                "username": (user or {}).get("username", f"user_{uid}"),
                "actions": [],
                "images_used": set(),
            }
        by_user[uid]["actions"].append(a)
        if a.get("image_id"):
            by_user[uid]["images_used"].add(a["image_id"])

    # Flatten sets to lists for JSON serialization
    result = []
    for uid, u in by_user.items():
        u["images_used"] = list(u["images_used"])
        result.append(u)

    return result


@app.get("/health")
def health():
    """Health check."""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
