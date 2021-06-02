from lark import Lark, Tree, Transformer
from collections import defaultdict
import logger_config
from repository.market import MarketRepository
from datetime import datetime, timedelta
from sqlitedict import SqliteDict
from statistics import mean
from calculator import Calculator
import logger_config
import types
from exceptions import InvalidIndicatorSource
from config import HANDLER_CACHE_DB_FILENAME

class Evaluator(Transformer):

    def __init__(self, calculator, *args, **kwargs):
        super(Evaluator, self).__init__(*args, **kwargs)
        self.log = logger_config.get_logger(__name__)
        self.calculator = calculator
        self.db = SqliteDict(HANDLER_CACHE_DB_FILENAME, autocommit=True)
        self.log.info(f"Loaded handler cache db with {len(self.db)} entries")

    INT = int
    CNAME = str
    TWO_DIGITS = int
    WORD = str
    INDICATOR = str
    SIGNED_NUMBER = float
    CANDLE_VALS = str

    def number(self, x):
        n = float(x[0])
        return (f"{n:.2E}", lambda t: n)

    def minutes(self, x):
        return int(x[0])

    def hours(self, x):
        return int(x[0])*60

    def days(self, x):
        return int(x[0])*60*24

    def percentage(self, x):
        n = float(x[0])/100
        return (f"{n:.2E}", lambda t: n)

    def MATH_OPERATOR(self, c):
        if c=='+':
            return (c, lambda a,b: a+b)
        elif c=='-':
            return (c, lambda a,b: a-b)
        elif c=='*':
            return (c, lambda a,b: a*b)
        elif c=='/':
            return (c, lambda a,b: a/b)
        raise Exception(f"Unknown MATH_OPERATOR {c}")

    def COMPARATOR(self, c):
        if c=='>':
            return (c, lambda a,b: a>b)
        elif c=='>=':
            return (c, lambda a,b: a>=b)
        elif c=='<=':
            return (c, lambda a,b: a<=b)
        elif c=='<':
            return (c, lambda a,b: a<b)
        raise Exception(f"Unknown comparator {c}")

    def LOGICAL_OPERATOR(self, c):
        if c=='and':
            return (c, lambda a,b: a and b)
        elif c=='or':
            return (c, lambda a,b: a or b)
        raise Exception(f"Unknown logical operator {c}")

    def pair(self, args):
        return (args[0].upper(), args[1].upper())

    @staticmethod
    def normalize_time(time):
        return time.replace(second = 0, microsecond =0)

    def memoize(self, desc, fun):
        def rec_fun(time):
            time = Evaluator.normalize_time(time)
            key = f"{desc}@{time.timestamp()}"
            if key not in self.db:
                return None
            return self.db[key]

        def mem_fun(time):
            time = Evaluator.normalize_time(time)
            key = f"{desc}@{time.timestamp()}"
            if key not in self.db:
                self.db[key] = fun(time, rec_fun)
            return self.db[key]
        return (desc, mem_fun)

    def price(self, args):
        candle, (fsym, tsym) = args
        if candle == 'price':
            candle = 'close'
        return (
            f"{candle}:{fsym}/{tsym}",
            lambda t: self.calculator.price(fsym, tsym, candle, Evaluator.normalize_time(t))
        )

    def change(self, args):
        (desc, fun), interval = args
        return (
            f"change:({desc}):{interval}",
            lambda t: self.calculator.change(fun, interval, t)
        )

    def ema(self, args):
        (desc, fun), window, interval = args
        if not desc:
            raise InvalidIndicatorSource("ema")
        return self.memoize(
            f"ema:({desc}):{window}:{interval}",
            lambda t,rec: self.calculator.smma(fun, window, interval, t, rec, alpha=2.0/(window+1), upwards=None)
        )

    def sma(self, args):
        (desc, fun), window, interval = args
        if not desc:
            raise InvalidIndicatorSource("sma")
        return self.memoize(
            f"sma:({desc}):{window}:{interval}",
            lambda t,_: self.calculator.sma(fun, window, interval, t)
        )

    def smma(self, args, upwards=None):
        (desc, fun), window, interval = args
        if not desc:
            raise InvalidIndicatorSource("smma")
        return self.memoize(
            f"smma:({desc}):{window}:{interval}:{upwards}",
            lambda t,rec: self.calculator.smma(fun, window, interval, t, rec, upwards=upwards, alpha=1.0/window)
        )

    def rsi(self, args):
        child, window, interval = args
        (desc, fun) = child
        if not desc:
            raise InvalidIndicatorSource("rsi")
        def calc(t):
            change = self.change([child, interval])
            _, rs_up = self.smma([change, window, interval], True)
            rs_up = rs_up(t)
            _, rs_down = self.smma([change, window, interval], False)
            rs_down = abs(rs_down(t))
            self.log.debug(f"Computing rsi:({desc}):{window}:{interval}, rs_up={rs_up}, rs_down={rs_down}")
            if rs_down < 1e-9:
                return 100.
            return 100. - 100. / ( 1. + rs_up/rs_down)
        return (
            f"rsi:({desc}):{window}:{interval}",
            calc
        )

    def condition(self, args):
        (p_desc, p), (c_desc, c), (q_desc, q) = args
        return (f"({p_desc}){c_desc}({q_desc})", lambda t: c(p(t), q(t)))

    def math_op(self, args):
        (p_desc, p), (c_desc, c), (q_desc, q) = args
        return (f"({p_desc}){c_desc}({q_desc})", lambda t: c(p(t), q(t)))

    def absolut(self, args):
        (desc, fun) = args[0]
        return (f"abs({desc})", lambda t: abs(fun(t)))

    def if_exp(self, args):
        (c_desc, c), (p_desc, p), (q_desc, q) = args
        return (
            f"if({c_desc})({p_desc})({q_desc})",
            lambda t: p(t) if c(t) else q(t)
        )

    def expression(self, args):
        return lambda t: args[0][1](t)

    def custom(self, args):
        name, cond = args
        return lambda t: cond[1](t)
