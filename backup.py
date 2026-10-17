from discord.ext import commands
from dotenv import load_dotenv
import asyncio
import discord
import redis
import json
import time
import os

load_dotenv()

TOKEN = os.getenv("TOKEN")
REDIS_URL = os.getenv("REDIS_URL")

variables:dict = json.load(open("./vars.json", "r"))

engine_kingdom_guild_id:int = variables["engine_kingdom_guild_id"]
tracked_user_id:int       = variables["tracked_user_id"]
log_channel_id:int        = variables["log_channel_id"]
greet_channel_id:int      = variables["greet_channel_id"]
role_ping_id:int          = variables["role_ping_id"]
banner_cmd_guild_id:int   = variables["banner_cmd_guild_id"]
banner_log_channel_id:int = variables["banner_log_channel_id"]
banner_admins:list        = variables["banner_admins"]
banner_allowed_roles:list = variables["banner_allowed_roles"]
banner_delay_hours:int    = variables["banner_delay_hours"]
honeypot_channel_id:int   = variables["honeypot_channel_id"]
honeypot_immune_roles:list = variables["honeypot_immune_roles"]
honeypot_delete_channels:list = variables["honeypot_delete_channels"]

redis_db = redis.Redis.from_url(REDIS_URL)
temp_banneds:list[int] = []

# ==================== change zeez ====================
HONEYPOT_MSG = """
Hola $username$, tu cuenta ha sido expulsada temporalmente de **$guild_name$** debido a que ha sido comprometida (enviando imágenes, enlaces o mensajes sospechosos). Asegura tu cuenta antes de volver por favor.
-# Puedes volver en 15 minutos.

https://discord.gg/n4JdZbCunR
"""
# actual code

def update_vars():
    global engine_kingdom_guild_id
    global tracked_user_id
    global log_channel_id
    global greet_channel_id
    global role_ping_id
    global banner_cmd_guild_id
    global banner_log_channel_id
    global banner_admins
    global banner_allowed_roles
    global banner_delay_hours
    global honeypot_channel_id
    global honeypot_immune_roles
    global honeypot_delete_channels

    variables = json.load(open("./vars.json", "r"))
    engine_kingdom_guild_id = variables["engine_kingdom_guild_id"]
    tracked_user_id       = variables["tracked_user_id"]
    log_channel_id        = variables["log_channel_id"]
    role_ping_id          = variables["role_ping_id"]
    banner_cmd_guild_id   = variables["banner_cmd_guild_id"]
    banner_log_channel_id = variables["banner_log_channel_id"]
    banner_admins         = variables["banner_admins"]
    banner_allowed_roles  = variables["banner_allowed_roles"]
    banner_delay_hours    = variables["banner_delay_hours"]
    honeypot_channel_id   = variables["honeypot_channel_id"]
    honeypot_immune_roles = variables["honeypot_immune_roles"]
    honeypot_delete_channels = variables["honeypot_delete_channels"]

    if client and client.log_channel and client.log_channel.id != log_channel_id:
        client.log_channel = client.get_channel(log_channel_id)

async def log(msg:str, channel:discord.TextChannel = None):
    print(msg)
    if channel:
        await channel.send(f"{msg}")

