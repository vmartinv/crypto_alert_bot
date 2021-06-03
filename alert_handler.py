import logger_config
from repository.market import MarketRepository
from datetime import datetime, timedelta
from calculator import Calculator
from evaluator import Evaluator
import config

class AlertHandler:
    def __init__(self, db, calculator, bot):
        self.db = db
        self.log = logger_config.get_logger(__name__)
        self.bot = bot
        if 'chats' not in self.db:
            self.db['chats'] = set()
        tot_alerts = sum(len(alerts) for k,alerts in self.db.items() if k.endswith('alerts'))
        self.log.info(f"Loaded handler db with {len(self.db['chats'])} chats registered and {tot_alerts} total alerts")
        self.evaluator = Evaluator(calculator=calculator, visit_tokens=True)

    @staticmethod
    def db_key(chatId):
        return f'{chatId}-alerts'

    def create(self, chatId, command):
        command = command.strip()
        if len(command)>config.MAX_ALERT_LENGTH:
            return f"An alert cannot contain more than {config.MAX_ALERT_LENGTH} characters and this one has {len(command)}."
        try:
            parsed = Evaluator.ALERT_PARSER.parse(command)
        except Exception as err:
            return f'Error while parsing the expression: {err}'
        try:
            value = self.evaluator.eval_now(parsed)
        except Exception as err:
            return f'Error while evaluating the expression: {err}'
        name = AlertHandler.get_name(parsed)
        key = AlertHandler.db_key(chatId)
        if key not in self.db:
            self.db[key] = {}
            tmp = set(self.db['chats'])
            tmp.add(chatId)
            self.db['chats'] = tmp
        tmp = dict(self.db[key])
        tmp[name] = (command, parsed, datetime.now())
        if len(tmp)>config.MAX_ALERTS_PER_USER:
            return f"Maximum alerts per user is {config.MAX_ALERTS_PER_USER}. Please remove some alerts before adding more."
        self.db[key] = tmp
        msg = f'Alert {name} created! Use /remove {name} to erase it.'
        if value:
            msg += '\nWARNING: alert already triggering'
        return msg


    def eval(self, chatId, command):
        command = command.strip()
        try:
            parsed = Evaluator.EXPRESSION_PARSER.parse(command)
        except Exception as err:
            return f'Error while parsing the expression: {err}'
        try:
            value = self.evaluator.eval_now(parsed)
        except Exception as err:
            return f'Error while evaluating the expression: {err}'
        return f'Result: {value}'

    def cleanup_check(self, chatId):
        key = AlertHandler.db_key(chatId)
        if key in self.db and len(self.db[key])==0:
            del self.db[key]
        if key not in self.db:
            tmp = set(self.db['chats'])
            tmp.discard(chatId)
            self.db['chats'] = tmp

    def remove(self, chatId, alert):
        alert = alert.strip()
        key = AlertHandler.db_key(chatId)
        if not alert:
            if key in self.db:
                del self.db[key]
                self.cleanup_check(chatId)
                return 'All alerts removed'
            else:
                return 'No alerts found'
        if alert in self.db[key]:
            tmp = dict(self.db[key])
            del tmp[alert]
            self.db[key] = tmp
            self.cleanup_check(chatId)
            return 'Alert removed'
        else:
            return 'Alert not found'


    def list(self, chatId, _command):
        key = AlertHandler.db_key(chatId)
        if key in self.db:
            msg = 'Current alerts:\n'
            for name,(cmd,_,_) in self.db[key].items():
                msg+=f"- {cmd}\n\n"
            return msg
        else:
            return 'No alert is set'

    @staticmethod
    def get_name(alert):
        return alert.children[0]

    def process(self):
        for chatId in self.db['chats']:
            key = AlertHandler.db_key(chatId)
            toUpdate = []
            for name,(str,parsed,ts) in self.db[key].items():
                if ts < datetime.now() and self.evaluator.eval_now(parsed):
                    self.bot.send_message(
                        text=f'The alert {name} was triggered!! (defined as {str})',
                        chat_id=chatId
                    )
                    self.log.debug(f"{name} triggered")
                    toUpdate.append(name)
            tmp = dict(self.db[key])
            for name in toUpdate:
                tmp[name] = (tmp[name][0], tmp[name][1], datetime.now() + timedelta(hours = 1))
            self.db[key] = tmp


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
    #     alert = Evaluator.ALERT_PARSER.parse(example)
    #     print(alert)
    #     print(Evaluator(calculator=calculator, visit_tokens=True).eval_now(alert))
    #     print()
    examples_eval = [
        "abs(ema(eth/busd, 7, 1h) - ema(eth/busd, 25, 1h))",
        "abs(ema(eth/busd, 7, 1h) - ema(eth/busd, 25, 1h)) > 1",
    ]
    for example in examples_eval:
        print(example)
        alert = Evaluator.EXPRESSION_PARSER.parse(example)
        print(alert)
        print(Evaluator(calculator=calculator, visit_tokens=True).transform(alert)(datetime.now()))
        print()
