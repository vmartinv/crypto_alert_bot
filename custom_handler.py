from lark import Lark, Tree, Transformer
from collections import defaultdict
import logger_config
from repository.market import MarketRepository
from datetime import datetime, timedelta
from sqlitedict import SqliteDict
from statistics import mean
import types

class Evaluator(Transformer):

    def __init__(self, repository, *args, **kwargs):
        super(Evaluator, self).__init__(*args, **kwargs)
        self.repository = repository

    INT = int
    CNAME = str
    TWO_DIGITS = int
    WORD = str
    INDICATOR = str
    SIGNED_NUMBER = float

    def number(self, x):
        return float(x[0])

    def minutes(self, x):
        return int(x[0])

    def hours(self, x):
        return int(x[0])*60

    def days(self, x):
        return int(x[0])*60*24

    def percentage(self, x):
        return float(x[0])/100

    def MATH_OPERATOR(self, c):
        if c=='+':
            return lambda a,b: a+b
        elif c=='-':
            return lambda a,b: a-b
        elif c=='*':
            return lambda a,b: a*b
        elif c=='/':
            return lambda a,b: a/b
        raise Exception(f"Unknown MATH_OPERATOR {c}")

    def COMPARATOR(self, c):
        if c=='>':
            return lambda a,b: a>b
        elif c=='>=':
            return lambda a,b: a>=b
        elif c=='<=':
            return lambda a,b: a<=b
        elif c=='<':
            return lambda a,b: a<b
        raise Exception(f"Unknown comparator {c}")

    def LOGICAL_OPERATOR(self, c):
        if c=='and':
            return lambda a,b: a and b
        elif c=='or':
            return lambda a,b: a or b
        raise Exception(f"Unknown logical operator {c}")

    def pair(self, args):
        return (args[0].upper(), args[1].upper())

    def price(self, args):
        fsym, tsym = args[0]
        return lambda t: self.repository.get_values(fsym, tsym, t)['open']

    def ema(self, args):
        (fsym, tsym), window, interval = args
        window = int(window)
        def calc(time):
            time = time.replace(second = 0, microsecond =0)
            # time = time.replace(minute = 0)
            sma_first = time - timedelta(minutes = window*interval*3)
            averages = [self.repository.get_values(fsym, tsym, sma_first + timedelta(minutes = (x+1)*interval - 1))['close'] for x in range(window)]
            sma = mean(averages)
            ema = sma
            weight = 2.0 / (1+window)
            # print(f"calculating ema for window={window} , interval={interval}, pair={fsym}/{tsym}, time={time}")
            ema_first = time - timedelta(minutes = window*interval*2)
            # print(f"SMA {ema}")
            for x in range(window*2):
                cur = ema_first + timedelta(minutes = (x+1)*interval - 1)
                today = self.repository.get_values(fsym, tsym, cur)['close']
                ema = today * weight + ema * (1 - weight)
                # print(f"EMA({x}) {ema} (cur={cur}, today={today})")
            return ema
        return calc

    def current(self, args):
        return args[0](datetime.now())

    def condition(self, cond):
        if cond[0] is None or cond[2] is None:
            return False
        return cond[1](cond[0], cond[2])

    def math_op(self, args):
        return lambda t: args[1](args[0](t), args[2](t))

    def absolut(self, args):
        return lambda t: abs(args[0](t))

    def custom(self, args):
        name, cond = args
        return cond

class CustomHandler:
    def __init__(self, db, repository, api):
        self.db = db
        self.api = api
        if 'chats' not in self.db:
            self.db['chats'] = set()
        self.evaluator = Evaluator(repository=repository, visit_tokens=True)

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
            value = self.evaluator.transform(parsed)
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


    def eval(self, chatId, command):
        command = command.strip()
        try:
            parsed = CustomHandler.VALUE_PARSER.parse(command)
        except Exception as err:
            return f'Error while parsing the expression: {err}'
        try:
            value = self.evaluator.transform(parsed)
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
            del self.db[key]
            self.cleanup_check(chatId)
            return 'All alerts removed'
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
                if ts < datetime.now() and self.evaluator.transform(parsed):
                    self.api.sendMessage(f'The alert {name} was triggered!! (defined as {str})', chatId)
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
        ?time_dep_value: "price" "(" pair ")" -> price
            | "ema" "(" pair "," number "," time_interval ")"         -> ema
            | time_dep_value MATH_OPERATOR time_dep_value -> math_op
            | "abs" "(" time_dep_value ")" -> absolut
            // | "rsi" "(" pair "," time_interval "," number ")"         -> rsi
            // | "change" "(" time_dep_value ("," time_interval)? ")"      -> change
        ?value: percentage
            | number
            | time_dep_value      -> current
            // | "max" "(" time_dep_value "," time_interval ")"         -> max
            // | "min" "(" time_dep_value "," time_interval ")"         -> min
        ?condition: "(" condition ")"
            | condition LOGICAL_OPERATOR condition
            | value COMPARATOR value

        custom: CNAME condition

        %import common.DIGIT
        %import common.CNAME
        %import common.WORD
        %import common.SIGNED_NUMBER
        %import common.WS
        %ignore WS
        """
    CUSTOM_PARSER = Lark(DSL, start='custom', parser='lalr')
    VALUE_PARSER = Lark(DSL, start='value', parser='lalr')


if __name__ == "__main__":
    log = logger_config.instance
    repository = MarketRepository(log)
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
    for example in examples:
        print(example)
        custom = CustomHandler.CUSTOM_PARSER.parse(example)
        print(custom)
        print(Evaluator(repository=repository, visit_tokens=True).transform(custom))
        print()
    examples_eval = [
        "abs(ema(eth/busd, 7, 1h) - ema(eth/busd, 25, 1h))",
    ]
    for example in examples_eval:
        print(example)
        custom = CustomHandler.VALUE_PARSER.parse(example)
        print(custom)
        print(Evaluator(repository=repository, visit_tokens=True).transform(custom))
        print()
