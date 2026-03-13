import discord
from discord import app_commands
from discord.ui import Button, View
import json
import os
from datetime import datetime
from dotenv import load_dotenv

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
        "button_style": discord.ButtonStyle.success,
    },
    "updating": {
        "label": "🟡 Frostbot — Updating",
        "color": discord.Color.yellow(),
        "button_style": discord.ButtonStyle.secondary,
    },
    "offline": {
        "label": "🔴 Frostbot — Offline",
        "color": discord.Color.red(),
        "button_style": discord.ButtonStyle.danger,
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
        title="📊 Frostbot Status",
        description="Official status panel for Frostbot.\n━━━━━━━━━━━━━━━━━━━━",
        color=cfg["color"],
    )
    embed.add_field(name="Current Status", value=cfg["label"], inline=False)
    embed.set_footer(text=f"Last updated: {now}")

    if THUMBNAIL_URL:
        embed.set_thumbnail(url=THUMBNAIL_URL)

    return embed


# ─────────────────────────────────────────
#  BUTTONS VIEW
# ─────────────────────────────────────────
class StatusView(View):
    def __init__(self):
        super().__init__(timeout=None)

    async def _handle_button(self, interaction: discord.Interaction, state: str):
        if interaction.user.id != OWNER_ID:
            await interaction.response.send_message(
                "You do not have permission to use this.", ephemeral=True
            )
            return
        await set_status(interaction.channel, state, respond=interaction)

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
#  CORE STATUS SETTER
# ─────────────────────────────────────────
async def set_status(
    channel: discord.TextChannel,
    state: str,
    respond: discord.Interaction | None = None,
) -> None:
    data = load_status()
    embed = build_embed(state)
    view  = StatusView()

    message_id = data.get("message_id")
    message    = None

    # Try to fetch the existing message
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

    if respond:
        await respond.response.send_message(
            f"Status updated to **{state}**.", ephemeral=True
        )


# ─────────────────────────────────────────
#  BOT SETUP
# ─────────────────────────────────────────
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
    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message(
            "You do not have permission to use this.", ephemeral=True
        )
        return

    channel = client.get_channel(CHANNEL_ID)
    if channel is None:
        await interaction.response.send_message(
            "Status channel not found. Check CHANNEL_ID in .env.", ephemeral=True
        )
        return

    await set_status(channel, state.value, respond=interaction)


@client.event
async def on_ready():
    # Register persistent view so buttons keep working after restart
    client.add_view(StatusView())

    # Sync slash commands globally
    await tree.sync()
    print("Bot is ready.")

    # Reload and refresh the status message on startup
    data    = load_status()
    channel = client.get_channel(CHANNEL_ID)
    if channel:
        await set_status(channel, data.get("state", "offline"))


# ─────────────────────────────────────────
#  RUN
# ─────────────────────────────────────────
client.run(TOKEN)
