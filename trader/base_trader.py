import logging
import json

module_logger = logging.getLogger(__name__)


class Trader(object):
    def __init__(self, client, product_id):
        self.client = client
        self.product_id = product_id

        # Query for product and find status/increment
        products = self.client.get_products()
        product = [x for x in products if x['status'] == 'online' and x['id'] == product_id]
        if len(product) != 1:
            module_logger.error('Product {} invalid from products {}'.format(product_id, json.dumps(products, indent=4,
                                                                                                    sort_keys=True)))
            raise ProductDefinitionFailure(product_id + ' not active for trading')
        self.quote_increment = product[0]['quote_increment']
        self.base_currency = product[0]['base_currency']
        self.quote_currency = product[0]['quote_currency']

        # Query for current open orders
        orders = self.client.get_orders()[0]
        self.orders = dict(zip([x['id'] for x in orders], orders))
        module_logger.info(
            'Started trader on {} with increment {} and {} open orders'.format(product_id, self.quote_increment,
                                                                               len(self.orders)))

    # on_start
    # on_fill

    def buy_limit_ptc(self, size, price):
        """Post only limit buy"""
        balance = self.get_balance(self.quote_currency)
        if balance < size * price:
            module_logger.exception('Insufficient funds for buy of {}, current balance {}'.format(size, balance))
            raise AccountBalanceFailure('Needed {} have {}'.format(size * price, balance))
        result = self.client.buy(type='limit',
                                 product_id=self.product_id,
                                 price=self.to_increment(price),
                                 size=size,
                                 post_only=True)
        if 'message' in result:
            module_logger.exception('Error placing buy order, message from api: {}'.format(result['message']))
            raise OrderPlacementFailure(result['message'])
        else:
            self.orders[result['id']] = result
        module_logger.info('Placed buy order for {} {} @ {}'.format(size, self.product_id, price))

    def sell_limit_ptc(self, size, price):
        """Post only limit sell"""
        balance = self.get_balance(self.base_currency)
        if balance < size:
            module_logger.exception('Insufficient funds for sell of {}, current balance {}'.format(size, balance))
            raise AccountBalanceFailure('Needed {} have {}'.format(size, balance))
        result = self.client.sell(type='limit',
                                  product_id=self.product_id,
                                  price=self.to_increment(price),
                                  size=size,
                                  post_only=True)
        if 'message' in result:
            module_logger.exception('Error placing sell order, message from api: {}'.format(result['message']))
            raise OrderPlacementFailure(result['message'])
        else:
            self.orders[result['id']] = result
        module_logger.info('Placed sell order for {} {} @ {}'.format(size, self.product_id, price))

    def get_balance(self, currency):
        accounts = self.client.get_accounts()
        account = [x for x in accounts if x['currency'] == currency]
        if len(account) != 1 or 'available' not in account[0]:
            module_logger.error('Account lookup failure for {} from {}'.format(currency, json.dumps(accounts, indent=4,
                                                                                                    sort_keys=True)))
            raise AccountBalanceFailure(currency + ' not found in active accounts')
        return float(account[0]['available'])

    def to_increment(self, price):
        diff = price - round(price)
        increments = round(diff / self.quote_increment)
        return round(price) + (increments * self.quote_increment)


class AccountBalanceFailure(Exception):
    def __init__(self, value):
        self.parameter = value

    def __str__(self):
        return repr(self.parameter)


class OrderPlacementFailure(Exception):
    def __init__(self, value):
        self.parameter = value

    def __str__(self):
        return repr(self.parameter)


class ProductDefinitionFailure(Exception):
    def __init__(self, value):
        self.parameter = value

    def __str__(self):
        return repr(self.parameter)


if __name__ == '__main__':
    from gdax.authenticated_client import AuthenticatedClient

    with open('../config/sandbox.json') as config:
        data = json.load(config)

    auth_client = AuthenticatedClient(data["auth"]["key"],
                                      data["auth"]["secret"],
                                      data["auth"]["phrase"],
                                      api_url=data["endpoints"]["rest"])
    t = Trader(auth_client, 'BTC-USD')
    # t.buy_limit_ptc(1, 100.001)
    res = auth_client.get_accounts()
    print(json.dumps(res, indent=4, sort_keys=True))
    res = auth_client.get_products()
    print(json.dumps(res, indent=4, sort_keys=True))
