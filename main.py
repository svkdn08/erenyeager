# trading_bot.py
import discord
from discord.ext import commands, tasks
import json
import datetime
import os

from keep_alive import keep_alive

# ---- CONFIG ----
TOKEN = os.environ.get("DISCORD_TOKEN")
GUILD_ID = int(os.environ.get("GUILD_ID", "1234567890"))

# ---- BOT SETUP ----
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ---- DATA STORAGE ----
DATA_FILE = "trading_data.json"

keep_alive()
def load_data():
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

data = load_data()

# ---- HELPER FUNCTIONS ----
def calculate_rr(entry, stoploss, target):
    try:
        risk = abs(entry - stoploss)
        reward = abs(target - entry)
        return round(reward / risk, 2) if risk != 0 else 0
    except:
        return 0

def get_user_trades(user_id):
    return data.get(str(user_id), {}).get("trades", [])

def get_best_trade(user_id):
    trades = get_user_trades(user_id)
    return max(trades, key=lambda t: t["rr"], default=None)

def get_worst_trade(user_id):
    trades = get_user_trades(user_id)
    return min(trades, key=lambda t: t["rr"], default=None)

def get_streak(user_id):
    trades = get_user_trades(user_id)
    streak = 0
    for t in reversed(trades):
        profit = (t["target"] - t["entry"]) if t["target"] > t["entry"] else (t["entry"] - t["target"])
        if profit > 0:
            streak += 1
        else:
            break
    return streak

def filter_trades_by_period(user_id, period_days):
    trades = get_user_trades(user_id)
    cutoff = datetime.date.today() - datetime.timedelta(days=period_days)
    return [t for t in trades if datetime.date.fromisoformat(t["date"]) >= cutoff]

# ---- COMMANDS ----
@bot.command(name="ping")
async def ping(ctx):
    await ctx.send(f"Pong! {round(bot.latency*1000)}ms")

@bot.command(name="help")
async def help_command(ctx):
    help_text = """
**Trading Bot Commands**
!trade [entry] [stoploss] [target] [notes] - Add a trade
!stats - Show your trading stats
!streak - Show winning/losing streak
!besttrade - Show best trade
!worsttrade - Show worst trade
!dailystats - Today stats
!weeklystats - Weekly stats
!monthlystats - Monthly stats
!lifetimestats - Lifetime stats
!resetstats - Reset your stats
!allresetstats - Admin only: Reset all stats
!leaderboard - Show top traders
!calendar - Show trading calendar
!ping - Check bot latency
"""
    await ctx.send(help_text)

@bot.command(name="trade")
async def trade(ctx, entry: float, stoploss: float, target: float, *, notes=""):
    user_id = str(ctx.author.id)
    rr = calculate_rr(entry, stoploss, target)
    trade_record = {
        "entry": entry,
        "stoploss": stoploss,
        "target": target,
        "notes": notes,
        "rr": rr,
        "date": str(datetime.date.today())
    }
    if user_id not in data:
        data[user_id] = {"trades": [], "streak": 0}
    data[user_id]["trades"].append(trade_record)
    save_data(data)
    await ctx.send(f"Trade added! R:R = {rr}")

@bot.command(name="stats")
async def stats(ctx):
    trades = get_user_trades(ctx.author.id)
    if not trades:
        await ctx.send("No trades yet!")
        return
    total_trades = len(trades)
    avg_rr = round(sum(t["rr"] for t in trades)/total_trades,2)
    await ctx.send(f"Total Trades: {total_trades}\nAverage R:R: {avg_rr}")

@bot.command(name="besttrade")
async def besttrade(ctx):
    best = get_best_trade(ctx.author.id)
    if not best:
        await ctx.send("No trades yet!")
        return
    await ctx.send(f"Best Trade:\nEntry: {best['entry']}, SL: {best['stoploss']}, Target: {best['target']}, R:R: {best['rr']}")

@bot.command(name="worsttrade")
async def worsttrade(ctx):
    worst = get_worst_trade(ctx.author.id)
    if not worst:
        await ctx.send("No trades yet!")
        return
    await ctx.send(f"Worst Trade:\nEntry: {worst['entry']}, SL: {worst['stoploss']}, Target: {worst['target']}, R:R: {worst['rr']}")

@bot.command(name="streak")
async def streak(ctx):
    s = get_streak(ctx.author.id)
    await ctx.send(f"Your current winning streak: {s}")

@bot.command(name="leaderboard")
async def leaderboard(ctx):
    leaderboard_list = []
    for uid, info in data.items():
        trades = info.get("trades", [])
        if trades:
            avg_rr = sum(t["rr"] for t in trades)/len(trades)
            leaderboard_list.append((uid, avg_rr))
    leaderboard_list.sort(key=lambda x: x[1], reverse=True)
    msg = "**Leaderboard (Avg R:R)**\n"
    for i, (uid, rr) in enumerate(leaderboard_list[:10], start=1):
        user = await bot.fetch_user(int(uid))
        msg += f"{i}. {user.name} - Avg R:R: {round(rr,2)}\n"
    await ctx.send(msg)

@bot.command(name="dailystats")
async def dailystats(ctx):
    trades = filter_trades_by_period(ctx.author.id, 1)
    if not trades:
        await ctx.send("No trades today!")
        return
    avg_rr = round(sum(t["rr"] for t in trades)/len(trades),2)
    await ctx.send(f"Today's Trades: {len(trades)}\nAverage R:R: {avg_rr}")

@bot.command(name="weeklystats")
async def weeklystats(ctx):
    trades = filter_trades_by_period(ctx.author.id, 7)
    if not trades:
        await ctx.send("No trades this week!")
        return
    avg_rr = round(sum(t["rr"] for t in trades)/len(trades),2)
    await ctx.send(f"This Week's Trades: {len(trades)}\nAverage R:R: {avg_rr}")

@bot.command(name="monthlystats")
async def monthlystats(ctx):
    trades = filter_trades_by_period(ctx.author.id, 30)
    if not trades:
        await ctx.send("No trades this month!")
        return
    avg_rr = round(sum(t["rr"] for t in trades)/len(trades),2)
    await ctx.send(f"This Month's Trades: {len(trades)}\nAverage R:R: {avg_rr}")

@bot.command(name="lifetimestats")
async def lifetimestats(ctx):
    trades = get_user_trades(ctx.author.id)
    if not trades:
        await ctx.send("No trades yet!")
        return
    avg_rr = round(sum(t["rr"] for t in trades)/len(trades),2)
    await ctx.send(f"Lifetime Trades: {len(trades)}\nAverage R:R: {avg_rr}")

@bot.command(name="calendar")
async def calendar(ctx):
    today = datetime.date.today()
    await ctx.send(f"Trading Calendar:\nToday: {today}")

@bot.command(name="resetstats")
async def resetstats(ctx):
    uid = str(ctx.author.id)
    if uid in data:
        data[uid] = {"trades": [], "streak": 0}
        save_data(data)
        await ctx.send("Your stats have been reset.")
    else:
        await ctx.send("No stats to reset!")

@bot.command(name="allresetstats")
async def allresetstats(ctx):
    if ctx.author.guild_permissions.administrator:
        data.clear()
        save_data(data)
        await ctx.send("All user stats have been reset by admin!")
    else:
        await ctx.send("You are not an admin!")

# ---- DAILY BACKUP TASK ----
@tasks.loop(hours=24)
async def daily_backup():
    save_data(data)
    print("Daily backup saved.")

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    daily_backup.start()

# ---- RUN BOT ----
bot.run(TOKEN)

