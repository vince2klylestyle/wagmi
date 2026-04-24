# Bagworker Raid Platform

Complete TG Mini App-based bagworker coordination system. Operator forwards X links to a private group → bot broadcasts Mini App → members tap to raid (Like/RT/Reply with images) → every action tracked with points and leaderboard.

## Quick Start

### Prerequisites
- Python 3.10+
- Telegram bot token (from @BotFather)
- Cloudflare account (free tier) for HTTPS tunnel
- X/Twitter account with API access (for caching tweets)

### 1. Deployment Setup

**Install Cloudflare Tunnel:**
```bash
winget install Cloudflare.cloudflared
cloudflared login
cloudflared tunnel create bagworker
cloudflared tunnel route dns bagworker bagworker.yourdomain.com
```

**Configure .env:**
```bash
BAGWORKER_URL=https://bagworker.yourdomain.com
MEMEGINE_TELEGRAM_BOT_TOKEN=<your-bot-token>
MEMEGINE_TELEGRAM_ALLOWED_CHAT_IDS=<group-id>  # negative number
```

### 2. Start Services (3 terminals)

**Terminal 1: Main bot**
```bash
python -m memegine serve
```

**Terminal 2: Bagworker API server**
```bash
python -m uvicorn memegine.bagworker_server:app --host 0.0.0.0 --port 8000
```

**Terminal 3: Cloudflare tunnel**
```bash
cloudflared tunnel run bagworker
```

### 3. Register Mini App with BotFather
- Talk to @BotFather on Telegram
- Use `/newapp` command
- Set app name and description
- Set web app URL to: `https://bagworker.yourdomain.com/miniapp`

### 4. Test the Flow
1. Forward an X/Twitter link to your group
2. Bot detects URL and broadcasts "RAID LAUNCHED" with WebApp button
3. Members tap button → Mini App opens in TG
4. Pick brand (Kilroy/Spong/Motion) and image
5. Tap action (RT/Like/Reply) → opens X intent + logs click
6. In your group, run `/tracker` to see who raided what
7. Run `/leaderboard` to see top raiders

## Commands

### Operator Commands
- `/raid <url> [brand]` — Explicit raid creation (brand: kilroy/spong/motion)
- `/tracker` — Show who did what on latest raid
- `/broadcast` — Re-send active raid to group
- `/leaderboard [limit]` — Top raiders

### Member Commands
- `/miniapp` — Send Mini App link
- `/stats` — Show your points and rank

## Architecture

### Flow
```
User forwards X URL to group
    ↓
telegram_ops.on_url_message() detects URL (existing)
    ↓
bagworker_bot.handle_url_as_raid() creates raid + broadcasts
    ↓
Member taps WebApp button
    ↓
Mini App (bagworker_miniapp.html) loads in TG WebView
    ↓
Fetches /raid/{raid_id} → tweet card
Fetches /gallery/{brand} → image gallery
    ↓
Member picks image + taps action
    ↓
Mini App calls tg.openLink() to X intent URL (opens X app/web)
Mini App POSTs to /engage with image_id
    ↓
Server logs to JSONL, awards points
    ↓
User runs /tracker to review clicks + manually reward
```

### Database (JSONL-based)
- `data/bagworker_db/users.jsonl` — User profiles with points, streaks, speed bonuses
- `data/bagworker_db/posts.jsonl` — Raids with tweet metadata
- `data/bagworker_db/actions.jsonl` — Click log (user, action, image, timestamp, points)

No SQL needed. Scales to 1000+ users with simple file-based storage.

## API Endpoints

### Mini App
- `GET /miniapp` → Serves HTML for TG WebApp

### Raids
- `POST /post` → Create raid from text
- `GET /posts [limit=10]` → List recent raids
- `GET /raid/{raid_id}` → Get raid metadata (tweet, handle, text, brand)

### Gallery
- `GET /gallery/{brand} [limit=20]` → Image list for brand
- `GET /images/{brand}/{filename}` → Serve image file

### Engagement
- `POST /auth` → User auth (TG data)
- `POST /engage` → Log click (retweet/like/reply) + award points
- `GET /user/{tg_id}` → User stats
- `GET /leaderboard [limit=10]` → Top users by points
- `GET /tracker/{raid_id}` → Who clicked what in raid

## Schemas

### User
```json
{
  "tg_id": 123456,
  "username": "user",
  "points": 100,
  "retweets": 5,
  "likes": 10,
  "replies": 2,
  "streak_days": 3,
  "speed_bonuses": 2,
  "last_raid_at": "2026-04-21T12:34:56.789",
  "created_at": "2026-04-20T08:00:00"
}
```

