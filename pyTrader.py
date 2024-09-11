import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime
import time

class GoldTrader:
    def __init__(self):
        mt5.initialize()
        self.SYMBOL = "XAUUSD"
        self.TIMEFRAME = mt5.TIMEFRAME_M5
        self.EMA_PERIOD = 12
        self.TP_PERCENT = 0.0045  # 0.45%
        self.SL_PERCENT = 0.002   # 0.2%
        self.MAGIC = 100
        self.Comment = 'GoldEMA5M'
        self.initial_balance = 2000
        self.risk_percentage = 0.01  # 1% risk per trade
        self.min_account_size = 100000  # $100,000 base for minimum lot size

    def calculate_position_size(self, entry_price, stop_loss_price):
        account_info = mt5.account_info()
        if account_info is None:
            print("Failed to get account info")
            return 0.01

        equity = account_info.equity
        risk_amount = equity * self.risk_percentage

        symbol_info = mt5.symbol_info(self.SYMBOL)
        contract_size = symbol_info.trade_contract_size
        pip_value = contract_size * 0.01  # 1 pip is 0.01 for XAUUSD

        pips_risked = abs(entry_price - stop_loss_price) / symbol_info.point

        position_size = risk_amount / (pips_risked * pip_value)

        # Calculate minimum lot size based on 1% of $100,000
        min_lot_size = (self.min_account_size * self.risk_percentage) / (pips_risked * pip_value)

        # Use the larger of the calculated position size and the minimum lot size
        position_size = max(position_size, min_lot_size)

        position_size = round(position_size, 2)

        min_volume = symbol_info.volume_min
        max_volume = symbol_info.volume_max
        position_size = max(min(position_size, max_volume), min_volume)

        return position_size

    def get_ema(self):
        rates = mt5.copy_rates_from_pos(self.SYMBOL, self.TIMEFRAME, 0, self.EMA_PERIOD + 1)
        df = pd.DataFrame(rates)
        df['ema'] = df['close'].ewm(span=self.EMA_PERIOD, adjust=False).mean()
        return df['ema'].iloc[-1], df['close'].iloc[-1]

    def check_signal(self):
        ema, current_close = self.get_ema()

        if current_close > ema:
            print("Bullish")
            return 1  # Buy signal
        elif current_close < ema:
            print("Bearish")
            return -1  # Sell signal
        else:
            return 0  # No signal

    def open_position(self, signal):
        price = mt5.symbol_info_tick(self.SYMBOL).ask if signal == 1 else mt5.symbol_info_tick(self.SYMBOL).bid
        
        sl = price * (1 - self.SL_PERCENT) if signal == 1 else price * (1 + self.SL_PERCENT)
        tp = price * (1 + self.TP_PERCENT) if signal == 1 else price * (1 - self.TP_PERCENT)
        
        volume = self.calculate_position_size(price, sl)

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.SYMBOL,
            "volume": volume,
            "type": mt5.ORDER_TYPE_BUY if signal == 1 else mt5.ORDER_TYPE_SELL,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": 20,
            "magic": self.MAGIC,
            "comment": self.Comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            print(f"Order sending failed: {result.comment}")
        else:
            print(f"Position opened: {result.comment}")
            print(f"Volume: {volume}, SL: {sl}, TP: {tp}")

    def close_position(self):
        positions = mt5.positions_get(symbol=self.SYMBOL)
        if positions:
            for pos in positions:
                if pos.magic == self.MAGIC:
                    close_request = {
                        "action": mt5.TRADE_ACTION_DEAL,
                        "position": pos.ticket,
                        "symbol": self.SYMBOL,
                        "volume": pos.volume,
                        "type": mt5.ORDER_TYPE_BUY if pos.type == 1 else mt5.ORDER_TYPE_SELL,
                        "price": mt5.symbol_info_tick(self.SYMBOL).bid if pos.type == 0 else mt5.symbol_info_tick(self.SYMBOL).ask,
                        "deviation": 20,
                        "magic": self.MAGIC,
                        "comment": "Position closed",
                        "type_time": mt5.ORDER_TIME_GTC,
                        "type_filling": mt5.ORDER_FILLING_IOC,
                    }
                    result = mt5.order_send(close_request)
                    if result.retcode != mt5.TRADE_RETCODE_DONE:
                        print(f"Failed to close position: {result.comment}")
                    else:
                        print(f"Position closed: {result.comment}")

    def manage_open_position(self, current_signal):
        positions = mt5.positions_get(symbol=self.SYMBOL)
        if positions:
            for position in positions:
                if position.magic == self.MAGIC:
                    print(f"Current position state: Profit: {position.profit}, SL: {position.sl}, TP: {position.tp}")
                    
                    # Check if the position has hit SL or TP
                    current_price = mt5.symbol_info_tick(self.SYMBOL).bid if position.type == 0 else mt5.symbol_info_tick(self.SYMBOL).ask
                    if (position.type == 0 and current_price <= position.sl) or (position.type == 1 and current_price >= position.sl):
                        print("Stop Loss hit. Closing position.")
                        self.close_position()
                    elif (position.type == 0 and current_price >= position.tp) or (position.type == 1 and current_price <= position.tp):
                        print("Take Profit hit. Closing position.")
                        self.close_position()
                    else:
                        print(f"Position maintained. Current signal: {current_signal}")

    def main(self):
        print(f"Starting Gold Trading Bot for {self.SYMBOL} on {self.TIMEFRAME} timeframe")
        print(f"Using {self.EMA_PERIOD}-period EMA strategy")
        print(f"Stop Loss: {self.SL_PERCENT*100}%, Take Profit: {self.TP_PERCENT*100}%")
        print("Bot is now running. Press Ctrl+C to stop.")
        
        last_candle_time = None
        
        while True:
            try:
                current_time = datetime.now()
                
                # Check if it's the start of a new 5-minute candle
                if current_time.minute % 5 == 0 and current_time.second == 0:
                    if last_candle_time != current_time.replace(second=0, microsecond=0):
                        print(f"\nScanning at {current_time}")
                        last_candle_time = current_time.replace(second=0, microsecond=0)
                        
                        signal = self.check_signal()
                        print(f"Signal: {signal} (1: Buy, -1: Sell, 0: No action)")
                        
                        positions = mt5.positions_get(symbol=self.SYMBOL)
                        
                        if not positions and signal != 0:
                            print("No open positions. Attempting to open a new position...")
                            self.open_position(signal)
                        elif positions:
                            print("Position is open. Checking if management is needed...")
                            self.manage_open_position(signal)
                        else:
                            print("No action taken.")
                
                # Optional: Print a dot every minute to show the bot is still running
                if current_time.second == 0:
                    print(".", end="", flush=True)
                
                time.sleep(1)  # Check every second to catch the exact candle close

            except KeyboardInterrupt:
                print('\nKeyboardInterrupt received. Stopping the bot.')
                break
            except Exception as e:
                print(f"\nAn error occurred: {e}")
                print("Waiting for 60 seconds before retrying...")
                time.sleep(60)  # Wait for a minute before retrying

        print("Bot has stopped running.")

if __name__ == '__main__':
    trader = GoldTrader()
    trader.main()
