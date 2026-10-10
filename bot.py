"""
Anti-compromised-account bot.

Detects the classic "hacked account" pattern: the same message (usually with an
@everyone / @here ping) posted in several channels within a short time window,
then kicks the account and cleans up the spam.
"""

import hashlib
import logging
import os
import time
from collections import defaultdict

import discord
from dotenv import load_dotenv

load_dotenv()

# ---------- From .env ----------
TOKEN = os.getenv("DISCORD_TOKEN")
# Channel for kick reports (blank = no reports)
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", "").strip() or 0) or None
# Comma-separated role IDs that are never kicked (e.g. mods)
EXEMPT_ROLE_IDS = {int(x) for x in os.getenv("EXEMPT_ROLE_IDS", "").split(",") if x.strip()}

# ---------- Behavior (fixed) ----------
CHANNEL_THRESHOLD = 3          # same message in this many different channels...
WINDOW_SECONDS = 60            # ...within this many seconds triggers a kick
REQUIRE_PING = True            # only count messages containing @everyone / @here
EXEMPT_ADMINS = True           # never kick members with Administrator permission
DM_USER = True                 # DM the user that their account looks hacked

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("antihack")

intents = discord.Intents.default()
intents.message_content = True   # must also be enabled in the Developer Portal
intents.members = True
client = discord.Client(intents=intents)

# (guild_id, user_id) -> {fingerprint: [(timestamp, message), ...]}
recent: dict[tuple[int, int], dict[str, list[tuple[float, discord.Message]]]] = defaultdict(
    lambda: defaultdict(list)
)
# users currently being actioned, so we don't fire twice
handling: set[tuple[int, int]] = set()


def fingerprint(message: discord.Message) -> str | None:
    """Normalize a message's text + attachments into a comparable hash."""
    text = " ".join(message.content.lower().split())
    files = sorted(f"{a.filename}:{a.size}" for a in message.attachments)
    if not text and not files:
        return None
    raw = text + "|" + ",".join(files)
    return hashlib.sha256(raw.encode()).hexdigest()


def has_mass_ping(message: discord.Message) -> bool:
    # mention_everyone is only True if the ping actually went through, so also
    # check the raw text — hacked accounts often lack permission to ping.
    content = message.content
    return message.mention_everyone or "@everyone" in content or "@here" in content


def is_exempt(member: discord.Member) -> bool:
    if member.bot or member == member.guild.owner:
        return True
    if EXEMPT_ADMINS and member.guild_permissions.administrator:
        return True
    return any(r.id in EXEMPT_ROLE_IDS for r in member.roles)


async def log_to_channel(guild: discord.Guild, embed: discord.Embed) -> None:
    if not LOG_CHANNEL_ID:
        return
    channel = guild.get_channel(LOG_CHANNEL_ID)
    if channel:
        try:
            await channel.send(embed=embed)
        except discord.HTTPException as e:
            log.warning("Could not send to log channel: %s", e)


async def delete_messages(messages: list[discord.Message]) -> None:
    for m in messages:
        try:
            await m.delete()
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass


async def punish(member: discord.Member, messages: list[discord.Message]) -> None:
    guild = member.guild
    key = (guild.id, member.id)
    if key in handling:
        return
    handling.add(key)

    channels = sorted({m.channel.id for m in messages})
    preview = messages[0].content[:500] or "(attachment only)"
    reason = f"Compromised account: identical message spammed in {len(channels)} channels"

    try:
        me = guild.me
        if member.top_role >= me.top_role:
            log.warning("Can't kick %s: their role is above or equal to mine", member)
            await log_to_channel(guild, discord.Embed(
                title="⚠️ Spam detected but couldn't act",
                description=f"{member.mention} (`{member.id}`) — their top role is at or above the bot's. "
                            f"Move the bot's role higher.",
                color=discord.Color.orange(),
            ))
            await delete_messages(messages)
            return

        if DM_USER:
            try:
                await member.send(
                    f"You were kicked from **{guild.name}** because your account posted the same message "
                    f"in multiple channels, which usually means it has been compromised. "
                    f"Change your password, enable 2FA, and revoke unknown sessions/apps — "
                    f"then you're welcome to rejoin."
                )
            except (discord.Forbidden, discord.HTTPException):
                pass

        # Kick first so the account can't keep posting, then clean up the spam.
        await member.kick(reason=reason)
        await delete_messages(messages)

        log.info("Kicked %s (%s) in %s", member, member.id, guild.name)

        embed = discord.Embed(
            title="👢 Compromised account kicked",
            color=discord.Color.red(),
        )
        embed.add_field(name="User", value=f"{member.mention}\n`{member}` (`{member.id}`)", inline=False)
        embed.add_field(name="Channels", value=" ".join(f"<#{c}>" for c in channels)[:1024], inline=False)
        embed.add_field(name="Message", value=preview[:1024], inline=False)
        await log_to_channel(guild, embed)

    except discord.Forbidden:
        log.error("Missing permissions to kick %s", member)
    except discord.HTTPException as e:
        log.error("Failed to kick %s: %s", member, e)
    finally:
        recent.pop(key, None)
        handling.discard(key)


@client.event
async def on_ready():
    log.info("Logged in as %s — watching %d server(s)", client.user, len(client.guilds))
    log.info("Trigger: same message in %d channels within %ds (ping required: %s) -> kick",
             CHANNEL_THRESHOLD, WINDOW_SECONDS, REQUIRE_PING)


@client.event
async def on_message(message: discord.Message):
    if message.guild is None or not isinstance(message.author, discord.Member):
        return
    if is_exempt(message.author):
        return
    if REQUIRE_PING and not has_mass_ping(message):
        return

    fp = fingerprint(message)
    if fp is None:
        return

    key = (message.guild.id, message.author.id)
    now = time.monotonic()
    user_msgs = recent[key]

    # drop entries outside the window
    for f in list(user_msgs):
        user_msgs[f] = [(t, m) for t, m in user_msgs[f] if now - t <= WINDOW_SECONDS]
        if not user_msgs[f]:
            del user_msgs[f]

    user_msgs[fp].append((now, message))
    entries = user_msgs[fp]
    distinct_channels = {m.channel.id for _, m in entries}

    if len(distinct_channels) >= CHANNEL_THRESHOLD:
        await punish(message.author, [m for _, m in entries])


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("Set DISCORD_TOKEN in your .env file")
    client.run(TOKEN, log_handler=None)
