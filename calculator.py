from repository.market import MarketRepository
from datetime import datetime, timedelta
from sqlitedict import SqliteDict
import logger_config

class Calculator:
    def __init__(self, repository):
        self.repository = repository
        self.log = logger_config.get_logger(__name__)

    def price(self, fsym, tsym, t):
        return self.repository.get_values(fsym, tsym, t)['close']


    def sma(self, fun, window, interval, time):
        sma_first = time - timedelta(minutes = window*interval)
        sum_closes = sum(fun(sma_first + timedelta(minutes = (x+1)*interval - 1)) for x in range(window))
        return sum_closes / window

    def ema(self, fun, window, interval, time, rec):
        ema_prev = time - timedelta(minutes = interval)
        prev = rec(ema_prev)
        weight = 2.0 / (1+window)
        if prev is not None:
            self.log.info(f"Reusing last ema for window={window}, interval={interval}, time={time}")
            ema = prev
            today = fun(time - timedelta(minutes = 1))
            new_ema = today * weight + ema * (1 - weight)
            # self.log.info(f"Obtained ema of {new_ema}")
            return new_ema
        else:
            # time = time.replace(minute = 0)
            ema_first = time - timedelta(minutes = window*interval*2)
            ema = self.sma(fun, window, interval, ema_first)
            self.log.info(f"calculating ema for window={window} , interval={interval}, time={time}")
            # self.log.debug(f"SMA {ema}")
            for x in range(window*2):
                cur = ema_first + timedelta(minutes = (x+1)*interval - 1)
                today = fun(cur)
                ema = today * weight + ema * (1 - weight)
                # self.log.debug(f"EMA({x}) {ema} (cur={cur}, today={today})")
            return ema
