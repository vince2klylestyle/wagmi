"""Telegram bot handler for bagworker raids.

Handles:
- /post <text> — create a raid post
- /raid <url> [brand] — explicit raid creation
- /tracker — show who raided what
- /broadcast — re-send active raid to group
- /stats — user stats
- /leaderboard — top users
- /miniapp — send link to Mini App
"""
from __future__ import annotations

import json
import re
from html import unescape
from urllib.parse import quote

from .bagworker_api import db


async def handle_post_command(update, context):
    """Handle /post command to create a raid.

    Usage: /post "tweet text here"
    """
    if not context.args:
        await update.message.reply_text(
            "Usage: /post \"tweet text\"\n\n"
            "Example: /post \"just realized i'm actually a genius trader\""
        )
        return

    # Get the tweet text
    text = " ".join(context.args)
    text = text.strip('\'"')  # Remove quotes if present

    if not text:
        await update.message.reply_text("Tweet text cannot be empty")
        return

    # Create the post in database
    post_id = f"post_{update.message.message_id}_{update.message.from_user.id}"
    post = db.post_create(
        post_id=post_id,
        text=text,
        created_by_tg_id=update.message.from_user.id,
    )

    # Send confirmation
    await update.message.reply_text(
        f"✅ **New Raid Posted!**\n\n"
        f"_\"{text[:100]}...\"_\n\n"
        f"Bagworkers can raid this on the mini app now!\n\n"
        f"[Open Raid Dashboard](https://your-domain.com/miniapp)"
    )


async def handle_forward_message(update, context):
    """Handle forwarded messages (tweets) to auto-create raids.

    When someone forwards a tweet or paste text, create a raid from it.
    """
    if not update.message:
        return

    # Get the message text
    text = update.message.text or update.message.caption or ""
    if not text:
        return

    # Skip if it's a command
    if text.startswith("/"):
        return

    # Extract tweet-like text (first 280 chars)
    text = text[:280].strip()

    if len(text) < 10:
        return  # Skip very short messages

    # Create post from forwarded message
    post_id = f"post_{update.message.message_id}_{update.message.from_user.id}"
    post = db.post_create(
        post_id=post_id,
        text=text,
        created_by_tg_id=update.message.from_user.id,
    )

    # Send confirmation reaction or reply
    await update.message.reply_text(
        f"🎯 Added to raids!\n\n"
        f"Bagworkers can raid this now.",
        reply_to_message_id=update.message.message_id,
    )


async def handle_miniapp_command(update, context):
    """Handle /miniapp command to send Mini App link."""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
    from .config import settings

    tg_id = update.message.from_user.id
    username = update.message.from_user.username or f"user_{tg_id}"

    # Get latest raid to use as default, or show generic link
    posts = db.posts_recent(limit=1)
    raid_id = posts[0]["post_id"] if posts else "latest"

    miniapp_url = f"{settings.bagworker_url}/miniapp?raid={raid_id}"

    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("Open Raid Dashboard", web_app=WebAppInfo(url=miniapp_url))
    ]])

    await update.message.reply_text(
        f"🎯 **Bagworker Raid Dashboard**\n\n"
        f"Your account: @{username}\n"
        f"Tap button to open dashboard.",
        reply_markup=kb,
        parse_mode="Markdown",
    )


async def handle_stats_command(update, context):
    """Handle /stats command to show user stats."""
    tg_id = update.message.from_user.id
    user = db.user_get(tg_id)

    if not user:
        await update.message.reply_text(
            "You don't have an account yet. "
            "Use /miniapp to create one!"
        )
        return

    leaderboard = db.leaderboard(limit=1000)
    rank = next(
        (i + 1 for i, u in enumerate(leaderboard) if u["tg_id"] == tg_id),
        len(leaderboard) + 1,
    )

    stats = (
        f"📊 **Your Stats**\n\n"
        f"👤 @{user['username']}\n"
        f"🏆 Rank: #{rank}\n"
        f"💰 Points: {user.get('points', 0)}\n\n"
        f"📈 Engagements:\n"
        f"  🔄 Retweets: {user.get('retweets', 0)}\n"
        f"  ❤️ Likes: {user.get('likes', 0)}\n"
        f"  💬 Replies: {user.get('replies', 0)}"
    )

    await update.message.reply_text(stats, parse_mode="Markdown")


