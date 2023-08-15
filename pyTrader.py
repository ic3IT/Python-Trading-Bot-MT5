import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime
import time
import numpy as np
import json
from IPython.display import clear_output



class River:
    def __init__(self):
        mt5.initialize()
        # self.login =
        # self.password = ''
        # self.server = ''
        # mt5.login(self.login, self.password, self.server)
        self.SYMBOL = 'CADJPY'
        self.Atr_Perc_tp = 1.5
        self.Atr_Perc_sl = 2.2
        self.TIMEFRAME_15M = mt5.TIMEFRAME_M15
        self.TIMEFRAME_5M = mt5.TIMEFRAME_M5
        self.TIMEFRAME_1H = mt5.TIMEFRAME_H1
        self.RSI_PERIOD = 14
        self.VOLUME = 5.0
        self.MAGIC = 100
        self.Comment = 'River'
        self.sec_to_shift = 14400 # depend of the local time, check the timestamp of mt5 and in your machine to match.
        self.symbol_list = ['AUDUSD', 'CHFJPY', 'EURUSD', 'GBPUSD', 'USDCAD', 'USDCHF',
                            'USDJPY', 'EURCAD', 'GBPJPY', 'AUDCHF', 'AUDCAD', 'AUDJPY',
                            'EURGBP', 'EURAUD', 'EURJPY', 'EURCHF', 'EURNZD', 'AUDNZD',
                            'GBPCHF', 'CADCHF', 'CADJPY', 'GBPAUD', 'GBPCAD',
                            'GBPNZD', 'NZDCAD', 'NZDCHF', 'NZDUSD', 'NZDJPY'] # 29
        self.max_positions = {
            'JPY': 2,
            'USD': 2,
            'AUD': 2,
            'EUR': 2,
            'CAD': 2,
            'NZD': 2,
            'GBP': 2,
            # Add more currency pairs as needed
        }
        self.open_positions = {currency: 0 for currency in self.max_positions.keys()}
        self.last_executed = {}
        for pair in self.symbol_list:
            self.last_executed[pair] = 0


    ''' H I S T O R I C A L   D A T A '''

    # GET DATA (on)
    def Historical(self):
        # Get data from now to back by the numbers of candles
        number_of_candles = 400
        looknow = int(datetime.utcnow().timestamp())
        lookback = (looknow - (number_of_candles * 5)*60) # in sec
        df = pd.DataFrame(mt5.copy_rates_range(self.SYMBOL,self.TIMEFRAME_1H, lookback + self.sec_to_shift, looknow + self.sec_to_shift))

        # Create dataframe
        df = df.drop(['spread','real_volume'],axis=1)
        df = df[['time','open','high','low','close','tick_volume']]
        df['time']=pd.to_datetime(df['time'], unit='s')
        df.reset_index()
        df = df.dropna()

        # pd.set_option('display.max_columns', None)
        # print(df.tail(30))
        return df


    ''' I N D I C A T O R S '''

    def SMA(self, symbol, timeframe, period):
        # Get the rates
        rates = mt5.copy_rates_from(symbol, timeframe, datetime.now(), period)

        # Convert to a DataFrame
        data = pd.DataFrame(rates)

        # Convert time in seconds into the datetime format
        data['time'] = pd.to_datetime(data['time'], unit='s')

        # Get last tick
        last_tick = mt5.symbol_info_tick(symbol).last

        # Append last tick to 'close' column of the dataframe
        data.at[period - 1, 'close'] = last_tick

        # Calculate SMA
        data['SMA'] = data['close'].rolling(window=period).mean()

        # Get the last SMA value
        sma_value = data['SMA'].iloc[-1]

        return sma_value
    # Relative Strength Index (RSI)
    def RSI(self, SYMBOL, timeframe, rsi_period):
        def rsi_tradingview(ohlc: pd.DataFrame, period: int = 14, round_rsi: bool = True):
            delta = ohlc["close"].diff()

            up = delta.copy()
            up[up < 0] = 0
            up = pd.Series.ewm(up, alpha=1 / period).mean()

            down = delta.copy()
            down[down > 0] = 0
            down *= -1
            down = pd.Series.ewm(down, alpha=1 / period).mean()

            rsi = np.where(up == 0, 0, np.where(down == 0, 100, 100 - (100 / (1 + up / down))))

            return np.round(rsi, 2) if round_rsi else rsi

        num_bars = rsi_period + 60
        bars = mt5.copy_rates_from_pos(SYMBOL, timeframe, 1, num_bars)
        bars_df = pd.DataFrame(bars)

        last_close = bars_df.iloc[-1].close

        rsi_values = rsi_tradingview(bars_df, rsi_period)

        rsi_value = rsi_values[-2]

        direction = 'flat'
        if rsi_value < 35:  # Adjusted the RSI threshold
            direction = 'buy'
        elif rsi_value > 65:  # Adjusted the RSI threshold
            direction = 'sell'

        return last_close, rsi_value, direction


    ''' P O S I T I O N   M A N A G E R '''

    # OPEN MARKET POSITION (on)
    def open_market_position(self, s_l, Volume, stop_loss_perc, take_profit_perc):
        volume = self.VOLUME
        current_time = time.time()
        response = None  # initialize response here.


        # The rest of your logic remains the same...
        if s_l == 1:
            current_price = mt5.symbol_info_tick(self.SYMBOL).bid
            stop_loss = current_price - (stop_loss_perc * current_price)
            take_profit = current_price + (take_profit_perc * current_price)
            if self.SYMBOL.startswith('GBP'):
                adjusted_volume = self.VOLUME / 1.25
                print(f"Adjusted volume: {adjusted_volume}")
            else:
                adjusted_volume = self.VOLUME
            if self.SYMBOL.startswith(('CAD', 'NZD', 'AUD')):
                adjusted_volume = self.VOLUME * 1.5
                print(f"Adjusted volume: {adjusted_volume}")
            else:
                adjusted_volume = self.VOLUME
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": self.SYMBOL,
                "volume": adjusted_volume,
                "type": mt5.ORDER_TYPE_BUY,
                "price": current_price,
                "sl": stop_loss,
                "tp": take_profit,
                "deviation": 20,
                "magic": self.MAGIC,
                "comment": self.Comment,
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            response = mt5.order_send(request)

            if response.retcode != mt5.TRADE_RETCODE_DONE:
                print("Trade failed, error code: ", response.retcode)
                # Add more robust error handling here if necessary

        elif s_l == -1:
            current_price = mt5.symbol_info_tick(self.SYMBOL).ask
            stop_loss = current_price + (stop_loss_perc * current_price)
            take_profit = current_price - (take_profit_perc * current_price)
            if self.SYMBOL.startswith('GBP'):
                adjusted_volume = self.VOLUME / 1.25
                print(f"Adjusted volume: {adjusted_volume}")
            else:
                adjusted_volume = self.VOLUME
            if self.SYMBOL.startswith(('CAD', 'NZD', 'AUD')):
                adjusted_volume = self.VOLUME * 1.5
                print(f"Adjusted volume: {adjusted_volume}")
            else:
                adjusted_volume = self.VOLUME
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": self.SYMBOL,
                "volume": adjusted_volume,
                "type": mt5.ORDER_TYPE_SELL,
                "price": current_price,
                "sl": stop_loss,
                "tp": take_profit,
                "deviation": 20,
                "magic": self.MAGIC,
                "comment": self.Comment,
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            response = mt5.order_send(request)

            if response.retcode != mt5.TRADE_RETCODE_DONE:
                print("Trade failed, error code: ", response.retcode)
                # Add more robust error handling here if necessary

        return response

    # CLOSE MARKET POSITION (off)
    def close_position(self, s_l):
        # mt5.positions_get()[0][0]

        if (s_l == 1):
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": self.SYMBOL,
                "volume": self.VOLUME, # FLOAT
                "type": mt5.ORDER_TYPE_BUY,
                "position": mt5.positions_get(symbol=self.SYMBOL)[0][0],
                "price": mt5.symbol_info_tick(self.SYMBOL).bid,
                "sl": 0.0, # FLOAT
                "tp": 0.0, # FLOAT
                "deviation": 20, # INTERGER
                "magic": self.MAGIC,
                "comment": self.Comment,
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,}

            response = mt5.order_send(request)
            return response

        if (s_l == -1):
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": self.SYMBOL,
                "volume": self.VOLUME, # FLOAT
                "type": mt5.ORDER_TYPE_SELL,
                "position": mt5.positions_get(symbol=self.SYMBOL)[0][0],
                "price": mt5.symbol_info_tick(self.SYMBOL).ask,
                "sl": 0.0, # FLOAT
                "tp": 0.0, # FLOAT
                "deviation": 20, # INTERGER
                "magic": self.MAGIC,
                "comment": self.Comment,
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,}

            response = mt5.order_send(request)
            # print(response)
            return response


    # GET POSITION CURRENTLY OPEN (on)
    def get_opened_positions(self, SYMBOL):
        self.SYMBOL = SYMBOL

        if len(mt5.positions_get(symbol = self.SYMBOL)) == 0:
            return ''

        # 0 == buy, 1 == sell
        elif len(mt5.positions_get(symbol = self.SYMBOL)) > 0:
            positions = pd.DataFrame(mt5.positions_get(symbol = self.SYMBOL)[0])
            side = positions[0][5] # type, buy or sell, 0 or 1
            entryprice = positions[0][10]
            profit = positions[0][15]
            ticket_ID = positions[0][0] # ID positon

            if side == 0:
                pos = 1
                return [pos, side,profit,entryprice, ticket_ID]

            elif side == 1:
                pos = -1

                return ([pos, side, profit, entryprice, ticket_ID])

            else:
                return 'NONE'
        else:
            return 'NONE'


    ''' C H E C K   S I G N A L S '''

    def check_signal(self, SYMBOL):
        self.SYMBOL = SYMBOL

        last_close, rsi, direction = self.RSI(SYMBOL, self.TIMEFRAME_1H, self.RSI_PERIOD)

        sma_value = self.SMA(SYMBOL, self.TIMEFRAME_1H, 200)  # Call the SMA function

        if direction == 'buy' and last_close > sma_value:
            SIGNAL = 1  # Buy signal
        elif direction == 'sell' and last_close < sma_value:
            SIGNAL = -1  # Sell signal
        else:
            SIGNAL = 0  # No signal

        return SIGNAL

    # REMOVE ALL STOP LOSS (on)
    def remove_sl(self, SYMBOL, pos):
        self.SYMBOL = SYMBOL
        Openedd = mt5.positions_get(symbol = SYMBOL)
        Positions_Opened = [ pos for pos in Openedd ]
        for pos in Openedd:
            # print(pos.ticket)
            request = {
                "action": mt5.TRADE_ACTION_SLTP,
                "symbol": self.SYMBOL,
                "position": pos.ticket,
                "sl": 0.0 if pos.sl > 0.0 or pos.sl != "" else None,
                "tp": pos.tp}

            response = mt5.order_send(request)
            return response

    ''' E X E C U T I O N '''

    # BUY or SELL (on)
    def main(self, step):
        for SYMBOL in self.symbol_list:
            # ------- close all ------- #
            POSITIONS = self.get_opened_positions(SYMBOL)
            CLOSE_ALL = False  # switch to True for execute
            if CLOSE_ALL:
                Opened = mt5.positions_get(symbol=SYMBOL)
                for pos in Opened:
                    self.close_all_positions(SYMBOL, pos)

            POSITIONS = self.get_opened_positions(SYMBOL)
            Openedd = mt5.positions_get(symbol=SYMBOL)
            Pendingg = mt5.orders_get(symbol=SYMBOL)

            Tot_Len = len(Pendingg) + len(Openedd)
            signal = self.check_signal(SYMBOL)

            if CLOSE_ALL is False:
                # Limit the number of open positions
                if signal != 0 and any(currency in SYMBOL for currency in self.max_positions.keys()):
                    involved_currencies = [currency for currency in self.max_positions.keys() if currency in SYMBOL]
                    for currency in involved_currencies:
                        if self.open_positions.get(currency, 0) >= self.max_positions[currency]:
                            continue

                # LOOKING FOR PATTERN
                if POSITIONS == '' and len(Openedd) < 1:
                    try:
                        if signal == 1:
                            stop_loss_perc = 0.0015  # Stop loss as a percentage
                            take_profit_perc = 0.0015  # Take profit as a percentage

                            self.open_market_position(1, self.VOLUME, stop_loss_perc, take_profit_perc)
                            print(f'1L1 - Long Opened {SYMBOL}')
                            self.last_executed[SYMBOL] = int(time.time())

                        elif signal == -1:
                            stop_loss_perc = 0.0015  # Stop loss as a percentage
                            take_profit_perc = 0.0015  # Take profit as a percentage

                            self.open_market_position(-1, self.VOLUME, stop_loss_perc, take_profit_perc)
                            print(f'1S1 - Short Opened {SYMBOL}')
                            self.last_executed[SYMBOL] = int(time.time())

                            involved_currencies = [currency for currency in self.max_positions.keys() if
                                                   currency in SYMBOL]
                            for currency in involved_currencies:
                                if currency not in self.open_positions:
                                    self.open_positions[currency] = 1
                                else:
                                    self.open_positions[currency] += 1

                    except:
                        print('Could not open new position')

    # EXECUTE MAIN - BUY or SELL (on)
    def execution_main(self):
        import datetime

        TIMEFRAME = mt5.TIMEFRAME_H1
        RSI_PERIOD = 14

        # The broker cause massive spread during the closing and open time of the market and
        # this more often burn all the stop losses of the position if using timeframe of 10min or less.
        # To avoid this, just before the market close, stop searching for signals and remove all the stop losses.
        # After about 1 hour from the open when the spread came to normal re-add the stop losses and start searching for signal.


        counterr = 1
        print(f'Looking for pattern in {self.symbol_list}...')
        while True:
                # stop executing until:
            current_time = datetime.datetime.now().time()
            if current_time > datetime.time(23, 45) or current_time <= datetime.time(23, 46):
                try:
                    for SYMBOL in self.symbol_list:

                        self.main(counterr)
                        counterr = counterr + 1
                        if counterr > 5:
                            counterr = 1
                        last_close, rsi, direction = self.RSI(SYMBOL, TIMEFRAME, RSI_PERIOD)
                        print(f"Looping through {SYMBOL} RSI: {rsi}")
                        time.sleep(2.8)


                except KeyboardInterrupt:
                    print('\n\KeyboardInterrupt. Stopping.')
                    exit()
            else:
                print('Starting again at 23:35')
                time.sleep(180)
                continue



if __name__ == '__main__':
    Trade = River()
    Trade.execution_main()
