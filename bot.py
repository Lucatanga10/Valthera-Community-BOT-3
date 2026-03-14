import discord
from discord import app_commands
from discord.ui import Button, View
import json
import os
import time
from datetime import datetime
from dotenv import load_dotenv
from server import keep_alive

# ─────────────────────────────────────────
#  LOAD ENVIRONMENT VARIABLES
# ─────────────────────────────────────────
load_dotenv()

TOKEN         = os.getenv("TOKEN")
CHANNEL_ID    = int(os.getenv("CHANNEL_ID"))
OWNER_ID      = int(os.getenv("OWNER_ID"))
THUMBNAIL_URL = os.getenv("THUMBNAIL_URL", "")

STATUS_FILE   = "status.json"

# ─────────────────────────────────────────
#  STATE CONFIG
# ─────────────────────────────────────────
STATE_CONFIG = {
    "online": {
        "label": "🟢 Frostbot — Online",
        "color": discord.Color.green(),
    },
    "updating": {
        "label": "🟡 Frostbot — Updating",
        "color": discord.Color.yellow(),
    },
    "offline": {
        "label": "🔴 Frostbot — Offline",
        "color": discord.Color.red(),
    },
}

# ─────────────────────────────────────────
#  JSON HELPERS
# ─────────────────────────────────────────
def load_status() -> dict:
    if os.path.exists(STATUS_FILE):
        with open(STATUS_FILE, "r") as f:
            return json.load(f)
    return {"state": "offline", "message_id": None}


def save_status(state: str, message_id: int | None) -> None:
    with open(STATUS_FILE, "w") as f:
        json.dump({"state": state, "message_id": message_id}, f, indent=4)


# ─────────────────────────────────────────
#  EMBED BUILDER
# ─────────────────────────────────────────
def build_embed(state: str) -> discord.Embed:
    cfg = STATE_CONFIG[state]
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    embed = discord.Embed(
        title="📡 Frostbot Status",
        description="Official status panel for Frostbot.\n━━━━━━━━━━━━━━━━━━━━",
        color=cfg["color"],
    )
    embed.add_field(name="Current Status", value=cfg["label"], inline=False)
    embed.set_footer(text=f"Last updated: {now}")

    if THUMBNAIL_URL:
        embed.set_thumbnail(url=THUMBNAIL_URL)

    return embed


# ─────────────────────────────────────────
#  CORE STATUS SETTER
# ─────────────────────────────────────────
async def set_status(channel: discord.TextChannel, state: str) -> None:
    data = load_status()
    embed = build_embed(state)
    view  = StatusView()

    message_id = data.get("message_id")
    message    = None

    if message_id:
        try:
            message = await channel.fetch_message(message_id)
        except (discord.NotFound, discord.HTTPException):
            message = None

    if message:
        await message.edit(embed=embed, view=view)
    else:
        message = await channel.send(embed=embed, view=view)

    save_status(state, message.id)


# ─────────────────────────────────────────
#  BUTTONS VIEW
# ─────────────────────────────────────────
class StatusView(View):
    def __init__(self):
        super().__init__(timeout=None)

    async def _handle_button(self, interaction: discord.Interaction, state: str):
        try:
            if interaction.user.id != OWNER_ID:
                await interaction.response.send_message(
                    "You do not have permission to use this.", ephemeral=True
                )
                return

            await interaction.response.defer(ephemeral=True)

            channel = interaction.client.get_channel(CHANNEL_ID)
            if channel is None:
                channel = await interaction.client.fetch_channel(CHANNEL_ID)

            await set_status(channel, state)
            await interaction.followup.send(f"Status updated to **{state}**.", ephemeral=True)

        except Exception as e:
            print(f"[ERROR] Button error: {e}")
            try:
                await interaction.followup.send("An error occurred. Please try again.", ephemeral=True)
            except Exception:
                pass

    @discord.ui.button(label="🟢 Set Online", style=discord.ButtonStyle.success, custom_id="btn_online")
    async def btn_online(self, interaction: discord.Interaction, button: Button):
        await self._handle_button(interaction, "online")

    @discord.ui.button(label="🟡 Set Updating", style=discord.ButtonStyle.secondary, custom_id="btn_updating")
    async def btn_updating(self, interaction: discord.Interaction, button: Button):
        await self._handle_button(interaction, "updating")

    @discord.ui.button(label="🔴 Set Offline", style=discord.ButtonStyle.danger, custom_id="btn_offline")
    async def btn_offline(self, interaction: discord.Interaction, button: Button):
        await self._handle_button(interaction, "offline")


# ─────────────────────────────────────────
#  BOT FACTORY
# ─────────────────────────────────────────
def create_bot():
    intents = discord.Intents.default()
    client  = discord.Client(intents=intents)
    tree    = app_commands.CommandTree(client)

    @tree.command(name="status", description="Update the Frostbot status panel.")
    @app_commands.describe(state="Choose the new status for Frostbot.")
    @app_commands.choices(state=[
        app_commands.Choice(name="online",   value="online"),
        app_commands.Choice(name="updating", value="updating"),
        app_commands.Choice(name="offline",  value="offline"),
    ])
    async def status_command(interaction: discord.Interaction, state: app_commands.Choice[str]):
        try:
            if interaction.user.id != OWNER_ID:
                await interaction.response.send_message(
                    "You do not have permission to use this.", ephemeral=True
                )
                return

            await interaction.response.defer(ephemeral=True)

            channel = client.get_channel(CHANNEL_ID)
            if channel is None:
                channel = await client.fetch_channel(CHANNEL_ID)

            await set_status(channel, state.value)
            await interaction.followup.send(f"Status updated to **{state.value}**.", ephemeral=True)

        except Exception as e:
            print(f"[ERROR] Command error: {e}")
            try:
                await interaction.followup.send("An error occurred.", ephemeral=True)
            except Exception:
                pass

    @client.event
    async def on_ready():
        client.add_view(StatusView())
        await tree.sync()
        print(f"✅ Bot is ready. Logged in as {client.user}")

        data = load_status()
        try:
            channel = client.get_channel(CHANNEL_ID)
            if channel is None:
                channel = await client.fetch_channel(CHANNEL_ID)
            await set_status(channel, data.get("state", "offline"))
        except Exception as e:
            print(f"[ERROR] on_ready set_status failed: {e}")

    return client


# ─────────────────────────────────────────
#  RUN
# ─────────────────────────────────────────
keep_alive()

# Wait before first connection to avoid Cloudflare rate limit on Render's shared IPs
print("Waiting 20 seconds before connecting to Discord...")
time.sleep(20)

MAX_RETRIES = 5
RETRY_DELAY = 60  # wait 60 seconds between retries

for attempt in range(1, MAX_RETRIES + 1):
    try:
        print(f"Connecting to Discord... (attempt {attempt}/{MAX_RETRIES})")
        bot = create_bot()
        bot.run(TOKEN, reconnect=True)
        break
    except Exception as e:
        print(f"[ERROR] Connection failed: {e}")
        if attempt < MAX_RETRIES:
            print(f"Retrying in {RETRY_DELAY} seconds...")
            time.sleep(RETRY_DELAY)
        else:
            print("Max retries reached. Exiting.")
