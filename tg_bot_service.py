import time
import logger_config
import config
from repository.market import MarketRepository
from command_handler import CommandHandler
from alert_handler import AlertHandler
from sqlitedict import SqliteDict
from calculator import Calculator
from telegram.ext import Updater

class TgBotService:

    def __init__(self):
        self.log = logger_config.get_logger(__name__)
        self.db = SqliteDict(config.DB_FILENAME)
        calculator = Calculator(MarketRepository())
        self.updater = Updater(token=config.TG_TOKEN, use_context=True)
        self.alert_handler = AlertHandler(self.db, calculator, self.updater.bot)
        command_handler = CommandHandler(self.alert_handler)
        command_handler.add_handlers(self.updater.dispatcher)


    def run(self):
        self.last_time = 0
        self.updater.start_polling()
        self.alert_loop()
        self.updater.stop()

    def process_alerts(self):
        start = time.time()
        if start-self.last_time>=10*60:
            self.log.info("Start checking alerts")
        self.alert_handler.process()
        end = time.time()
        if start-self.last_time>=10*60:
            self.last_time = end
            self.log.info(f"Checking alerts took {(end-start)} seconds")

    def alert_loop(self):
        loop = True
        while loop:
            try:
                self.process_alerts()
                time.sleep(1)
            except KeyboardInterrupt:
                self.log.info("interrupt received, stopping...")
                loop = False
            except Exception as err:
                self.log.exception(f"Exception at processing alerts {err}")
                loop = False

            self.db.commit()

if __name__ == "__main__":
    service = TgBotService()
    service.run()
