

class InvalidPairException(Exception):
    def __init__(self, fsym, tsym):
        self.message = f"I don't know how to fetch the pair {fsym}/{tsym}, please use only pairs listed on Binance"
        super().__init__(self.message)