class Client(commands.Bot):
    async def on_ready(self):
        global online
        await log("[Backup] Fetching log channel...")
        self.log_channel:discord.TextChannel = self.get_channel(log_channel_id)
        self.hw_channel:discord.TextChannel = self.get_channel(greet_channel_id)
        await log("[Backup] Finished!", self.hw_channel)
        await self.hw_channel.send("## Hello world!\n-# 🛠️ Backup instance")
        print(f"{self.user.name} online")

    async def on_message(self, msg:discord.Message):
        if msg.author.bot or any(role.id in honeypot_immune_roles for role in msg.author.roles):
            return

        if msg.channel.id != honeypot_channel_id:
            return

        if msg.author.id in temp_banneds:
            return

        temp_banneds.append(msg.author.id)

        try:
            await msg.guild.fetch_ban(msg.author)
        except:
            pass
        else:
            temp_banneds.remove(msg.author.id)
            return

        try:
            await msg.author.send(
                HONEYPOT_MSG.replace("$username$", msg.author.name).replace("$guild_name$", msg.guild.name)
            )
        except:
            pass

        try:
            await msg.delete()
        except:
            pass

        await asyncio.sleep(2)

        await msg.author.ban(
            reason="Cuenta hackeada (cayó en el bait de #the-thing) ban temporal.",
            delete_message_days=1
        )

        redis_db.incr("honey_eaten")
        honey_eaten = int(redis_db.get("honey_eaten"))
        embed = discord.Embed(
            title="💠 Logs ︱ Honeypot Triggered",
            description=f"{msg.author.name} (<@{msg.author.id}>) was banned! - <t:{int(time.time())}:f>\n\n`ID: {msg.author.id}`\nBans performed: `{honey_eaten}`",
            color=0xD4C32A
        )
        if client.intents.message_content:
            embed.add_field(name="Message content", value=f"`{msg.content if msg.content else '(No content)'}`"+(f'+{len(msg.attachments)} attachments' if msg.attachments else ''), inline=False)

        for channel_id in honeypot_delete_channels:
            channel = self.get_channel(channel_id)
            try:
                await channel.purge(limit=3, check=lambda m: (m.author.id == msg.author.id and abs(m.created_at.timestamp() - msg.created_at.timestamp()) < 60))
            except:
                pass

        channel = self.get_channel(banner_log_channel_id)

        await channel.send(embed=embed)

        await asyncio.sleep(15*60)

        try:
            await msg.author.unban(reason="Baneo temporal del bait de #the-thing finalizado.")
        except:
            embed = discord.Embed(
                title="💠 Logs ︱ Failed to unban user",
                description=f"Failed to automatically unban {msg.author.name} (<@{msg.author.id}>)! - <t:{int(time.time())}:f>\n\n`ID: {msg.author.id}`",
                color=0xD42A2A
            )
        else:
            embed = discord.Embed(
                title="💠 Logs ︱ User unbanned",
                description=f"Automatically unbanned {msg.author.name} (<@{msg.author.id}>) after 15 minutes! - <t:{int(time.time())}:f>\n\n`ID: {msg.author.id}`",
                color=0x4CD42A
            )
        await channel.send(embed=embed)
        temp_banneds.remove(msg.author.id)


intents = discord.Intents.default()
intents.presences = True
intents.members = True

client = Client("", intents=intents)
client.log_channel = None

# ======================= commands =======================

@client.tree.command(name="toggle", description="🔶 Enable or disable tracking EK-Bot")
@discord.app_commands.allowed_contexts(guilds = True)
async def toggle_track(interaction:discord.Interaction, enable:bool):
    await interaction.response.send_message(":warning: The bot is in backup mode, this command is disabled", ephemeral=True)

@client.tree.command(name="catch-up", description="🔶 Check EK-Bot's status and update the message accordingly")
@discord.app_commands.allowed_contexts(guilds = True)
async def catch_up_cmd(interaction:discord.Interaction):
        await interaction.response.send_message(":warning: The bot is in backup mode, this command is disabled", ephemeral=True)

@client.tree.command(name="banner", description="Set the banner for the bot")
@discord.app_commands.describe(banner="Choose a banner for the bot (max 10 MB)")
@discord.app_commands.allowed_contexts(guilds = True, dms = True)
async def set_banner_cmd(interaction:discord.Interaction, banner:discord.Attachment):
        await interaction.response.send_message(":warning: The bot is in backup mode, this command is disabled", ephemeral=True)


# ======================= our server only =======================

@client.tree.command(name="update", description="📦 Update the variables from vars.json without needing to restart the bot", guild=discord.Object(id=banner_cmd_guild_id))
@discord.app_commands.allowed_contexts(guilds = True)
async def update_vars_cmd(interaction:discord.Interaction):
    update_vars()
    if interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(":white_check_mark: Variables updated!")
    else:
        await interaction.response.send_message(f":no_entry: You don't have permission to use this command\n-# Are you trying to make an account? use **</setup:1199514841363255340>**.", ephemeral=True)

@client.tree.command(name="banner-ban", description="📦 Ban a user from changing the banner", guild=discord.Object(id=banner_cmd_guild_id))
@discord.app_commands.allowed_contexts(guilds = True)
async def banner_ban_cmd(interaction:discord.Interaction, user_id:str):
        await interaction.response.send_message(":warning: The bot is in backup mode, this command is disabled", ephemeral=True)