async def handle_leaderboard_command(update, context):
    """Handle /leaderboard command to show top users."""
    leaderboard = db.leaderboard(limit=10)

    lines = ["🏆 **Top Bagworkers**\n"]
    for i, user in enumerate(leaderboard, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"#{i}"
        lines.append(
            f"{medal} @{user['username']} — {user.get('points', 0)} pts "
            f"({user.get('retweets', 0)}🔄 {user.get('likes', 0)}❤️)"
        )

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def handle_help_command(update, context):
    """Handle /help command."""
    help_text = (
        "🎯 **Bagworker Raid System**\n\n"
        "**Commands:**\n"
        "/post \"text\" — Create a raid\n"
        "/miniapp — Open dashboard\n"
        "/stats — Your stats\n"
        "/leaderboard — Top 10\n"
        "/help — This message\n\n"
        "**How it works:**\n"
        "1. Post raids with /post or forward messages\n"
        "2. Bagworkers raid on Twitter/X\n"
        "3. Earn points for engagement\n"
        "4. Climb the leaderboard\n"
        "5. Win rewards!"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def handle_url_as_raid(update, context):
    """Handle X URLs detected in messages — create bagworker raid."""
    from .ops_db import ops_db
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
    from .config import settings

    if not update.message or not update.message.text:
        return

    # Extract URL from message
    text = update.message.text
    url_re = re.compile(r"https?://(?:www\.)?(?:twitter|x)\.com/[^/\s]+/status/(\d+)")
    match = url_re.search(text)
    if not match:
        return

    url = match.group(0)
    tweet_id = match.group(1)

    # Try to get tweet from ops_db cache
    try:
        tweet_data = ops_db.get_tweet(tweet_id)
        if not tweet_data:
            return
    except Exception:
        return

    # Determine brand from context (default to spong)
    brand = "spong"
    if "kilroy" in text.lower():
        brand = "kilroy"
    elif "motion" in text.lower():
        brand = "motion"

    # Create raid
    post_id = f"raid_{tweet_id}"
    post = db.post_create(
        post_id=post_id,
        text=tweet_data.get("text", "")[:280],
        created_by_tg_id=update.message.from_user.id,
        tweet_id=tweet_id,
        tweet_url=url,
        x_handle=tweet_data.get("author_handle", ""),
        brand=brand,
    )

    # Broadcast WebApp button to group
    miniapp_url = f"{settings.bagworker_url}/miniapp?raid={post_id}"
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🎯 Raid", web_app=WebAppInfo(url=miniapp_url))
    ]])

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=(
            f"🚀 RAID LAUNCHED\n\n"
            f"@{tweet_data.get('author_handle', '?')}\n"
            f"{tweet_data.get('text', '')[:150]}\n\n"
            f"Brand: {brand.upper()}\n"
            f"Tap to raid and earn points!"
        ),
        reply_markup=kb,
    )


async def handle_raid_command(update, context):
    """Handle /raid <url> [brand] command."""
    from .ops_db import ops_db
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
    from .config import settings

    args = context.args or []
    if not args:
        await update.message.reply_text("Usage: /raid <tweet_url> [kilroy|spong|motion]")
        return

    url = args[0]
    brand = next((a for a in args[1:] if a in ("kilroy", "spong", "motion")), "spong")

    # Extract tweet ID
    url_re = re.compile(r"https?://(?:www\.)?(?:twitter|x)\.com/[^/\s]+/status/(\d+)")
    match = url_re.search(url)
    if not match:
        await update.message.reply_text("Invalid X URL")
        return

    tweet_id = match.group(1)

    # Get tweet data
    try:
        tweet_data = ops_db.get_tweet(tweet_id)
        if not tweet_data:
            await update.message.reply_text("Could not fetch tweet (not in cache)")
            return
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")
        return

    # Create raid
    post_id = f"raid_{tweet_id}"
    post = db.post_create(
        post_id=post_id,
        text=tweet_data.get("text", "")[:280],
        created_by_tg_id=update.message.from_user.id,
        tweet_id=tweet_id,
        tweet_url=url,
        x_handle=tweet_data.get("author_handle", ""),
        brand=brand,
    )

    # Broadcast WebApp button
    miniapp_url = f"{settings.bagworker_url}/miniapp?raid={post_id}"
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🎯 Raid", web_app=WebAppInfo(url=miniapp_url))
    ]])

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=(
            f"🚀 RAID LAUNCHED\n\n"
            f"@{tweet_data.get('author_handle', '?')}\n"
            f"{tweet_data.get('text', '')[:150]}\n\n"
            f"Brand: {brand.upper()}\n"
            f"Tap to raid and earn points!"
        ),
        reply_markup=kb,
    )

    await update.message.reply_text("✅ Raid created and broadcast!")


