from time import time
from datetime import datetime, timedelta
import math
import collections
import os
from exceptions import InvalidPairException
# from secrets import CC_API_KEY
# os.environ['CRYPTOCOMPARE_API_KEY'] = CC_API_KEY
# from cryptocompare import cryptocompare
from secrets import BINANCE_API_KEY, BINANCE_SECRET_KEY
from binance import Client, ThreadedWebsocketManager, ThreadedDepthCacheManager
from config import PRICES_DB_FILENAME
from sqlitedict import SqliteDict
import logger_config

class MarketRepository(object):
    def __init__(self):
        self.log = logger_config.get_logger(__name__)
        # cryptocompare._set_api_key_parameter(CC_API_KEY)
        self.db = SqliteDict(PRICES_DB_FILENAME)
        self.bnb = Client(BINANCE_API_KEY, BINANCE_SECRET_KEY)
        tot_pairs = sum(1 for k in self.db.keys() if k.endswith("@last_available"))
        self.log.info(f"Loaded market db with {len(self.db)-tot_pairs} minute prices loaded from {tot_pairs} pairs")
        # self.symbols = cryptocompare.get_coin_list()

    def fetch_data(self, fsym, tsym, time):
        last_key = f'{fsym}/{tsym}@last_available'
        if last_key in self.db and time>self.db[last_key] and time-self.db[last_key] < timedelta(minutes=500):
            self.log.debug(f'Querying last minutes to binance for symbol {fsym}{tsym}')
            start = self.db[last_key]
            end = min(datetime.now(), start + timedelta(minutes=501))
            limit=500+50
        else:
            self.log.debug(f'Long querying to binance for symbol {fsym}{tsym}, datetime={time}, last_key={last_key}')
            if last_key in self.db:
                self.log.debug(f"result={self.db[last_key]}")
                self.log.debug(f"result={time>self.db[last_key] and time-self.db[last_key] < timedelta(minutes=500)}")
                self.log.debug(f"result={time-self.db[last_key] < timedelta(minutes=500)}")
                self.log.debug(f"result={time-self.db[last_key]}")
                self.log.debug(f"result={timedelta(minutes=500)}")
            if time.hour>=12:
                start = time.replace(hour=12)
            else:
                start = time.replace(hour=0)
            end = start+timedelta(hours=12)+timedelta(minutes=1)
            limit=12*60+1+10
        assert limit<=1000
        self.log.info(f"Querying Binance for {fsym}{tsym} start={start}, end={end}")
        data = self.bnb.get_historical_klines(
                f"{fsym}{tsym}",
                Client.KLINE_INTERVAL_1MINUTE,
                int(start.timestamp())*1000,
                int(end.timestamp())*1000,
                limit=limit
            )
        self.add_data(fsym, tsym, data)

    def add_data(self, fsym, tsym, data):
        mx = 0
        for point in data:
            time = point[0]//1000
            key = f"{fsym}/{tsym}@{time}"
            mx = max(mx, time)
            cols = "open,high,low,close,volume".split(',')
            self.db[key] = {
                name: float(point[pos+1]) for pos,name in enumerate(cols)
            }
        last_key = f'{fsym}/{tsym}@last_available'
        end = datetime.fromtimestamp(mx)
        if last_key in self.db:
            self.db[last_key] = max(self.db[last_key], end)
        else:
            self.db[last_key] = end
        self.db.commit()

    # def fetch_data_cc(self, fsym, tsym, time):
    #     data = cryptocompare.get_historical_price_minute(fsym, tsym, limit=2000, exchange='CCCAGG', toTs=time)
    #     for point in data:
    #         key = f"{fsym}/{tsym}@{point['time']}"
    #         del point['conversionType']
    #         del point['conversionSymbol']
    #         self.db[key] = point
    #     self.db.commit()

    def get_values(self, fsym, tsym, time):
        time = time.replace(second=0, microsecond=0)
        key = f'{fsym}/{tsym}@{int(time.timestamp())}'
        if key not in self.db:
            self.fetch_data(fsym, tsym, time)
        assert key in self.db, f"Couldn't get price for {key}"
        return self.db[key]

if __name__ == "__main__":
    pass