### Post (Raid)
```json
{
  "post_id": "raid_12345",
  "text": "tweet text",
  "tweet_id": "12345",
  "tweet_url": "https://x.com/user/status/12345",
  "x_handle": "user",
  "brand": "spong",
  "created_at": "2026-04-21T12:00:00",
  "raid_count": 5
}
```

### Action
```json
{
  "post_id": "raid_12345",
  "user_tg_id": 123456,
  "action_type": "retweet",
  "image_id": "spong_abc123",
  "image_brand": "spong",
  "points_earned": 5,
  "timestamp": "2026-04-21T12:05:00"
}
```

## Points System

| Action | Points | Speed Bonus |
|--------|--------|------------|
| Like | 2 | +0 |
| Retweet | 5 | +3 (if < 5 min) |
| Reply | 10 | +3 (if < 5 min) |

**Streaks:** Consecutive days with at least one raid. Track user engagement.

**Speed Bonus:** +3 pts if action within 5 minutes of raid creation. Rewards fast raiders.

## Image Galleries

Stored in `data/projects/{brand}/references/` with semantic index:

### Spong
- 85+ images indexed
- Tags: spong, face, object, mood, setting, color
- Auto-indexed from memedepot library

### Motion
- 235+ images indexed
- Tags: motion, effect, transition, animation, style

### Kilroy
- 0+ images (bootstrap from your kilroy_compositor.py output)
- Tags: kilroy, graffiti, location, style
- Bootstrap script: `python -c "from memegine.kilroy_bootstrap import bootstrap; bootstrap()"`

Index format (index.json):
```json
[
  {
    "id": "spong_123",
    "filename": "spong_123.jpg",
    "tags": ["spong", "face", "happy"],
    "source": "memedepot",
    "notes": "Character smiling",
    "added_at": "2026-04-20T08:00:00"
  }
]
```

## Configuration

### Environment Variables
```bash
BAGWORKER_URL=https://bagworker.yourdomain.com  # REQUIRED
MEMEGINE_TELEGRAM_BOT_TOKEN=<token>
MEMEGINE_TELEGRAM_ALLOWED_CHAT_IDS=-123456789  # Group ID (negative)
```

### Config File (config.py)
- `bagworker_url` — Mini App server URL (must be HTTPS for TG)
- `data_root` — Base data directory
- `data_dir` — Project-specific data dir

## Testing

Run integration tests:
```bash
python -m pytest tests/test_bagworker_integration.py -v
```

Tests cover:
- Database path resolution
- Tweet metadata schema
- Image tracking
- Streak logic
- All server endpoints

## Troubleshooting

### Mini App won't open
- Verify `BAGWORKER_URL` is HTTPS (TG requires it)
- Check BotFather has correct URL registered
- Verify tunnel is running: `cloudflared tunnel run bagworker`

### Images not showing in gallery
- Check `data/projects/{brand}/references/` has images
- For kilroy: run `python -c "from memegine.kilroy_bootstrap import bootstrap; bootstrap()"`
- Verify index.json exists and is valid JSON

### X deep links not opening
- On Android: TG Mini App sandbox only allows `tg.openLink()` (used by Mini App)
- On iOS: Same behavior
- Fallback: Links work on desktop browsers

### Click not logged
- Check bagworker server is running on port 8000
- Verify `/engage` endpoint responds: `curl -X POST http://localhost:8000/engage -H "Content-Type: application/json" -d '{"post_id":"raid_1","user_tg_id":1,"action_type":"like"}'`

## Future Enhancements (Phase 6-7)

1. **Kilroy Gallery**: Bootstrap with 20+ kilroy compositor outputs
2. **Motion Gallery**: Index all Motion images with semantic tags
3. **Raid Notifications**: `/raid @user` pings specific bagworkers
4. **Rewards Dashboard**: Web interface for manual reward distribution
5. **Analytics**: Daily raid volume, engagement per brand, top performers
6. **Tier System**: Bronze/Silver/Gold based on points
7. **Seasonal Resets**: Monthly leaderboard restart

## Architecture Files

- `src/memegine/bagworker_api.py` — Database layer
- `src/memegine/bagworker_server.py` — FastAPI server
- `src/memegine/bagworker_bot.py` — TG bot handlers
- `src/memegine/bagworker_miniapp.html` — Mobile Mini App
- `src/memegine/kilroy_bootstrap.py` — Kilroy indexer
- `tests/test_bagworker_integration.py` — Integration tests

## Support

For bugs or feature requests, see CLAUDE.md for skills and debugging tools.
