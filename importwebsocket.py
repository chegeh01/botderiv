import websocket
import json
import time
import pandas as pd
import numpy as np
import logging
from datetime import datetime

# === CONFIGURATION === #
API_TOKEN = "your_api_token_here"  # Secure API key
TRADE_SYMBOL = "R_100"  # Volatility 100 Index
RISK_PER_TRADE = 0.02  # 2% Risk per trade
COOLDOWN_PERIOD = 300  # CoEoldown in seconds (5 min)
DAILY_STOP_LOSS = 5  # Max % loss per day before disabling trading
SESSION_FILTER = ["London", "NY", "Asian"]  # Session-based trading
ENABLE_STEALTH_MODE = True  # Hide SL/TP from broker
ENABLE_VOLATILITY_PROTECTION = True  # Avoid trades in extreme spikes

# === LOGGING SETUP === #
logging.basicConfig(filename="trade_logs.log", level=logging.INFO, format="%(asctime)s - %(message)s")

# === WebSocket Connection === #
ws = None
is_trading_enabled = True
last_trade_time = None
balance = 1000  # Assume starting balance
open_trades = []

# === ATR Calculation === #
def calculate_atr(data, period=14):
    data['TR'] = np.maximum((data['High'] - data['Low']), np.abs(data['High'] - data['Close'].shift(1)), np.abs(data['Low'] - data['Close'].shift(1)))
    data['ATR'] = data['TR'].rolling(period).mean()
    return data['ATR'].iloc[-1]

# === Lot Sizing === #
def calculate_lot_size(balance, risk_per_trade, stop_loss):
    return (balance * risk_per_trade) / stop_loss

# === Market Session Check === #
def is_correct_trading_session():
    current_hour = datetime.utcnow().hour
    if "London" in SESSION_FILTER and 7 <= current_hour <= 16:
        return True
    if "NY" in SESSION_FILTER and 13 <= current_hour <= 21:
        return True
    if "Asian" in SESSION_FILTER and (0 <= current_hour <= 6 or 22 <= current_hour <= 23):
        return True
    return False

# === Smart Entry Filter === #
def check_trade_conditions(data):
    """ Implements Scalping, Breakout & Trend-Following conditions """
    atr = calculate_atr(data)
    last_close = data["Close"].iloc[-1]
    last_high = data["High"].iloc[-1]
    last_low = data["Low"].iloc[-1]

    # Breakout Strategy
    if last_close > last_high - (0.2 * atr):
        return "BUY"
    elif last_close < last_low + (0.2 * atr):
        return "SELL"

    # Trend-Following Strategy (Using EMA)
    ema_50 = data["Close"].rolling(50).mean().iloc[-1]
    ema_200 = data["Close"].rolling(200).mean().iloc[-1]
    
    if last_close > ema_50 > ema_200:
        return "BUY"
    elif last_close < ema_50 < ema_200:
        return "SELL"

    return None

# === WebSocket Callbacks === #
def on_open(ws):
    print("Connected to Deriv API")
    auth_data = {"authorize": API_TOKEN}
    ws.send(json.dumps(auth_data))

def on_message(ws, message):
    global balance, is_trading_enabled, last_trade_time, open_trades
 
    data = json.loads(message)
    
    if "authorize" in data:
        print("Authorized Successfully!")
        ws.send(json.dumps({"balance": 1}))  # Request balance
    
    if "balance" in data:
        balance = data["balance"]["balance"]
        print(f"Current Balance: ${balance}")

    # Market Data Stream
    if "tick" in data:
        symbol = data["tick"]["symbol"]
        price = float(data["tick"]["quote"])
        print(f"{symbol} Price: {price}")

        # Get historical market data
        market_data = fetch_historical_data()
        trade_signal = check_trade_conditions(market_data)

        if trade_signal and is_correct_trading_session():
            if last_trade_time and (time.time() - last_trade_time < COOLDOWN_PERIOD):
                print("Cooldown active, skipping trade...")
                return
            
            lot_size = calculate_lot_size(balance, RISK_PER_TRADE, calculate_atr(market_data))
            execute_trade(trade_signal, lot_size)

def fetch_historical_data():
    """ Simulates fetching market data """
    data = {
        "Close": np.random.uniform(1000, 1100, 50),
        "High": np.random.uniform(1050, 1150, 50),
        "Low": np.random.uniform(950, 1050, 50)
    }
    return pd.DataFrame(data)

# === Trade Execution === #
def execute_trade(direction, lot_size):
    global last_trade_time, open_trades

    print(f"Executing {direction} trade with {lot_size} lot size")
    trade_data = {
        "buy" if direction == "BUY" else "sell": 1,
        "symbol": TRADE_SYMBOL,
        "amount": lot_size,
        "stop_loss": None if ENABLE_STEALTH_MODE else 5,
        "take_profit": None if ENABLE_STEALTH_MODE else 10
    }
    
    ws.send(json.dumps(trade_data))
    last_trade_time = time.time()
    open_trades.append(trade_data)
    logging.info(f"Trade Executed: {direction}, Lot Size: {lot_size}")

# === WebSocket Execution === #
def start_trading():
    global ws
    ws = websocket.WebSocketApp("wss://ws.deriv.com/websocket",
                                on_open=on_open,
                                on_message=on_message)
    ws.run_forever()

if __name__ == "__main__":
    start_trading()
