from discord.ext import commands
from dotenv import load_dotenv
import requests
import asyncio
import discord
import redis
import json
import time
import os
import io

load_dotenv()

TOKEN = os.getenv("TOKEN")
REDIS_URL = os.getenv("REDIS_URL")
WIDG_TOKEN = os.getenv("WIDG_TOKEN")
WIDG_APPID = os.getenv("WIDG_APPID")
WIDG_USR = os.getenv("WIDG_USR")
WIDG_URL = os.getenv("WIDG_URL")

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

db:dict = json.load(open("./db.json", "r"))
redis_db = redis.Redis.from_url(REDIS_URL)

last_msg_id:int         = db["last_msg_id"]
online:bool             = db["online"]
track:bool              = db["track"]
banner_change_date:int  = db["banner_change_date"]
banner_changer_id:int   = db["banner_changer_id"]
banner_changer_name:str = db["banner_changer_name"]
banner_banned:list      = db["banner_banned"]

# ==================== change zeez ====================
ONLINE_MSG = f"""
# :white_check_mark: ¡Los Servidores han vuelto!
:flag_us: The Servers are back!
:flag_br: Os Servidores voltaram!
-# <@&{role_ping_id}> - $time$
"""

OFFLINE_MSG = f"""
# <:EK_bad_servers:1502482565968302080> ¡Los Servidores están offline!
:flag_us: The Servers are offline!
:flag_br: Os Servidores estão offline!
-# <@&{role_ping_id}> - $time$
"""

HONEYPOT_MSG = """
Hola $username$, tu cuenta ha sido expulsada temporalmente de **$guild_name$** debido a que ha sido comprometida (enviando imágenes, enlaces o mensajes sospechosos). Asegura tu cuenta antes de volver por favor.
-# Puedes volver en 15 minutos.

https://discord.gg/n4JdZbCunR
"""
# actual code

class Widget:
    def __init__(self):
        self.token = None
        self.app_id = None
    def auth(self, token:str, app_id:int):
        self.token = token
        self.app_id = app_id
    def update(self, data:str, user_id:int):
        url = f"https://discord.com/api/v9/applications/{self.app_id}/users/{user_id}/identities/0/profile"
        headers = {
            "Content-Type":"application/json",
            "Authorization":f"Bot {self.token}",
            "User-Agent":"DiscordBot (https://github.com/discord/discord-api-docs, 1.0.0)"
        }
        resp = requests.patch(url, data=data, headers=headers)
        return resp

widget = Widget()
widget.auth(WIDG_TOKEN, WIDG_APPID)

def update_db():
    global last_msg_id
    global online
    global track
    global banner_change_date
    global banner_changer_id
    global banner_changer_name
    global banner_banned

    db.update({
        "last_msg_id": last_msg_id,
        "online":online,
        "track": track,
        "banner_change_date": banner_change_date,
        "banner_changer_id": banner_changer_id,
        "banner_changer_name": banner_changer_name,
        "banner_banned": banner_banned
    })
    json.dump(db, open("./db.json", "w"), indent=4)

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

def update_widget(amount:int):
    data:str = json.dumps(json.loads(requests.get(WIDG_URL).content.decode().replace("$honey_eaten$", str(amount))))
    resp = widget.update(data, WIDG_USR)
    return resp.status_code == 204

async def offline_to_online():
    global online
    global last_msg_id
    online = True
    await client.change_presence(
        status=discord.Status.online,
        activity=(discord.CustomActivity(f"Banner by {banner_changer_name}") if banner_changer_name else None)
    )
    try:
        await client.get_channel(log_channel_id).get_partial_message(last_msg_id).delete()
        await asyncio.sleep(1)
    except:
        pass
    new_msg = await client.log_channel.send(ONLINE_MSG.replace("$time$", f"<t:{int(time.time())}:R>"))
    last_msg_id = new_msg.id
    update_db()

