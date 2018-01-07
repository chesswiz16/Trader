__author__ = 'Tiger'


class Trader(object):
    def __init__(self, client, product_id, quote_increment):
        self.client = client
        self.product_id = product_id
        self.quote_increment = quote_increment
        self.orders = dict()

    def buy_limit_ptc(self, size, price):
        """Post only limit buy"""
        result = self.client.buy(type="limit",
                                 product_id=self.product_id,
                                 price=self.to_increment(price),
                                 size=size,
                                 post_only=True)
        if "message" in result:
            raise OrderPlacementFailure(result["message"])
        else:
            self.orders[result["id"]] = result

    def sell_limit_ptc(self, size, price):
        """Post only limit sell"""
        result = self.client.sell(type="limit",
                                  product_id=self.product_id,
                                  price=self.to_increment(price),
                                  size=size,
                                  post_only=True)
        if "message" in result:
            raise OrderPlacementFailure(result["message"])
        else:
            self.orders[result["id"]] = result

    def to_increment(self, price):
        return price


class OrderPlacementFailure(Exception):
    def __init__(self, value):
        self.parameter = value

    def __str__(self):
        return repr(self.parameter)
