# Anti-Hacked-Account Discord Bot

Kicks accounts that show the typical "compromised account" behavior: posting the **same message in multiple channels** within a short window, usually with an **@everyone / @here** ping.

## How it works

1. Every message containing `@everyone` or `@here` is fingerprinted (text normalized + attachment names/sizes, so image scams are caught too).
2. If the same user posts the same fingerprint in **3+ different channels within 60 seconds**, the bot:
   - DMs them that their account looks compromised
   - Kicks them and deletes the spam messages (they can rejoin once their account is secured)
   - Posts a summary to your mod-log channel

The ping check counts the text even if the ping didn't go through, since hacked accounts often lack permission to actually ping everyone.

## Setup

1. **Create the bot** at https://discord.com/developers/applications → New Application → Bot → Reset Token (copy it).
2. On the **Bot** page, enable **Message Content Intent** and **Server Members Intent**.
3. **Invite it**: OAuth2 → URL Generator → scope `bot`, permissions **Kick Members**, **Manage Messages**, **View Channels**, **Read Message History**, **Send Messages**, **Embed Links**. Open the generated URL and add it to your server.
4. In Server Settings → Roles, **drag the bot's role above your normal member roles** — it can't kick anyone whose role is equal or higher.
5. Install and run:
   ```bash
   pip install -r requirements.txt
   cp .env.example .env      # then paste your token in .env
   python bot.py
   ```

## `.env` settings

| Setting | What it's for |
|---|---|
| `DISCORD_TOKEN` | Your bot token (required) |
| `LOG_CHANNEL_ID` | Channel where kick reports are posted. Leave blank for none. |
| `EXEMPT_ROLE_IDS` | Comma-separated role IDs that are never kicked, e.g. your mod roles |

To get an ID, enable Developer Mode (User Settings → Advanced), then right-click the channel or role → Copy ID. Everything else (3 channels in 60 seconds, ping required, kick, DM) is fixed in the code.

## Hosting

The bot needs to run 24/7 to protect the server — a VPS, a Raspberry Pi, or a host like Railway / fly.io works. Restarts only reset the short in-memory tracking window, nothing else is stored.
