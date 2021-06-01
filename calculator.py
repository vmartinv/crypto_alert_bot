from repository.market import MarketRepository
from datetime import datetime, timedelta
from sqlitedict import SqliteDict
import logger_config

class Calculator:
    def __init__(self, repository):
        self.repository = repository
        self.log = logger_config.get_logger(__name__)

    def price(self, fsym, tsym, candle, t):
        return self.repository.get_values(fsym, tsym, t)[candle]

    def change(self, fun, interval, t):
        old = fun(t-timedelta(minutes=interval))
        return (fun(t)-old)/old

    @staticmethod
    def adj(upwards, v):
        if upwards is not None and (v>0 and not upwards) or (v<0 and upwards):
            return 0
        return v

    def sma(self, fun, window, interval, time, upwards=None):
        sma_first = time - timedelta(minutes = window*interval)
        sum_closes = sum(Calculator.adj(upwards, fun(sma_first + timedelta(minutes = (x+1)*interval))) for x in range(window))
        return sum_closes / window

    def smma(self, fun, window, interval, time, rec, alpha, upwards=None):
        smma_prev = time - timedelta(minutes = interval)
        smma = rec(smma_prev)
        if smma is None:
            self.log.info(f"Calculating smma from scratch for window={window}, interval={interval}, time={time}")
            smma_prev = time - timedelta(minutes = window*interval*2)
            smma = self.sma(fun, window, interval, smma_prev, upwards=upwards)
        while smma_prev < time:
            smma_prev += timedelta(minutes = interval)
            today = Calculator.adj(upwards, fun(smma_prev))
            smma = today * alpha + smma * (1-alpha)
        return smma