async def online_to_offline():
    global online
    global last_msg_id
    global honeypot_channel_id
    global honeypot_immune_roles
    online = False
    await client.change_presence(
        status=discord.Status.dnd,
        activity=discord.CustomActivity("Servers are down, download levels instead")
    )
    try:
        await client.get_channel(log_channel_id).get_partial_message(last_msg_id).delete()
        await asyncio.sleep(1)
    except:
        pass
    new_msg = await client.log_channel.send(OFFLINE_MSG.replace("$time$", f"<t:{int(time.time())}:R>"))
    last_msg_id = new_msg.id
    update_db()

async def log(msg:str, channel:discord.TextChannel = None):
    print(msg)
    if channel:
        await channel.send(f"{msg}")

class Client(commands.Bot):
    async def on_ready(self):
        global online
        await log("Fetching log channel...")
        self.log_channel:discord.TextChannel = self.get_channel(log_channel_id)
        self.hw_channel:discord.TextChannel = self.get_channel(greet_channel_id)
        await log("Booting up...", self.hw_channel)
        await log("Syncing global command tree...", self.hw_channel)
        await self.tree.sync()
        await log("Syncing private command tree...", self.hw_channel)
        await self.tree.sync(guild=discord.Object(id=banner_cmd_guild_id))
        await log("Finished!", self.hw_channel)
        await self.hw_channel.send("## Hello world!")
        print(f"{self.user.name} online")
        if online:
            await client.change_presence(
                status=discord.Status.online,
                activity=(discord.CustomActivity(f"Banner by {banner_changer_name}") if banner_changer_name else None)
            )
        else:
            await client.change_presence(
                status=discord.Status.dnd,
                activity=discord.CustomActivity("Servers are down, download levels instead")
            )

    async def on_presence_update(self, before:discord.Member, after:discord.Member):
        global online
        global track
        if track:
            if self.log_channel and before.id == tracked_user_id:
                if before.status.name != "offline" and after.status.name == "offline" and online:
                    await online_to_offline()

                elif before.status.name == "offline" and after.status.name != "offline" and not online:
                    await offline_to_online()

    async def on_message(self, msg:discord.Message):
        if msg.author.bot or any(role.id in honeypot_immune_roles for role in msg.author.roles):
            return

        if msg.channel.id != honeypot_channel_id:
            return

        try:
            await msg.guild.fetch_ban(msg.author)
        except:
            pass
        else:
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

        await msg.author.ban(
            reason="Cuenta hackeada (cayó en el bait de #the-thing) ban temporal.",
            delete_message_days=1
        )

        redis_db.incr("honey_eaten")
        honey_eaten = int(redis_db.get("honey_eaten"))
        widupdate = update_widget(honey_eaten)
        embed = discord.Embed(
            title="💠 Logs ︱ Honeypot Triggered",
            description=f"{msg.author.name} (<@{msg.author.id}>) was banned! - <t:{int(time.time())}:f>\n\n`ID: {msg.author.id}`\nBans performed: `{honey_eaten}`",
            color=0xD4C32A
        )
        if client.intents.message_content:
            embed.add_field(name="Message content", value=f"`{msg.content if msg.content else '(No content)'}`"+(f'\n+{len(msg.attachments)} attachments' if msg.attachments else ''), inline=False)

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


intents = discord.Intents.default()
intents.presences = True
intents.members = True

client = Client("", intents=intents)
client.log_channel = None

# ======================= commands =======================

@client.tree.command(name="toggle", description="🔶 Enable or disable tracking EK-Bot")
@discord.app_commands.allowed_contexts(guilds = True)
async def toggle_track(interaction:discord.Interaction, enable:bool):
    global track
    if interaction.user.guild_permissions.administrator:
        if enable == False:
            track = False
            await client.change_presence(
                status=discord.Status.idle,
                activity=discord.CustomActivity("Tracking is currently off")
            )
            await interaction.response.send_message(":warning: Tracking has been **disabled**.")
        else:
            track = True
            await client.change_presence(
                status=discord.Status.online,
                activity=(discord.CustomActivity(f"Banner by {banner_changer_name}") if banner_changer_name else None)
            )
            await interaction.response.send_message(":white_check_mark: Tracking has been **enabled**.")
        update_db()
    else:
        await interaction.response.send_message(f":no_entry: You don't have permission to use this command\n-# Are you trying to make an account? use **</setup:1199514841363255340>**.", ephemeral=True)

