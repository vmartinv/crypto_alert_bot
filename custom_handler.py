from lark import Lark, Tree, Transformer
from collections import defaultdict
import logger_config
from repository.market import MarketRepository
from datetime import datetime

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

    def time_dep_value(self, args):
        ind, (fsym, tsym) = args
        if ind=='price':
            return lambda t: self.repository.get_price(fsym, tsym, t)
        # elif c=='or':
        #     return lambda a,b: a or b

    def current(self, args):
        return args[0](datetime.now())

    def condition(self, cond):
        if cond[0] is None or cond[2] is None:
            return False
        return cond[1](cond[0], cond[2])

    def custom(self, args):
        name, cond = args
        return cond

class CustomHandler:
    def __init__(self, db, repository):
        self.db = db
        self.evaluator = Evaluator(repository=repository, visit_tokens=True)
        if 'customs' not in self.db:
            self.db['customs'] = defaultdict(lambda: defaultdict(lambda: []))

    def create(self, chatId, command):
        parsed = CustomHandler.PARSER.parse(command)
        name = CustomHandler.get_name(parsed)
        self.db['customs'][chatId][name] = (command, parsed)
        return f'Alert {name} created! Use /remove {name} to erase it'

    def remove(self, chatId, custom):
        if not custom:
            del self.db['customs'][chatId]
            return 'All alerts removed'
        if custom in self.db['customs'][chatId]:
            del self.db['customs'][chatId][custom]
            if len(self.db['customs'][chatId])==0:
                del self.db['customs'][chatId]
            return 'Alert removed'
        else:
            return 'Alert not found'


    def list(self, chatId):
        if chatId in self.db['customs'] and len(self.db['customs'][chatId])>0:
            msg = 'Current alerts:\n'
            for str,_ in self.db['customs'][chatId].values():
                msg+=f"{str}\n\n"
            return msg
        else:
            return 'No alert is set'

    @staticmethod
    def get_name(custom):
        return custom.children[0]

    def process(self):
        for chatId, customs in self.db['customs'].items():
            for name,(str,parsed) in customs.items():
                if self.evaluator.transform(parsed):
                    self.api.sendMessage(f'The alert {name} was triggered (defined as {str})', chatId)


    PARSER = Lark(r"""
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
        INDICATOR: "price"
            // | "rsi"
        time_dep_value: INDICATOR "(" pair ")"
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
        """, start='custom', parser='lalr')


if __name__ == "__main__":
    log = logger_config.instance
    repository = MarketRepository(log)
    examples = [
        "martin price(btc/usd) > 20",
        "clouds price(btc/usd) > 20%",
        "tree (price(btc/usd) > 20%)",
        # "_no price(btc/usd) > 100 and change(price(btc/usd), 24h) > 10% ",
        "yes change(price(btc/usd), 24h) >10%",
        # "x123 max(change(price(btc/usd), 24h), 24h)>10% and change(price(btc/usd), 10m)>-5%",
        "num (price(btc/usd) > 200)",
    ]
    for example in examples:
        print(example)
        custom = CustomHandler.PARSER.parse(example)
        print(custom)
        print(CustomHandler.get_name(custom))
        print(Evaluator(repository=repository, visit_tokens=True).transform(custom))
        print()
