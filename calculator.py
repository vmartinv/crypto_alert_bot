from repository.market import MarketRepository
from datetime import datetime, timedelta
from sqlitedict import SqliteDict
from statistics import mean
from config import INDICATORS_CACHE_DB_FILENAME
import logger_config

class Calculator:
    def __init__(self, repository):
        self.repository = repository
        self.db = SqliteDict(INDICATORS_CACHE_DB_FILENAME, autocommit=True)
        self.log = logger_config.get_logger(__name__)

    def price(self, fsym, tsym, t):
        return self.repository.get_values(fsym, tsym, t)['open']

    def get_or_calc(self, key, f):
        if key not in self.db:
            self.db[key] = f()
        return self.db[key]

    @staticmethod
    def normalize_time(time):
        return time.replace(second = 0, microsecond =0)

    def sma(self, fsym, tsym, window, interval, time):
        time = Calculator.normalize_time(time)
        key = f"sma:{fsym}/{tsym}:{window}:{interval}:{time.timestamp()}"
        def calc():
            sma_first = time - timedelta(minutes = window*interval)
            sum_closes = sum(self.repository.get_values(fsym, tsym, sma_first + timedelta(minutes = (x+1)*interval - 1))['close'] for x in range(window))
            return sum_closes / window
        return self.get_or_calc(key, calc)

    def ema(self, fsym, tsym, window, interval, time):
        time = Calculator.normalize_time(time)
        key = f"ema:{fsym}/{tsym}:{window}:{interval}:{time.timestamp()}"
        def calc():
            ema_prev = time - timedelta(minutes = interval)
            prev_key = f"ema:{fsym}/{tsym}:{window}:{interval}:{ema_prev.timestamp()}"
            weight = 2.0 / (1+window)
            if prev_key in self.db:
                self.log.info(f"Reusing last ema {prev_key} for calculating {key}")
                ema = self.db[prev_key]
                today = self.repository.get_values(fsym, tsym, time - timedelta(minutes = 1))['close']
                new_ema = today * weight + ema * (1 - weight)
                # self.log.info(f"Obtained ema of {new_ema}")
                return new_ema
            else:
                # time = time.replace(minute = 0)
                ema_first = time - timedelta(minutes = window*interval*2)
                ema = self.sma(fsym, tsym, window, interval, ema_first)
                self.log.info(f"calculating ema for window={window} , interval={interval}, pair={fsym}/{tsym}, time={time}")
                # self.log.debug(f"SMA {ema}")
                for x in range(window*2):
                    cur = ema_first + timedelta(minutes = (x+1)*interval - 1)
                    today = self.repository.get_values(fsym, tsym, cur)['close']
                    ema = today * weight + ema * (1 - weight)
                    # self.log.debug(f"EMA({x}) {ema} (cur={cur}, today={today})")
                return ema
        return self.get_or_calc(key, calc)