@client.tree.command(name="catch-up", description="🔶 Check EK-Bot's status and update the message accordingly")
@discord.app_commands.allowed_contexts(guilds = True)
async def catch_up_cmd(interaction:discord.Interaction):
    global online
    if interaction.user.guild_permissions.administrator:
        member = client.log_channel.guild.get_member(tracked_user_id)
        if member.status.name != "offline" and not online:
            await offline_to_online()
            await interaction.response.send_message(":white_check_mark: EK-Bot is now **online**, I've updated my message.")
        elif member.status.name == "offline" and online:
            await online_to_offline()
            await interaction.response.send_message(":white_check_mark: EK-Bot is now **offline**, I've updated my message.")
        else:
            await interaction.response.send_message(":warning: EK-Bot's status is the same as the last update, no changes were made.")
    else:
        await interaction.response.send_message(f":no_entry: You don't have permission to use this command\n-# Are you trying to make an account? use **</setup:1199514841363255340>**.", ephemeral=True)

@client.tree.command(name="banner", description="Set the banner for the bot")
@discord.app_commands.describe(banner="Choose a banner for the bot (max 10 MB)")
@discord.app_commands.allowed_contexts(guilds = True, dms = True)
async def set_banner_cmd(interaction:discord.Interaction, banner:discord.Attachment):
    global banner_change_date
    global banner_changer_id
    global banner_changer_name
    global banner_banned
    global banner_log_channel_id
    global online

    if interaction.guild:
        member = interaction.guild.get_member(interaction.user.id)
    else:
        guild = client.get_channel(log_channel_id).guild
        member = guild.get_member(interaction.user.id)

    if not member:
        await interaction.response.send_message(":x: Couldn't find you in Engine Kingdom.", ephemeral=True)
        return

    if member.id in banner_admins or any(role.id in banner_allowed_roles for role in member.roles):
        if member.id in banner_banned:
            await interaction.response.send_message(":x: You are banned from changing the banner.", ephemeral=True)
            return

        if member.id == banner_changer_id:
            await interaction.response.send_message(":x: You can't change the banner twice in a row.", ephemeral=True)
            return

        if not member.id in banner_admins:
            cooldown = int(time.time()) - banner_change_date
            if cooldown < 60 * 60 * banner_delay_hours: # 1 hour cooldown for non-admins
                await interaction.response.send_message(f":x: The banner can only be changed once every hour. You'll be able to change it <t:{banner_change_date + (60 * 60 * banner_delay_hours)}:R>.", ephemeral=True)
                return

        if not banner.content_type or not banner.content_type.startswith("image/"):
            await interaction.response.send_message(":x: Please upload a valid image file.", ephemeral=True)
            return

        if banner.size > 10 * 1024 * 1024:
            await interaction.response.send_message(":x: The image file size must be less than 10 MB.", ephemeral=True)
            return

        try:
            await interaction.response.defer()
            img_bytes = await banner.read()
            await client.user.edit(banner=img_bytes)

            if online:
                await client.change_presence(
                    status=discord.Status.online,
                    activity=(discord.CustomActivity(f"Banner by {member.name}") if member.name else None)
                )

            banner_log_channel = client.get_channel(banner_log_channel_id)

            image_stream = io.BytesIO(img_bytes)

            filename = banner.filename.replace(" ", "").replace("_", "")
            file = discord.File(fp=image_stream, filename=filename)

            embed = discord.Embed(title="<:boxg:1502150406523064401> Logs ︱ Banner Updated", description=f"{member.name} (<@{member.id}>) changed my banner! - <t:{int(time.time())}:f>\n\n`ID: {member.id}`", color=0x5B0BAA)

            embed.set_image(url="attachment://"+filename)

            await banner_log_channel.send(embed=embed, file=file)

            if not member.id in banner_admins:
                banner_change_date = int(time.time())
            banner_changer_id = member.id
            banner_changer_name = member.name
            update_db()
            await interaction.followup.send(":white_check_mark: Banner updated successfully! Check it out!")
        except Exception as e:
                await interaction.followup.send(f":x: Failed to update banner: `{e}`", ephemeral=True)
    else:
        await interaction.response.send_message(f":no_entry: You don't have permission to use this command\n-# Are you trying to make an account? use **</setup:1199514841363255340>**.", ephemeral=True)


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
    global banner_banned
    if interaction.user.id in banner_admins:
        user = client.get_user(int(user_id))
        if not user:
            await interaction.response.send_message(f":x: User not found.")
            return
        if user.id not in banner_banned:
            banner_banned.append(user.id)
            update_db()
            await interaction.response.send_message(f":white_check_mark: {user.name} has been banned from changing the banner.")
        else:
            await interaction.response.send_message(f":warning: {user.name} is already banned from changing the banner.")
    else:
        await interaction.response.send_message(f":no_entry: You don't have permission to use this command\n-# Are you trying to make an account? use **</setup:1199514841363255340>**.", ephemeral=True)