@client.tree.command(name="banner-unban", description="📦 Unban a user from changing the banner", guild=discord.Object(id=banner_cmd_guild_id))
@discord.app_commands.allowed_contexts(guilds = True)
async def banner_unban_cmd(interaction:discord.Interaction, user_id:str):
        await interaction.response.send_message(":warning: The bot is in backup mode, this command is disabled", ephemeral=True)

@client.tree.command(name="softban", description="📦 Softban an user from Engine Kingdom", guild=discord.Object(id=banner_cmd_guild_id))
@discord.app_commands.allowed_contexts(guilds = True)
async def softban_cmd(interaction:discord.Interaction, user_id:str):
    guild = client.get_channel(log_channel_id).guild
    member = guild.get_member(int(user_id))
    if member is None:
        try:
            member = await guild.fetch_member(int(user_id))
        except discord.NotFound:
            await interaction.response.send_message(":x: User not found")
            return

    if not member:
        await interaction.response.send_message(":x: User not found")
        return

    await interaction.response.defer()
    
    try:
        await member.send(
            HONEYPOT_MSG.replace("$username$", member.name).replace("$guild_name$", guild.name)
        )
    except:
        pass

    try:
        await member.ban(
            reason="Cuenta hackeada (cayó en el bait de #the-thing) ban temporal.",
            delete_message_days=1
        )
    except Exception as e:
        await interaction.followup.send(f":x: Failed to softban `{member.name}`: `{e}`")
        return

    await interaction.followup.send(f":white_check_mark: Successfully banned `{member.name}`")
    redis_db.incr("honey_eaten")
    honey_eaten = int(redis_db.get("honey_eaten"))
    embed = discord.Embed(
        title=f"<:boxg:1502150406523064401> Logs ︱ Manual softban by {interaction.user.name}",
        description=f"{member.name} (<@{member.id}>) was banned! - <t:{int(time.time())}:f>\n\n`ID: {member.id}`\nBans performed: `{honey_eaten}`",
        color=0xD4C32A
    )
    embed.set_footer(text=f"Action performed by @{interaction.user.name} - {interaction.user.id}", icon_url=interaction.user.display_avatar.url)

    channel = client.get_channel(banner_log_channel_id)

    await channel.send(embed=embed)

    await asyncio.sleep(5)

    try:
        await guild.unban(discord.Object(id=member.id), reason="Baneo temporal del bait de #the-thing finalizado.")
    except:
        embed = discord.Embed(
            title="<:boxg:1502150406523064401> Logs ︱ Failed to unban user",
            description=f"Failed to automatically unban {member.name} (<@{member.id}>)! - <t:{int(time.time())}:f>\n\n`ID: {member.id}`",
            color=0xD42A2A
        )
    else:
        embed = discord.Embed(
            title="<:boxg:1502150406523064401> Logs ︱ User unbanned",
            description=f"Automatically unbanned {member.name} (<@{member.id}>) after 5 seconds! - <t:{int(time.time())}:f>\n\n`ID: {member.id}`",
            color=0x4CD42A
        )
    embed.set_footer(text=f"Action performed by @{interaction.user.name} - {interaction.user.id}", icon_url=interaction.user.display_avatar.url)
    await channel.send(embed=embed)

@client.tree.command(name="unban", description="📦 Unban an user from Engine Kingdom", guild=discord.Object(id=banner_cmd_guild_id))
@discord.app_commands.allowed_contexts(guilds = True)
async def unban_cmd(interaction:discord.Interaction, user_id:str):
    
    guild = client.get_channel(log_channel_id).guild
    user = discord.Object(id=int(user_id))

    await interaction.response.defer()

    channel = client.get_channel(banner_log_channel_id)

    try:
        await guild.unban(user, reason="Baneo temporal del bait de #the-thing finalizado.")
    except:
        embed = discord.Embed(
            title="<:boxg:1502150406523064401> Logs ︱ Failed to unban user",
            description=f"Failed to manually unban <@{user.id}>! - <t:{int(time.time())}:f>\n\n`ID: {user.id}`",
            color=0xD42A2A
        )
        await interaction.followup.send(f":x: Failed to unban <@{user.id}> from {guild.name}")
    else:
        embed = discord.Embed(
            title="<:boxg:1502150406523064401> Logs ︱ User unbanned",
            description=f"Manually unbanned (<@{user.id}>)! - <t:{int(time.time())}:f>\n\n`ID: {user.id}`",
            color=0x4CD42A
        )
        await interaction.followup.send(f":white_check_mark: <@{user.id}> was unbanned from {guild.name}")
    embed.set_footer(text=f"Action performed by @{interaction.user.name} - {interaction.user.id}", icon_url=interaction.user.display_avatar.url)
    await channel.send(embed=embed)

