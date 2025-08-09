import discord
from discord.ext import commands, tasks
import asyncio
import logging
import json
import os
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

config = {}
target_user_id = None
ping_channel_id = None

def load_config():
    global config, target_user_id, ping_channel_id
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
        target_user_id = config.get('target_user_id')
        ping_channel_id = config.get('ping_channel_id')
        return config
    except FileNotFoundError:
        logger.warning("Config file not found, creating default config")
        default_config = {
            "target_user_id": None,
            "ping_channel_id": None,
            "ping_message": "Hourly ping! {user}"
        }
        save_config(default_config)
        return default_config
    except json.JSONDecodeError:
        logger.error("Invalid JSON in config file, using default config")
        return {"target_user_id": None, "ping_channel_id": None, "ping_message": "Hourly ping! {user}"}

def save_config(new_config=None):
    global config
    if new_config is None:
        new_config = config
    try:
        with open('config.json', 'w') as f:
            json.dump(new_config, f, indent=4)
        config = new_config
        logger.info("Configuration saved successfully")
    except Exception as e:
        logger.error(f"Failed to save configuration: {e}")

@bot.event
async def on_ready():
    logger.info(f'{bot.user} has connected to Discord!')
    logger.info(f'Bot is in {len(bot.guilds)} guilds')
    if target_user_id and ping_channel_id:
        if not hourly_ping.is_running():
            hourly_ping.start()
            logger.info("Hourly ping task started")
    else:
        logger.warning("Target user ID or ping channel not configured. Use !setuser and !setchannel commands to configure.")

@tasks.loop(minutes=5)
async def hourly_ping():
    global target_user_id, ping_channel_id, config
    if not target_user_id or not ping_channel_id:
        logger.warning("Target user ID or ping channel not configured, skipping ping")
        return
    try:
        channel = bot.get_channel(ping_channel_id)
        if not channel:
            logger.error(f"Could not find channel with ID {ping_channel_id}")
            return
        user = bot.get_user(target_user_id)
        if not user:
            try:
                user = await bot.fetch_user(target_user_id)
            except discord.NotFound:
                logger.error(f"Could not find user with ID {target_user_id}")
                return
            except discord.HTTPException as e:
                logger.error(f"HTTP error while fetching user: {e}")
                return
        ping_message = config.get('ping_message', 'Hourly ping! {user}')
        message = ping_message.format(user=user.mention)
        await channel.send(message)
        logger.info(f"Successfully pinged {user.name} in #{channel.name}")
    except discord.Forbidden:
        logger.error("Bot doesn't have permission to send messages in the configured channel")
    except discord.HTTPException as e:
        logger.error(f"HTTP error while sending ping: {e}")
    except Exception as e:
        logger.error(f"Unexpected error during hourly ping: {e}")

@hourly_ping.before_loop
async def before_hourly_ping():
    await bot.wait_until_ready()

@bot.command(name='setuser')
async def set_target_user(ctx, user: discord.User):
    if ctx.author.id != 542485080204116010:
        await ctx.send("❌ Only the bot owner can use this command!")
        return
    global target_user_id, config
    target_user_id = user.id
    config['target_user_id'] = user.id
    save_config()
    await ctx.send(f"Target user set to {user.mention}")
    logger.info(f"Target user set to {user.name} (ID: {user.id}) by {ctx.author}")
    if ping_channel_id:
        if hourly_ping.is_running():
            hourly_ping.restart()
        else:
            hourly_ping.start()
        await ctx.send("Hourly ping task (re)started!")

@bot.command(name='setchannel')
@commands.has_permissions(administrator=True)
async def set_ping_channel(ctx, channel: discord.TextChannel = None):
    global ping_channel_id, config
    if channel is None:
        channel = ctx.channel
    ping_channel_id = channel.id
    config['ping_channel_id'] = channel.id
    save_config()
    await ctx.send(f"Ping channel set to {channel.mention}")
    logger.info(f"Ping channel set to #{channel.name} (ID: {channel.id}) by {ctx.author}")
    if target_user_id:
        if hourly_ping.is_running():
            hourly_ping.restart()
        else:
            hourly_ping.start()
        await ctx.send("Hourly ping task (re)started!")