async def handle_tracker_command(update, context):
    """Handle /tracker command — show latest raid stats."""
    posts = db.posts_recent(limit=1)
    if not posts:
        await update.message.reply_text("No raids yet")
        return

    latest = posts[0]
    raid_id = latest["post_id"]

    actions = db._read_jsonl(db.actions_file)
    raid_actions = [a for a in actions if a.get("post_id") == raid_id]

    if not raid_actions:
        await update.message.reply_text(f"No actions yet for raid {raid_id}")
        return

    # Group by user and action type
    summary = {}
    for a in raid_actions:
        uid = a["user_tg_id"]
        if uid not in summary:
            user = db.user_get(uid)
            summary[uid] = {
                "username": (user or {}).get("username", f"user_{uid}"),
                "retweets": 0,
                "likes": 0,
                "replies": 0,
                "images": set(),
            }
        summary[uid][a["action_type"] + "s"] += 1
        if a.get("image_id"):
            summary[uid]["images"].add(a["image_id"])

    lines = [f"📊 Tracker for @{latest.get('x_handle', '?')}\n"]
    for uid, s in sorted(
        summary.items(),
        key=lambda x: x[1]["retweets"] * 5 + x[1]["likes"] * 2 + x[1]["replies"] * 10,
        reverse=True,
    ):
        lines.append(
            f"@{s['username']}: "
            f"{s['retweets']}🔄 {s['likes']}❤️ {s['replies']}💬 "
            f"({len(s['images'])} images)"
        )

    await update.message.reply_text("\n".join(lines))


async def handle_broadcast_command(update, context):
    """Handle /broadcast — re-send active raid to group."""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
    from .config import settings

    posts = db.posts_recent(limit=1)
    if not posts:
        await update.message.reply_text("No active raids")
        return

    post = posts[0]
    miniapp_url = f"{settings.bagworker_url}/miniapp?raid={post['post_id']}"
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🎯 Raid", web_app=WebAppInfo(url=miniapp_url))
    ]])

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=(
            f"🔔 Active raid: @{post.get('x_handle', '?')}\n"
            f"Tap to raid and earn points!"
        ),
        reply_markup=kb,
    )

    await update.message.reply_text("✅ Raid re-broadcast!")


def register_bagworker_handlers(app, cfg):
    """Register handlers with the TG bot application.

    Usage in telegram_bot.py build_application():
        from memegine.bagworker_bot import register_bagworker_handlers
        bagworker_bot.register_bagworker_handlers(app, cfg)
    """
    from telegram.ext import CommandHandler, MessageHandler, filters

    # Command handlers
    app.add_handler(CommandHandler("post", handle_post_command))
    app.add_handler(CommandHandler("raid", handle_raid_command))
    app.add_handler(CommandHandler("tracker", handle_tracker_command))
    app.add_handler(CommandHandler("broadcast", handle_broadcast_command))
    app.add_handler(CommandHandler("miniapp", handle_miniapp_command))
    app.add_handler(CommandHandler("stats", handle_stats_command))
    app.add_handler(CommandHandler("leaderboard", handle_leaderboard_command))
    app.add_handler(CommandHandler("help", handle_help_command))

    # X URL handler (specific, runs at group=2 after ops handlers)
    url_re = re.compile(r"https?://(?:www\.)?(?:twitter|x)\.com/[^/\s]+/status/\d+", re.I)
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.Regex(url_re),
            handle_url_as_raid,
        ),
        group=2,  # Runs after ops handlers (group 0-1)
    )

    # Forward message handler (catch non-URL text — optional)
    # REMOVED to avoid catching all text — uncomment if needed
    # app.add_handler(
    #     MessageHandler(
    #         filters.TEXT & ~filters.COMMAND & ~filters.Regex(url_re),
    #         handle_forward_message,
    #     )
    # )