@client.tree.command(name="delete-msg", description="📦 Delete a message manually", guild=discord.Object(id=banner_cmd_guild_id))
@discord.app_commands.allowed_contexts(guilds = True)
async def delete_msg_cmd(interaction:discord.Interaction, message_url:str):
    global banner_log_channel_id
    log_channel = client.get_channel(banner_log_channel_id)
    if interaction.user.id in banner_admins:
        try:
            channel = await client.fetch_channel(int(message_url.split("/")[-2]))
            message = await channel.fetch_message(int(message_url.split("/")[-1]))
            await message.delete()
        except Exception as e:
            await interaction.response.send_message(f":x: Failed to delete message: `{e}`")
            embed = discord.Embed(
                title="<:boxg:1502150406523064401> Logs ︱ Failed to delete message",
                description=f"Failed to manually delete a message! - <t:{int(time.time())}:f>\n\n`Message URL: {message_url}`\n`Error: {e}`",
                color=0xD42A2A
            )
            await log_channel.send(embed=embed)
        else:
            await interaction.response.send_message(f":white_check_mark: Message deleted successfully.")
            embed = discord.Embed(
                title=f"<:boxg:1502150406523064401> Logs ︱ Message manually deleted by {interaction.user.name}",
                description=f"Manually deleted a message! - <t:{int(time.time())}:f>\n\n`Message URL: {message_url}`",
                color=0x4CD42A
            )
            if client.intents.message_content:
                embed.add_field(name="Message content", value=f"`{message.content if message.content else '(No content)'}`"+(f'+{len(message.attachments)} attachments' if message.attachments else ''), inline=False)
            await log_channel.send(embed=embed)
    else:
        await interaction.response.send_message(f":no_entry: You don't have permission to use this command\n-# Are you trying to make an account? use **</setup:1199514841363255340>**.", ephemeral=True)

