import discord
from discord.ext import commands
import os, json
from datetime import datetime, timedelta, timezone
from flask import Flask
import threading
import asyncio

# ===================== CONFIG =====================
DATA_FILE = "trades.json"
TOKEN = os.getenv("DISCORD_TOKEN")

# ===================== DATA HELPERS =====================
def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

trade_data = load_data()

def ensure_user(uid):
    if uid not in trade_data:
        trade_data[uid] = {"trades": []}

def log_trade(uid, record):
    ensure_user(uid)
    trade_data[uid]["trades"].append(record)
    save_data(trade_data)

# ===================== DISCORD BOT =====================
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=["!", "/"], intents=intents)

# ===================== KEEP ALIVE (Optional for Background Worker) =====================
app = Flask("")

@app.route("/")
def home():
    return "TradeBot is vibin'!"

def run_web():
    app.run(host="0.0.0.0", port=8000)

def keep_alive():
    t = threading.Thread(target=run_web, daemon=True)
    t.start()

# ===================== UTILS =====================
def compute_rr(entry, sl, tp):
    if sl is None or tp is None:
        return 0.0
    risk = abs(entry - sl)
    reward = abs(tp - entry)
    if risk == 0: return 0.0
    return round(reward / risk, 2)

def filter_trades(trades, period):
    now = datetime.now(timezone.utc)
    if period == "daily":
        cutoff = now - timedelta(days=1)
    elif period == "weekly":
        cutoff = now - timedelta(days=7)
    elif period == "monthly":
        cutoff = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        return trades
    return [t for t in trades if datetime.fromisoformat(t["timestamp"]) > cutoff]

def stats_summary(trades):
    total = len(trades)
    wins = sum(1 for t in trades if t["result"] == "tp")
    losses = sum(1 for t in trades if t["result"] == "sl")
    neutral = total - wins - losses
    total_rr = sum(t["rr"] for t in trades)
    avg_rr = (total_rr / total) if total > 0 else 0.0
    win_rate = (wins / (total - neutral) * 100) if (total - neutral) > 0 else 0.0
    return total, wins, losses, neutral, total_rr, avg_rr, win_rate

# ===================== COMMANDS =====================
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

@bot.command()
async def ping(ctx):
    await ctx.send("🏓 Boing! I'm alive and kickin'!")

@bot.command()
async def trade(ctx, symbol, action, entry, sl=None, tp=None, action_type="none"):
    try:
        user_id = str(ctx.author.id)
        entry = float(entry)
        sl = float(sl) if sl is not None else None
        tp = float(tp) if tp is not None else None
        
        if sl is None and tp is None:
            await ctx.send("❌ Please provide at least a stop-loss (SL) or take-profit (TP). Use: !trade <symbol> <buy/sell> <entry> [sl] [tp] [tp/sl/none]")
            return
        
        timestamp = datetime.now(timezone.utc).isoformat()
        rr = compute_rr(entry, sl, tp)
        record = {
            "pair": symbol.lower(),
            "dir": action.lower(),
            "entry": entry,
            "sl": sl,
            "tp": tp,
            "result": action_type.lower(),
            "rr": rr,
            "timestamp": timestamp
        }
        log_trade(user_id, record)
        
        if action_type.lower() == "tp":
            result_msg = "TP reached!"
        elif action_type.lower() == "sl":
            result_msg = "SL hit!"
        else:
            result_msg = "Pending"
            
        msg = f"🎉 Nice one! {symbol.upper()} {action.upper()} is logged 🎉 RR: +{rr:.2f} 🚀 ({result_msg})"
        await ctx.send(msg)
    except ValueError:
        await ctx.send("❌ Error: Entry, SL, and TP must be numbers. Use: !trade <symbol> <buy/sell> <entry> [sl] [tp] [tp/sl/none]")
    except Exception as e:
        await ctx.send(f"❌ Unexpected error in trade command: {str(e)}")

@bot.command()
async def stats(ctx):
    user_id = str(ctx.author.id)
    trades = trade_data.get(user_id, {}).get("trades", [])
    if not trades:
        await ctx.send("📊 No trades yet, champ!")
        return
    total, wins, losses, neutral, total_rr, avg_rr, win_rate = stats_summary(trades)
    await ctx.send(f"**{ctx.author.name} — Lifetime Stats** | Trades: {total} | Wins: {wins} | Losses: {losses} | Neutral: {neutral} | Total RR: {total_rr:+.2f} | Avg RR: {avg_rr:.2f} | Win Rate: {win_rate:.1f}%")

@bot.command()
async def dailystats(ctx):
    user_id = str(ctx.author.id)
    trades = filter_trades(trade_data.get(user_id, {}).get("trades", []), "daily")
    if not trades:
        await ctx.send("📅 No trades in the last 24 hours!")
        return
    total, wins, losses, neutral, total_rr, avg_rr, win_rate = stats_summary(trades)
    await ctx.send(f"**{ctx.author.name} — Daily Stats** | Trades: {total} | Wins: {wins} | Losses: {losses} | Neutral: {neutral} | Total RR: {total_rr:+.2f} | Avg RR: {avg_rr:.2f} | Win Rate: {win_rate:.1f}%")