@bot.command(name='setmessage')
@commands.has_permissions(administrator=True)
async def set_ping_message(ctx, *, message: str):
    global config
    config['ping_message'] = message
    save_config()
    await ctx.send(f"Ping message set to: `{message}`")
    logger.info(f"Ping message updated by {ctx.author}")

@bot.command(name='status')
async def bot_status(ctx):
    global target_user_id, ping_channel_id, config
    embed = discord.Embed(title="Bot Status", color=0x00ff00)
    if target_user_id:
        user = bot.get_user(target_user_id)
        if user:
            embed.add_field(name="Target User", value=user.mention, inline=False)
        else:
            embed.add_field(name="Target User", value=f"User ID: {target_user_id} (Not found)", inline=False)
    else:
        embed.add_field(name="Target User", value="Not set", inline=False)
    if ping_channel_id:
        channel = bot.get_channel(ping_channel_id)
        if channel:
            embed.add_field(name="Ping Channel", value=channel.mention, inline=False)
        else:
            embed.add_field(name="Ping Channel", value=f"Channel ID: {ping_channel_id} (Not found)", inline=False)
    else:
        embed.add_field(name="Ping Channel", value="Not set", inline=False)
    ping_message = config.get('ping_message', 'Hourly ping! {user}')
    embed.add_field(name="Ping Message", value=f"`{ping_message}`", inline=False)
    if hourly_ping.is_running():
        embed.add_field(name="Hourly Ping Task", value="✅ Running", inline=False)
    else:
        embed.add_field(name="Hourly Ping Task", value="❌ Stopped", inline=False)
    await ctx.send(embed=embed)

@bot.command(name='start')
@commands.has_permissions(administrator=True)
async def start_pings(ctx):
    global target_user_id, ping_channel_id
    if not target_user_id or not ping_channel_id:
        await ctx.send("❌ Please set both target user and ping channel first!")
        return
    if hourly_ping.is_running():
        await ctx.send("Hourly ping task is already running!")
    else:
        hourly_ping.start()
        await ctx.send("✅ Hourly ping task started!")
        logger.info(f"Hourly ping task manually started by {ctx.author}")

@bot.command(name='stop')
@commands.has_permissions(administrator=True)
async def stop_pings(ctx):
    if hourly_ping.is_running():
        hourly_ping.stop()
        await ctx.send("❌ Hourly ping task stopped!")
        logger.info(f"Hourly ping task manually stopped by {ctx.author}")
    else:
        await ctx.send("Hourly ping task is not running!")

@bot.command(name='ping')
async def ping_command(ctx):
    latency = round(bot.latency * 1000, 2)
    await ctx.send(f"Pong! Latency: {latency}ms")

@bot.command(name='help_ping')
async def help_ping(ctx):
    embed = discord.Embed(title="Hourly Ping Bot Commands", color=0x0099ff)
    embed.add_field(
        name="!setuser <@user>", 
        value="Set the target user to ping hourly (Admin only)", 
        inline=False
    )
    embed.add_field(
        name="!setchannel [#channel]", 
        value="Set the channel for hourly pings (Admin only)", 
        inline=False
    )
    embed.add_field(
        name="!setmessage <message>", 
        value="Set custom ping message. Use {user} for user mention (Admin only)", 
        inline=False
    )
    embed.add_field(
        name="!status", 
        value="Show current bot configuration and status", 
        inline=False
    )
    embed.add_field(
        name="!start", 
        value="Manually start hourly pings (Admin only)", 
        inline=False
    )
    embed.add_field(
        name="!stop", 
        value="Manually stop hourly pings (Admin only)", 
        inline=False
    )
    embed.add_field(
        name="!ping", 
        value="Check bot latency", 
        inline=False
    )
    await ctx.send(embed=embed)

def main():
    load_config()
    token = os.getenv('DISCORD_BOT_TOKEN')
    if not token:
        logger.error("DISCORD_BOT_TOKEN environment variable not set!")
        print("Please set the DISCORD_BOT_TOKEN environment variable with your bot's token.")
        return
    try:
        bot.run(token)
    except discord.LoginFailure:
        logger.error("Invalid bot token provided!")
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")

if __name__ == "__main__":
    main()
