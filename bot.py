import discord
from discord.ext import commands
import os

# ── Configuration ──────────────────────────────────────────────────────────────
TOKEN = os.getenv("DISCORD_TOKEN")  # Set this in your environment or .env file

# Maps command name → role name (role must already exist in your Discord server)
ROLE_COMMANDS = {
    "uo":  "UO",
    "osu": "OSU",
    "psu": "PSU",
    "sou": "SOU",
    "oit": "OIT",
    "wou": "WOU",
    "lc":  "L&C",
    "up":  "UP",
    "gf":  "GF",
    "cc":  "CC",
    "eou": "EOU",
    "pac": "Pacific",
    "bush": "Bushnell",
    "will": "Willamette",
    "lin": "Linfield",
    "cor": "Corban",
}

# The set of role names considered "claimed" roles
CLAIMED_ROLE_NAMES = set(ROLE_COMMANDS.values())

# ── Bot setup ──────────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)


def get_claimed_role(member: discord.Member) -> discord.Role | None:
    """Return the first claimed role the member already has, or None."""
    for role in member.roles:
        if role.name in CLAIMED_ROLE_NAMES:
            return role
    return None


async def assign_role(ctx: commands.Context, role_name: str):
    """Core logic: check eligibility, then assign the role."""
    member = ctx.author

    # 1. Check if user already has one of the managed roles
    existing = get_claimed_role(member)
    if existing:
        await ctx.reply(
            f"❌ You already have the **{existing.name}** role and cannot claim another one.",
            mention_author=True,
        )
        return

    # 2. Find the target role in the guild
    role = discord.utils.get(ctx.guild.roles, name=role_name)
    if role is None:
        await ctx.reply(
            f"⚠️ The role **{role_name}** doesn't exist on this server. "
            "Please ask an admin to create it.",
            mention_author=True,
        )
        return

    # 3. Assign the role
    try:
        await member.add_roles(role, reason="Self-assigned via bot command")
        await ctx.reply(
            f"✅ You've been given the **{role_name}** role! "
            "You cannot claim any additional roles.",
            mention_author=True,
        )
    except discord.Forbidden:
        await ctx.reply(
            "⚠️ I don't have permission to assign roles. "
            "Please ask an admin to move my role above the managed roles.",
            mention_author=True,
        )
    except discord.HTTPException as e:
        await ctx.reply(f"⚠️ Something went wrong: {e}", mention_author=True)


# ── Dynamically register one command per role ──────────────────────────────────
for cmd_name, role_name in ROLE_COMMANDS.items():
    # Use a closure to capture the correct role_name for each iteration
    def make_command(rn):
        async def role_command(ctx):
            await assign_role(ctx, rn)
        role_command.__name__ = cmd_name
        return role_command

    bot.command(name=cmd_name)(make_command(role_name))


# ── Events ─────────────────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")
    print(f"   Managing {len(ROLE_COMMANDS)} role commands: {', '.join('!' + c for c in ROLE_COMMANDS)}")


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return  # Silently ignore unknown commands
    raise error


# ── Run ────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if not TOKEN:
        raise ValueError("DISCORD_TOKEN environment variable is not set.")
    bot.run(TOKEN)
