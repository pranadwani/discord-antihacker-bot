# Anti-Hacked-Account Discord Bot

Kicks accounts that show the typical "compromised account" behavior

## How it works

1. Every message containing `@everyone` or `@here` is fingerprinted.
2. If the same user posts the same fingerprint in **3+ different channels within 60 seconds**, the bot:
   - DMs them that their account looks compromised
   - Kicks them and deletes the spam messages
   - Posts a summary to your mod-log channel

## Setup

1. Create the bot at https://discord.com/developers/applications → New Application → Bot → Reset Token.
2. On the Bot page, enable Message Content Intent and Server Members Intent.
3. Invite it: OAuth2 → URL Generator → scope `bot`, permissions Kick Members, Manage Messages, View Channels, Read Message History, Send Messages, Embed Links. Open the generated URL and add it to your server.
4. In Server Settings → Roles, drag the bot's role above your normal member roles.
5. Install and run:
   ```bash
   pip install -r requirements.txt
   cp .env.example .env      # then paste your token in .env
   python bot.py
   ```

## `.env` settings

1. DISCORD_TOKEN: Your bot token
2. LOG_CHANNEL_ID: Channel where kick reports are posted. Leave blank for none
3. EXEMPT_ROLE_IDS: Comma-separated role IDs that are never kicked

To get an ID, enable Developer Mode, then right-click the channel or role → Copy ID.
