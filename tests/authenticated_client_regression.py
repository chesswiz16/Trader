import uuid


# noinspection PyMethodMayBeStatic
class AuthenticatedClientRegression(object):
    def __init__(self, product_id, last_rates, starting_balance=1000):
        self.orders = []
        self.starting_balance = [
            {
                'currency': 'USD',
                'available': str(starting_balance),
                'balance': str(starting_balance),
                'id': 1,
            },
            {
                'currency': 'ETH',
                'available': '0',
                'balance': '0',
                'id': 2,
            },
            {
                'currency': 'BTC',
                'available': '0',
                'balance': '0',
                'id': 3,
            },
            {
                'currency': 'BTH',
                'available': '0',
                'balance': '0',
                'id': 4,
            },
            {
                'currency': 'LTC',
                'available': '0',
                'balance': '0',
                'id': 5,
            },
        ]
        self.product_id = product_id
        self.last_rates = last_rates

    def get_order(self, order_id):
        order = [x for x in self.orders if x['id'] == order_id][0]
        order['settled'] = True
        order['filled_size'] = order['size']
        return order

    def get_product_ticker(self, product_id):
        if self.product_id == product_id:
            return {
                'price': (self.last_rates[1] + self.last_rates[2]) / 2,
            }

    def get_accounts(self):
        return self.starting_balance

    def mock_trade(self, side, price, size, order_type, post_only):
        order = {
            'id': str(uuid.uuid4()),
            'price': str(price),
            'size': str(size),
            'side': side,
            'type': order_type,
            'product_id': self.product_id,
            'post_only': post_only,
        }
        self.orders.append(order)
        return order

    def get_products(self):
        return [
            {
                'base_currency': 'BCH',
                'base_max_size': '250',
                'base_min_size': '0.0001',
                'display_name': 'BCH/USD',
                'id': 'BCH-USD',
                'limit_only': False,
                'margin_enabled': False,
                'max_market_funds': '1000000',
                'min_market_funds': '1',
                'post_only': False,
                'quote_currency': 'USD',
                'quote_increment': '0.01',
                'status': 'online',
                'status_message': None,
            },
            {
                'base_currency': 'LTC',
                'base_max_size': '1000000',
                'base_min_size': '0.01',
                'display_name': 'LTC/EUR',
                'id': 'LTC-EUR',
                'limit_only': False,
                'margin_enabled': False,
                'max_market_funds': None,
                'min_market_funds': '1',
                'post_only': False,
                'quote_currency': 'EUR',
                'quote_increment': '0.01',
                'status': 'online',
                'status_message': None,
            },
            {
                'base_currency': 'LTC',
                'base_max_size': '1000000',
                'base_min_size': '0.01',
                'display_name': 'LTC/USD',
                'id': 'LTC-USD',
                'limit_only': False,
                'margin_enabled': False,
                'max_market_funds': '1000000',
                'min_market_funds': '1',
                'post_only': False,
                'quote_currency': 'USD',
                'quote_increment': '0.01',
                'status': 'online',
                'status_message': None,
            },
            {
                'base_currency': 'LTC',
                'base_max_size': '1000000',
                'base_min_size': '0.01',
                'display_name': 'LTC/BTC',
                'id': 'LTC-BTC',
                'limit_only': False,
                'margin_enabled': False,
                'max_market_funds': None,
                'min_market_funds': '0.0001',
                'post_only': False,
                'quote_currency': 'BTC',
                'quote_increment': '0.00001',
                'status': 'online',
                'status_message': None,
            },
            {
                'base_currency': 'ETH',
                'base_max_size': '5000',
                'base_min_size': '0.001',
                'display_name': 'ETH/EUR',
                'id': 'ETH-EUR',
                'limit_only': False,
                'margin_enabled': False,
                'max_market_funds': None,
                'min_market_funds': '1',
                'post_only': False,
                'quote_currency': 'EUR',
                'quote_increment': '0.01',
                'status': 'online',
                'status_message': None,
            },
            {
                'base_currency': 'ETH',
                'base_max_size': '5000',
                'base_min_size': '0.001',
                'display_name': 'ETH/USD',
                'id': 'ETH-USD',
                'limit_only': False,
                'margin_enabled': False,
                'max_market_funds': '1000000',
                'min_market_funds': '1',
                'post_only': False,
                'quote_currency': 'USD',
                'quote_increment': '0.01',
                'status': 'online',
                'status_message': None,
            },
            {
                'base_currency': 'ETH',
                'base_max_size': '5000',
                'base_min_size': '0.001',
                'display_name': 'ETH/BTC',
                'id': 'ETH-BTC',
                'limit_only': False,
                'margin_enabled': False,
                'max_market_funds': None,
                'min_market_funds': '0.0001',
                'post_only': False,
                'quote_currency': 'BTC',
                'quote_increment': '0.00001',
                'status': 'online',
                'status_message': None,
            },
            {
                'base_currency': 'BTC',
                'base_max_size': '250',
                'base_min_size': '0.0001',
                'display_name': 'BTC/GBP',
                'id': 'BTC-GBP',
                'limit_only': False,
                'margin_enabled': False,
                'max_market_funds': None,
                'min_market_funds': '1',
                'post_only': False,
                'quote_currency': 'GBP',
                'quote_increment': '0.01',
                'status': 'online',
                'status_message': None,
            },
            {
                'base_currency': 'BTC',
                'base_max_size': '250',
                'base_min_size': '0.0001',
                'display_name': 'BTC/EUR',
                'id': 'BTC-EUR',
                'limit_only': False,
                'margin_enabled': False,
                'max_market_funds': None,
                'min_market_funds': '1',
                'post_only': False,
                'quote_currency': 'EUR',
                'quote_increment': '0.01',
                'status': 'online',
                'status_message': None,
            },
            {
                'base_currency': 'BTC',
                'base_max_size': '250',
                'base_min_size': '0.0001',
                'display_name': 'BTC/USD',
                'id': 'BTC-USD',
                'limit_only': False,
                'margin_enabled': False,
                'max_market_funds': '1000000',
                'min_market_funds': '1',
                'post_only': False,
                'quote_currency': 'USD',
                'quote_increment': '0.01',
                'status': 'online',
                'status_message': None,
            }
        ]

    def get_orders(self):
        return [self.orders]

    def buy(self, **kwargs):
        return self.mock_trade('buy', kwargs['price'], kwargs['size'], kwargs['type'], kwargs.get('post_only', False))

    def sell(self, **kwargs):
        return self.mock_trade('sell', kwargs['price'], kwargs['size'], kwargs['type'], kwargs.get('post_only', False))

    def cancel_order(self, order_id):
        self.orders = [x for x in self.orders if x['id'] != order_id]
        return {
            'id': order_id,
        }

    def cancel_all(self):
        self.orders = []
        return {}

    def on_tick(self, low, high):
        """Give a market data slice, return the order (if any) that needs to be filled.
        Precedence given to buy orders in case the candle is really wide.
        """
        buy_orders = [x for x in self.orders if x['side'] == 'buy']
        sell_orders = [x for x in self.orders if x['side'] == 'sell']
        for buy_order in buy_orders:
            if (buy_order['type'] == 'stop' and float(high) >= float(buy_order['price'])) or float(low) <= float(
                    buy_order['price']):
                return buy_order
        for sell_order in sell_orders:
            if float(high) >= float(sell_order['price']):
                return sell_order
        return None