@bot.command()
async def weeklystats(ctx):
    user_id = str(ctx.author.id)
    trades = filter_trades(trade_data.get(user_id, {}).get("trades", []), "weekly")
    if not trades:
        await ctx.send("📅 No trades in the last 7 days!")
        return
    total, wins, losses, neutral, total_rr, avg_rr, win_rate = stats_summary(trades)
    await ctx.send(f"**{ctx.author.name} — Weekly Stats** | Trades: {total} | Wins: {wins} | Losses: {losses} | Neutral: {neutral} | Total RR: {total_rr:+.2f} | Avg RR: {avg_rr:.2f} | Win Rate: {win_rate:.1f}%")

@bot.command()
async def monthlystats(ctx):
    user_id = str(ctx.author.id)
    trades = filter_trades(trade_data.get(user_id, {}).get("trades", []), "monthly")
    if not trades:
        await ctx.send("📅 No trades this month!")
        return
    total, wins, losses, neutral, total_rr, avg_rr, win_rate = stats_summary(trades)
    await ctx.send(f"**{ctx.author.name} — Monthly Stats** | Trades: {total} | Wins: {wins} | Losses: {losses} | Neutral: {neutral} | Total RR: {total_rr:+.2f} | Avg RR: {avg_rr:.2f} | Win Rate: {win_rate:.1f}%")

@bot.command()
async def leaderboard(ctx):
    all_trades = []
    for uid in trade_data:
        all_trades.extend(trade_data[uid]["trades"])
    if not all_trades:
        await ctx.send("🏆 No trades to rank!")
        return
    sorted_trades = sorted(all_trades, key=lambda t: t["rr"], reverse=True)[:5]
    text = "🏆 **Leaderboard of Legends**\n"
    for i, t in enumerate(sorted_trades, 1):
        user = bot.get_user(int(t.get("user_id", "0"))) or "Unknown"
        text += f"{i}. {user.name} - {t['pair'].upper()} {t['dir'].upper()} RR: {t['rr']:+.2f}\n"
    await ctx.send(text)

@bot.command()
async def besttrade(ctx):
    user_id = str(ctx.author.id)
    trades = trade_data.get(user_id, {}).get("trades", [])
    if not trades:
        await ctx.send("❌ No trades to brag about!")
        return
    best = max(trades, key=lambda t: t["rr"])
    await ctx.send(f"🌟 **GLORIOUS VICTORY!** {best['pair']} {best['dir']} RR {best['rr']:+.2f}")

@bot.command()
async def worsttrade(ctx):
    user_id = str(ctx.author.id)
    trades = trade_data.get(user_id, {}).get("trades", [])
    if not trades:
        await ctx.send("❌ No trades to mourn!")
        return
    worst = min(trades, key=lambda t: t["rr"])
    await ctx.send(f"💀 **OUCH! EPIC FAIL!** {worst['pair']} {worst['dir']} RR {worst['rr']:+.2f}")

@bot.command()
async def streak(ctx):
    user_id = str(ctx.author.id)
    trades = trade_data.get(user_id, {}).get("trades", [])
    if not trades:
        await ctx.send("📊 No trades for a streak!")
        return
    streak = 0
    for t in reversed(trades):
        if t["result"] == "tp": streak += 1
        else: break
    await ctx.send(f"🔥 **WIN STREAK ALERT!** {streak} in a row!")

@bot.command()
async def resetstats(ctx, arg=None):
    user_id = str(ctx.author.id)
    if arg == "all":
        if ctx.author.guild_permissions.administrator:
            await ctx.send("⚠️ Confirm reset all with `!resetstats confirm` or `/resetstats confirm`\n✓ Admin check passed.")
            return
        else:
            await ctx.send("❌ Only admins can reset all stats!")
            return
    if arg == "confirm" and ctx.author.guild_permissions.administrator:
        trade_data.clear()
        save_data(trade_data)
        await ctx.send("✅ All stats wiped! Fresh start for everyone.\n✓ Data saved.")
        return
    trade_data[user_id] = {"trades": []}
    save_data(trade_data)
    await ctx.send("✅ Your stats are reset! New beginning.\n✓ Data saved.")

@bot.command()
async def calendar(ctx):
    user_id = str(ctx.author.id)
    trades = trade_data.get(user_id, {}).get("trades", [])
    if not trades:
        await ctx.send("📅 No trade history to tell!")
        return
    trades_by_day = {}
    for t in trades:
        d = datetime.fromisoformat(t["timestamp"]).strftime("%Y-%m-%d")
        trades_by_day.setdefault(d, []).append(t)
    text = "📖 **Trade Adventure Log**\n"
    for d, ts in trades_by_day.items():
        total_rr = sum(x["rr"] for x in ts)
        text += f"On {d}, you rocked {len(ts)} trades with a total RR of {total_rr:+.2f}!\n"
    await ctx.send(text)

# ===================== GLOBAL ERROR HANDLING =====================
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ Missing required argument. Check your command syntax!")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("❌ Invalid argument. Ensure numbers are used where required!")
    elif isinstance(error, commands.CommandNotFound):
        await ctx.send("❌ Unknown command. Type !help for available commands!")
    else:
        await ctx.send(f"❌ An unexpected error occurred: {str(error)}")
        print(f"Error: {str(error)}")  # Log to console for debugging

# ===================== RUN =====================
if __name__ == "__main__":
    if not TOKEN:
        print("❌ Set DISCORD_TOKEN in environment variables.")
    else:
        keep_alive()
        bot.run(TOKEN)
