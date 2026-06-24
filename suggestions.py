"""
suggestions.py — drop-in feature for the Discord bot.

Adds:
  • !suggest <message>  — posts the suggestion to a suggestions channel
                          (showing who submitted it) and confirms to the user
  • A daily digest       — automatically posts a compiled, numbered list of the
                          day's suggestions at a set time
  • !digest              — admin-only, posts the digest immediately (for testing)

The digest reads suggestions back from the channel history, so a host restart
never loses the day's data.

──────────────────────────────────────────────────────────────────────────────
TO INSTALL — just two steps:

1. Put this file (suggestions.py) in the same folder as bot.py in your repo.

2. Add this block to bot.py, right ABOVE the final `bot.run(TOKEN)` line:

       @bot.event
       async def setup_hook():
           await bot.load_extension("suggestions")

   (If bot.py already has a setup_hook, just add the load_extension line inside it.)

3. On Railway → Variables, add:
       SUGGESTIONS_CHANNEL_ID   = <the channel where suggestions appear>
       DIGEST_CHANNEL_ID        = <the channel where the daily list posts>
   (Enable Developer Mode in Discord, then right-click a channel → Copy Channel ID.)
──────────────────────────────────────────────────────────────────────────────
"""

import os
import datetime
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands, tasks

# ── Configuration (pulled from Railway environment variables) ──────────────────
SUGGESTIONS_CHANNEL_ID = int(os.getenv("SUGGESTIONS_CHANNEL_ID", "0"))
DIGEST_CHANNEL_ID      = int(os.getenv("DIGEST_CHANNEL_ID", "0"))

# When to post the daily digest (Pacific time, 24-hour clock)
DIGEST_TIMEZONE = ZoneInfo("America/Los_Angeles")
DIGEST_HOUR     = 18   # 6 PM
DIGEST_MINUTE   = 0

# Hidden marker in the embed footer so the digest can identify suggestions
SUGGESTION_MARKER = "📌 Suggestion"


class Suggestions(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.daily_digest.start()

    def cog_unload(self):
        self.daily_digest.cancel()

    # ── !suggest ────────────────────────────────────────────────────────────────
    @commands.command(name="suggest")
    async def suggest(self, ctx, *, message: str = None):
        """Usage: !suggest your idea here"""
        if not message:
            await ctx.reply(
                "⚠️ Please include your suggestion, e.g. `!suggest add a new game mode`",
                mention_author=True,
            )
            return

        channel = self.bot.get_channel(SUGGESTIONS_CHANNEL_ID)
        if channel is None:
            await ctx.reply(
                "⚠️ The suggestions channel isn't configured correctly. Please tell an admin.",
                mention_author=True,
            )
            return

        embed = discord.Embed(
            description=message,
            color=discord.Color.blurple(),
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        embed.set_author(
            name=str(ctx.author.display_name),
            icon_url=ctx.author.display_avatar.url,
        )
        embed.set_footer(text=SUGGESTION_MARKER)

        await channel.send(embed=embed)
        await ctx.reply("✅ Thanks! Your suggestion has been submitted.", mention_author=True)

    # ── Digest builder ────────────────────────────────────────────────────────────
    async def build_and_post_digest(self):
        suggestions_channel = self.bot.get_channel(SUGGESTIONS_CHANNEL_ID)
        digest_channel      = self.bot.get_channel(DIGEST_CHANNEL_ID)

        if suggestions_channel is None or digest_channel is None:
            print("⚠️ Digest skipped: channel(s) not configured.")
            return

        now    = datetime.datetime.now(datetime.timezone.utc)
        cutoff = now - datetime.timedelta(hours=24)

        collected = []
        async for msg in suggestions_channel.history(limit=500, after=cutoff):
            if msg.author.id != self.bot.user.id:
                continue
            for embed in msg.embeds:
                if embed.footer and embed.footer.text == SUGGESTION_MARKER:
                    author = embed.author.name if embed.author else "Unknown"
                    text   = embed.description or ""
                    collected.append((author, text))

        today_str = now.astimezone(DIGEST_TIMEZONE).strftime("%B %d, %Y")

        if not collected:
            await digest_channel.send(f"📭 No suggestions were submitted on {today_str}.")
            return

        lines = [f"**{i}.** {text}\n_— {author}_" for i, (author, text) in enumerate(collected, 1)]

        digest = discord.Embed(
            title=f"📋 Daily Suggestions — {today_str}",
            description="\n\n".join(lines)[:4096],
            color=discord.Color.green(),
        )
        digest.set_footer(text=f"{len(collected)} suggestion(s) today")

        await digest_channel.send(embed=digest)
        print(f"✅ Posted daily digest with {len(collected)} suggestion(s).")

    # ── Scheduled daily digest ────────────────────────────────────────────────────
    @tasks.loop(
        time=datetime.time(hour=DIGEST_HOUR, minute=DIGEST_MINUTE, tzinfo=DIGEST_TIMEZONE)
    )
    async def daily_digest(self):
        await self.build_and_post_digest()

    @daily_digest.before_loop
    async def before_daily_digest(self):
        await self.bot.wait_until_ready()

    # ── !digest (admin only, for testing) ─────────────────────────────────────────
    @commands.command(name="digest")
    @commands.has_permissions(administrator=True)
    async def digest_now(self, ctx):
        await ctx.reply("⏳ Generating today's digest...", mention_author=True)
        await self.build_and_post_digest()

    @digest_now.error
    async def digest_now_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.reply(
                "❌ You need administrator permission to use that command.",
                mention_author=True,
            )


# Required entry point so bot.load_extension("suggestions") works
async def setup(bot: commands.Bot):
    await bot.add_cog(Suggestions(bot))
