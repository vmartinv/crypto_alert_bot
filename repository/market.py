from time import time
from datetime import datetime, timedelta
import math
import collections
import os
from secrets import CC_API_KEY
os.environ['CRYPTOCOMPARE_API_KEY'] = CC_API_KEY
from cryptocompare import cryptocompare
from secrets import BINANCE_API_KEY, BINANCE_SECRET_KEY
from binance import Client, ThreadedWebsocketManager, ThreadedDepthCacheManager
from config import PRICES_DB_FILENAME
from sqlitedict import SqliteDict

class MarketRepository(object):
    def __init__(self, log):
        self.log = log
        # cryptocompare._set_api_key_parameter(CC_API_KEY)
        self.db = SqliteDict(PRICES_DB_FILENAME)
        self.bnb = Client(BINANCE_API_KEY, BINANCE_SECRET_KEY)
        self.symbols = cryptocompare.get_coin_list()

    TSYMS = ['BTC','USD','EUR','SEK','IRR','JPY','CNY','GBP','CAD','AUD','RUB','INR','USDT','ETH','BUSD']
    def is_pair_valid(self, fsym, tsym):
        return fsym in self.symbols.keys() and tsym in self.TSYMS

    def fetch_data(self, fsym, tsym, time):
        last_key = f'{fsym}/{tsym}@last_available'
        if last_key in self.db and time>self.db[last_key] and time-self.db[last_key] < timedelta(minutes=500):
            self.log.info(f'Querying last 10 minutes to binance for symbol {fsym}{tsym}')
            start = self.db[last_key]
            end = min(datetime.now(), start + timedelta(minutes=501))
            limit=500+50
        else:
            self.log.info(f'Long querying to binance for symbol {fsym}{tsym}, datetime={time}')
            if time.hour>=12:
                start = time.replace(hour=12)
            else:
                start = time.replace(hour=0)
            end = start+timedelta(hours=12)+timedelta(minutes=1)
            limit=12*60+1+10
        assert limit<=1000
        data = self.bnb.get_historical_klines(
                f"{fsym}{tsym}",
                Client.KLINE_INTERVAL_1MINUTE,
                int(start.timestamp())*1000,
                int(end.timestamp())*1000,
                limit=limit
            )
        if last_key in self.db:
            self.db[last_key] = max(self.db[last_key], end)
        else:
            self.db[last_key] = end
        self.add_data(fsym, tsym, data)

    def add_data(self, fsym, tsym, data):
        for point in data:
            key = f"{fsym}/{tsym}@{point[0]//1000}"
            cols = "open,high,low,close,volume".split(',')
            self.db[key] = {
                name: float(point[pos+1]) for pos,name in enumerate(cols)
            }
        self.db.commit()

    def fetch_data_cc(self, fsym, tsym, time):
        data = cryptocompare.get_historical_price_minute(fsym, tsym, limit=2000, exchange='CCCAGG', toTs=time)
        for point in data:
            key = f"{fsym}/{tsym}@{point['time']}"
            del point['conversionType']
            del point['conversionSymbol']
            self.db[key] = point

    def get_values(self, fsym, tsym, time):
        if not self.is_pair_valid(fsym, tsym):
            self.log.debug(f"price pair not valid {fsym} {tsym}")
            return None
        time = time.replace(second=0, microsecond=0)
        key = f'{fsym}/{tsym}@{int(time.timestamp())}'
        if key not in self.db:
            self.fetch_data(fsym, tsym, time)
        assert key in self.db
        return self.db[key]

if __name__ == "__main__":
    pass