@client.tree.command(name="message", description="📦 Send a message to a specific channel or user", guild=discord.Object(id=banner_cmd_guild_id))
@discord.app_commands.describe(
    id="The ID or mention of the target channel or user",
    message="The message you want to send"
)
@discord.app_commands.allowed_contexts(guilds = True)
async def message_cmd(interaction:discord.Interaction, id:str, message:str):
    if interaction.user.guild_permissions.administrator or interaction.user.id in banner_admins:
        log_channel = client.get_channel(log_channel_id)
        target_name = ""
        target_id = None
        target_label = ""

        async def respond(content:str):
            if interaction.response.is_done():
                await interaction.followup.send(content)
            else:
                await interaction.response.send_message(content)

        try:
            raw_id = id.strip()
            target_type = None

            if raw_id.startswith("<@"):
                target_type = "user"
                raw_id = raw_id.replace("<@", "").replace("<@!", "").replace("!", "").replace(">", "").strip()
            elif raw_id.startswith("<#"):
                target_type = "channel"
                raw_id = raw_id.replace("<#", "").replace(">", "").strip()
            elif raw_id.startswith("@"):
                target_type = "user"
                raw_id = raw_id.replace("@", "").strip()
            elif raw_id.startswith("#"):
                target_type = "channel"
                raw_id = raw_id.replace("#", "").strip()

            target_id = int(raw_id)

            if target_type == "user":
                target_user = await client.fetch_user(target_id)
                target_name = target_user.name
                target_id = target_user.id
                target_label = f"<@{target_user.id}>"
                await target_user.send(message)
                await respond(f":white_check_mark: DM sent successfully to <@{target_user.id}>!")
            elif target_type == "channel":
                target_channel = client.get_channel(target_id)
                if not target_channel:
                    target_channel = await client.fetch_channel(target_id)

                if not isinstance(target_channel, discord.TextChannel):
                    raise ValueError("The provided ID does not belong to a valid text channel.")

                target_name = f"#{target_channel.name}"
                target_id = target_channel.id
                target_label = f"<#{target_channel.id}>"
                await target_channel.send(message)
                await respond(f":white_check_mark: Message sent successfully to <#{target_channel.id}>!")
            else:
                try:
                    target_user = await client.fetch_user(target_id)
                except discord.NotFound:
                    target_user = None

                target_channel = client.get_channel(target_id)
                if not target_channel:
                    try:
                        target_channel = await client.fetch_channel(target_id)
                    except discord.NotFound:
                        target_channel = None

                if target_user is not None:
                    target_type = "user"
                    target_name = target_user.name
                    target_id = target_user.id
                    target_label = f"<@{target_user.id}>"
                    await target_user.send(message)
                    await respond(f":white_check_mark: DM sent successfully to <@{target_user.id}>!")
                elif isinstance(target_channel, discord.TextChannel):
                    target_type = "channel"
                    target_name = f"#{target_channel.name}"
                    target_id = target_channel.id
                    target_label = f"<#{target_channel.id}>"
                    await target_channel.send(message)
                    await respond(f":white_check_mark: Message sent successfully to <#{target_channel.id}>!")
                else:
                    await respond(":x: Target not found. Please check the ID.")
                    return

            embed = discord.Embed(
                title=f"<:boxg:1502150406523064401> Logs ︱ Message sent by {interaction.user.name}",
                description=f"A message was sent to {target_name} ({target_label}) - <t:{int(time.time())}:f>\n\n`🎯ID: {target_id}`",
                color=0x5B0BAA
            )
            embed.add_field(name="Message content", value=f"```\n{message[:1024]}\n```", inline=False)
            embed.set_footer(text=f"Action performed by @{interaction.user.name} - {interaction.user.id}", icon_url=interaction.user.display_avatar.url)
            await log_channel.send(embed=embed)

        except ValueError:
            await respond(":x: Invalid ID or mention format.")
        except discord.NotFound:
            await respond(":x: Target not found. Please check the ID.")
        except discord.Forbidden:
            await respond(":x: I don't have permissions to send this message (or the user closed their DMs).")
        except Exception as e:
            await respond(f":x: Failed to send message: `{e}`")
    else:
        await interaction.response.send_message(f":no_entry: You don't have permission to use this command\n-# Are you trying to make an account? use **</setup:1199514841363255340>**.", ephemeral=True)

@client.tree.command(name="edit", description="📦 Edit a message sent by the bot using the message link", guild=discord.Object(id=banner_cmd_guild_id))
@discord.app_commands.describe(
    message_url="The link to the message you want to edit",
    new_message="The new message"
)
@discord.app_commands.allowed_contexts(guilds = True)
async def edit_cmd(interaction:discord.Interaction, message_url:str, new_message:str):
    if interaction.user.guild_permissions.administrator or interaction.user.id in banner_admins:
        try:
            channel_id = int(message_url.split("/")[-2])
            message_id = int(message_url.split("/")[-1])

            channel = client.get_channel(channel_id)
            if not channel:
                channel = await client.fetch_channel(channel_id)

            message_obj = await channel.fetch_message(message_id)

            if message_obj.author.id == client.user.id:
                await message_obj.edit(content=new_message)
                await interaction.response.send_message(f":white_check_mark: Message edited successfully!\n-# > {message_url}")
            else:
                await interaction.response.send_message(":x: That message is not sent by me.")
        except (ValueError, IndexError):
            await interaction.response.send_message(":x: Invalid message link format.")
        except discord.NotFound:
            await interaction.response.send_message(":x: Message or channel not found.")
        except discord.Forbidden:
            await interaction.response.send_message(":x: I don't have permissions to access the channel.")
        except Exception as e:
            await interaction.response.send_message(f":x: Failed to edit message: `{e}`")
    else:
        await interaction.response.send_message(f":no_entry: You don't have permission to use this command\n-# Are you trying to make an account? use **</setup:1199514841363255340>**.", ephemeral=True)

client.run(TOKEN)
