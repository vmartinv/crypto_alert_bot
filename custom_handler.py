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

class CustomHandler:
    def __init__(self, db, calculator, api):
        self.db = db
        self.log = logger_config.get_logger(__name__)
        self.api = api
        if 'chats' not in self.db:
            self.db['chats'] = set()
        self.evaluator = Evaluator(calculator=calculator, visit_tokens=True)

    @staticmethod
    def db_key(chatId):
        return f'{chatId}-customs'

    def create(self, chatId, command):
        command = command.strip()
        try:
            parsed = CustomHandler.CUSTOM_PARSER.parse(command)
        except Exception as err:
            return f'Error while parsing the expression: {err}'
        try:
            value = self.eval_parsed(parsed)
        except Exception as err:
            return f'Error while evaluating the expression: {err}'
        name = CustomHandler.get_name(parsed)
        key = CustomHandler.db_key(chatId)
        if key not in self.db:
            self.db[key] = {}
            tmp = set(self.db['chats'])
            tmp.add(chatId)
            self.db['chats'] = tmp
        tmp = dict(self.db[key])
        tmp[name] = (command, parsed, datetime.now())
        self.db[key] = tmp
        msg = f'Alert {name} created! Use /remove {name} to erase it.'
        if value:
            msg += '\nWARNING: alert already triggering'
        return msg

    def eval_parsed(self, parsed):
        return self.evaluator.transform(parsed)(datetime.now())


    def eval(self, chatId, command):
        command = command.strip()
        try:
            parsed = CustomHandler.EXPRESSION_PARSER.parse(command)
        except Exception as err:
            return f'Error while parsing the expression: {err}'
        try:
            value = self.eval_parsed(parsed)
        except Exception as err:
            return f'Error while evaluating the expression: {err}'
        return f'Result: {value}'

    def cleanup_check(self, chatId):
        key = CustomHandler.db_key(chatId)
        if key in self.db and len(self.db[key])==0:
            del self.db[key]
        if key not in self.db:
            tmp = set(self.db['chats'])
            tmp.discard(chatId)
            self.db['chats'] = tmp

    def remove(self, chatId, custom):
        custom = custom.strip()
        key = CustomHandler.db_key(chatId)
        if not custom:
            if key in self.db:
                del self.db[key]
                self.cleanup_check(chatId)
                return 'All alerts removed'
            else:
                return 'No alerts found'
        if custom in self.db[key]:
            tmp = dict(self.db[key])
            del tmp[custom]
            self.db[key] = tmp
            self.cleanup_check(chatId)
            return 'Alert removed'
        else:
            return 'Alert not found'


    def list(self, chatId):
        key = CustomHandler.db_key(chatId)
        if key in self.db:
            msg = 'Current alerts:\n'
            for name,(cmd,_,_) in self.db[key].items():
                msg+=f"- {cmd}\n\n"
            return msg
        else:
            return 'No alert is set'

    @staticmethod
    def get_name(custom):
        return custom.children[0]

    def process(self):
        for chatId in self.db['chats']:
            key = CustomHandler.db_key(chatId)
            toUpdate = []
            for name,(str,parsed,ts) in self.db[key].items():
                if ts < datetime.now() and self.eval_parsed(parsed):
                    self.api.sendMessage(f'The alert {name} was triggered!! (defined as {str})', chatId)
                    self.log.debug(f"{name} triggered")
                    toUpdate.append(name)
            tmp = dict(self.db[key])
            for name in toUpdate:
                tmp[name] = (tmp[name][0], tmp[name][1], datetime.now() + timedelta(hours = 1))
            self.db[key] = tmp


    DSL = r"""
        ?symbol : WORD
        pair: symbol "/" symbol
        TWO_DIGITS: DIGIT DIGIT?
        time_interval: TWO_DIGITS "h"       -> hours
            | TWO_DIGITS "d"        -> days
            | TWO_DIGITS "m"        -> minutes
        INDICATORS: "price"
            | "change"
            | "rsi"
            | "stoch_rsi"
        COMPARATOR: "<"
                | ">"
                | ">="
                | "<="
        LOGICAL_OPERATOR: "and"
            | "or"
        number: SIGNED_NUMBER
        percentage: SIGNED_NUMBER "%"
        MATH_OPERATOR: "-"
            | "+"
            | "*"
            | "/"
        CANDLE_VALS: "price"
            | "open"
            | "high"
            | "low"
            | "close"
            | "volume"
        ?value: percentage
            | number
            | CANDLE_VALS "(" pair ")" -> price
            | "change" "(" value "," time_interval ")"         -> change
            | "if" "(" condition "," value "," value ")"         -> if_exp
            | "sma" "(" value "," INT "," time_interval ")"         -> sma
            | "smma" "(" value "," INT "," time_interval ")"         -> smma
            | "ema" "(" value "," INT "," time_interval ")"         -> ema
            | value MATH_OPERATOR value -> math_op
            | "abs" "(" value ")" -> absolut
            | "rsi" "(" value "," INT "," time_interval ")"         -> rsi
            // | "change" "(" value ("," time_interval)? ")"      -> change
            // | "max" "(" value "," time_interval ")"         -> max
            // | "min" "(" value "," time_interval ")"         -> min
        ?condition: "(" condition ")"
            | condition LOGICAL_OPERATOR condition
            | value COMPARATOR value

        expression: condition
            | value

        custom: CNAME condition

        %import common.DIGIT
        %import common.INT
        %import common.CNAME
        %import common.WORD
        %import common.SIGNED_NUMBER
        %import common.WS
        %ignore WS
        """
    CUSTOM_PARSER = Lark(DSL, start='custom', parser='lalr')
    EXPRESSION_PARSER = Lark(DSL, start='expression', parser='lalr')


if __name__ == "__main__":
    calculator = Calculator(MarketRepository())
    examples = [
        "martin price(btc/busd) > 20",
        "clouds price(btc/busd) > 20%",
        "tree (price(btc/busd) > 20%)",
        # "_no price(btc/usd) > 100 and change(price(btc/usd), 24h) > 10% ",
        # "yes change(price(btc/usd), 24h) >10%",
        # "x123 max(change(price(btc/usd), 24h), 24h)>10% and change(price(btc/usd), 10m)>-5%",
        "num (price(btc/busd) > 200)",
        "ema_test ema(eth/busd, 7, 1h) > 200",
        "ema_test ema(eth/busd, 25, 1h) > 200",
        # "ema_test ema(eth/busd, 200, 1h) > 200",
        "ema_test abs(ema(eth/busd, 7, 1h) - ema(eth/busd, 25, 1h)) < 0.1",
    ]
    # for example in examples:
    #     print(example)
    #     custom = CustomHandler.CUSTOM_PARSER.parse(example)
    #     print(custom)
    #     print(Evaluator(calculator=calculator, visit_tokens=True).transform(custom))
    #     print()
    examples_eval = [
        "abs(ema(eth/busd, 7, 1h) - ema(eth/busd, 25, 1h))",
        "abs(ema(eth/busd, 7, 1h) - ema(eth/busd, 25, 1h)) > 1",
    ]
    for example in examples_eval:
        print(example)
        custom = CustomHandler.EXPRESSION_PARSER.parse(example)
        print(custom)
        print(Evaluator(calculator=calculator, visit_tokens=True).transform(custom)(datetime.now()))
        print()