@client.tree.command(name="banner-unban", description="📦 Unban a user from changing the banner", guild=discord.Object(id=banner_cmd_guild_id))
@discord.app_commands.allowed_contexts(guilds = True)
async def banner_unban_cmd(interaction:discord.Interaction, user_id:str):
    global banner_banned
    if interaction.user.id in banner_admins:
        user = client.get_user(int(user_id))
        if not user:
            await interaction.response.send_message(f":x: User not found.")
            return
        if user.id in banner_banned:
            banner_banned.remove(user.id)
            update_db()
            await interaction.response.send_message(f":white_check_mark: {user.name} has been unbanned from changing the banner.")
        else:
            await interaction.response.send_message(f":warning: {user.name} is not banned from changing the banner.")
    else:
        await interaction.response.send_message(f":no_entry: You don't have permission to use this command\n-# Are you trying to make an account? use **</setup:1199514841363255340>**.", ephemeral=True)

@client.tree.command(name="softban", description="📦 Softban an user from Engine Kingdom", guild=discord.Object(id=banner_cmd_guild_id))
@discord.app_commands.allowed_contexts(guilds = True)
async def banner_unban_cmd(interaction:discord.Interaction, user_id:str):
    global log_channel_id
    
    guild = client.get_channel(log_channel_id).guild
    member = guild.get_member(int(user_id))
    user = client.get_user(int(user_id))
    
    if not member:
        await interaction.response.send_message(f":x: User not found")
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
    else:
        await interaction.followup.send(f":white_check_mark: Successfully banned `{member.name}`")
        redis_db.incr("honey_eaten")
        honey_eaten = int(redis_db.get("honey_eaten"))
        widupdate = update_widget(honey_eaten)
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
        await guild.unban(user, reason="Baneo temporal del bait de #the-thing finalizado.")
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
async def banner_unban_cmd(interaction:discord.Interaction, user_id:str):
    global log_channel_id
    
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
                embed.add_field(name="Message content", value=f"`{message.content if message.content else '(No content)'}`"+(f'\n+{len(message.attachments)} attachments' if message.attachments else ''), inline=False)
            await log_channel.send(embed=embed)
    else:
        await interaction.response.send_message(f":no_entry: You don't have permission to use this command\n-# Are you trying to make an account? use **</setup:1199514841363255340>**.", ephemeral=True)

client.run(TOKEN)
