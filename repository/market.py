from time import time
from datetime import datetime
import math
import collections
import os
from secrets import CC_API_KEY
os.environ['CRYPTOCOMPARE_API_KEY'] = CC_API_KEY
from cryptocompare import cryptocompare
from sqlitedict import SqliteDict

class MarketRepository(object):
    def __init__(self, log):
        self.log = log
        # cryptocompare._set_api_key_parameter(CC_API_KEY)
        self.db = SqliteDict(os.path.join('data', 'prices.sqlite'), autocommit=True)

    def get_symbols(self):
        if 'symbols' not in self.db:
            self.db['symbols'] = cryptocompare.get_coin_list()
        return self.db['symbols']

    TSYMS = ['BTC','USD','EUR','SEK','IRR','JPY','CNY','GBP','CAD','AUD','RUB','INR','USDT','ETH']
    def is_pair_valid(self, fsym, tsym):
        return fsym in self.get_symbols().keys() and tsym in self.TSYMS

    def fetch_data(self, fsym, tsym, time):
        data = cryptocompare.get_historical_price_minute(fsym, tsym, limit=2000, exchange='CCCAGG', toTs=time)
        for point in data:
            key = f"{fsym}/{tsym}@{point['time']}"
            del point['conversionType']
            del point['conversionSymbol']
            self.db[key] = point

    def get_price(self, fsym, tsym, time):
        if not self.is_pair_valid(fsym, tsym):
            self.log.debug(f"price pair not valid {fsym} {tsym}")
            return None
        time = time.replace(second=0, microsecond=0)
        key = f'{fsym}/{tsym}@{int(time.timestamp())}'
        if key not in self.db:
            self.fetch_data(fsym, tsym, time)
        assert key in self.db
        return self.db[key]['close']

if __name__ == "__main__":
    pass
