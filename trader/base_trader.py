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
            module_logger.error('Product {} invalid from products {}'.format(
                product_id, json.dumps(products, indent=4, sort_keys=True)))
            raise ProductDefinitionFailure(product_id + ' not active for trading')
        self.base_currency = product[0]['base_currency']
        self.quote_currency = product[0]['quote_currency']
        self.quote_increment = float(product[0]['quote_increment'])
        self.base_min_size = float(product[0]['base_min_size'])
        self.base_max_size = float(product[0]['base_max_size'])

        # Query for current open orders
        orders = self.client.get_orders()[0]
        self.orders = dict(zip([x['id'] for x in orders], orders))
        module_logger.info(
            'Started trader on {} with increment {} and {} open orders'.format(
                product_id, self.quote_increment, len(self.orders)))

    def seed_wallet(self, size):
        """At the start of the day or when the wallet is empty, need something to trade
        Place a stop buy at 1% above current market and a limit post buy at 1% below to minimize fees
        """
        ticker = self.client.get_product_ticker(self.product_id)
        if 'price' not in ticker:
            module_logger.exception('Unable to get current market quote')
            raise OrderPlacementFailure(
                'Unable to get market quote, api message: {}'.format(ticker.get('message', 'unknown error')))
        current_price = float(ticker['price'])
        delta = current_price * 0.01
        module_logger.info(
            'Seeding wallet: {} {} @ {}/{}'.format(size, self.product_id, current_price + delta, current_price - delta))
        self.buy_stop(size, current_price + delta)
        self.buy_limit_ptc(size, current_price - delta)

    # on_fill

    def buy_stop(self, size, price):
        balance = self.get_balance(self.quote_currency)
        if balance < size * price:
            module_logger.exception('Insufficient funds for buy of {}, current balance {}'.format(size, balance))
            raise AccountBalanceFailure('Needed {} have {}'.format(size * price, balance))
        if size < self.base_min_size or size > self.base_max_size:
            raise OrderPlacementFailure('Size of {} outside of exchange limits'.format(size))
        result = self.client.buy(
            type='stop',
            product_id=self.product_id,
            price=self.to_increment(price),
            size=size,
        )
        if 'message' in result:
            module_logger.exception('Error placing buy order, message from api: {}'.format(result['message']))
            raise OrderPlacementFailure(result['message'])
        else:
            self.orders[result['id']] = result
        module_logger.info('Placed buy stop order for {} {} @ {}'.format(size, self.product_id, price))

    def buy_limit_ptc(self, size, price):
        """Post only limit buy with validations"""
        balance = self.get_balance(self.quote_currency)
        if balance < size * price:
            module_logger.exception('Insufficient funds for buy of {}, current balance {}'.format(size, balance))
            raise AccountBalanceFailure('Needed {} have {}'.format(size * price, balance))
        if size < self.base_min_size or size > self.base_max_size:
            raise OrderPlacementFailure('Size of {} outside of exchange limits'.format(size))
        result = self.client.buy(
            type='limit',
            product_id=self.product_id,
            price=self.to_increment(price),
            size=size,
            post_only=True,
        )
        if 'message' in result:
            module_logger.exception('Error placing buy order, message from api: {}'.format(result['message']))
            raise OrderPlacementFailure(result['message'])
        else:
            self.orders[result['id']] = result
        module_logger.info('Placed buy limit order for {} {} @ {}'.format(size, self.product_id, price))

    def sell_limit_ptc(self, size, price):
        """Post only limit sell with validations"""
        balance = self.get_balance(self.base_currency)
        if balance < size:
            module_logger.exception('Insufficient funds for sell of {}, current balance {}'.format(size, balance))
            raise AccountBalanceFailure('Needed {} have {}'.format(size, balance))
        if size < self.base_min_size or size > self.base_max_size:
            raise OrderPlacementFailure('Size of {} outside of exchange limits'.format(size))
        result = self.client.sell(
            type='limit',
            product_id=self.product_id,
            price=self.to_increment(price),
            size=size,
            post_only=True,
        )
        if 'message' in result:
            module_logger.exception('Error placing sell order, message from api: {}'.format(result['message']))
            raise OrderPlacementFailure(result['message'])
        else:
            self.orders[result['id']] = result
        module_logger.info('Placed sell limit order for {} {} @ {}'.format(size, self.product_id, price))

    def get_balance(self, currency):
        accounts = self.client.get_accounts()
        account = [x for x in accounts if x['currency'] == currency]
        if len(account) != 1 or 'available' not in account[0]:
            module_logger.error('Account lookup failure for {} from {}'.format(
                currency, json.dumps(accounts, indent=4, sort_keys=True)))
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

    with open('../config/prod.json') as config:
        data = json.load(config)

    auth_client = AuthenticatedClient(
        data["auth"]["key"],
        data["auth"]["secret"],
        data["auth"]["phrase"],
        api_url=data["endpoints"]["rest"],
    )
    res = auth_client.get_accounts()
    print(json.dumps(res, indent=4, sort_keys=True))
    res = auth_client.get_products()
    print(json.dumps(res, indent=4, sort_keys=True))
    res = auth_client.get_product_ticker('BTC-USD')
    print(json.dumps(res, indent=4, sort_keys=True))
    # res = auth_client.get_product_trades('BTC-USD')
    # print(json.dumps(res, indent=4, sort_keys=True))
