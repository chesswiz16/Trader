import unittest
import uuid

from trader.base_trader import *

logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)


class AuthenticatedClientMock(object):
    # noinspection PyMethodMayBeStatic
    def mock_trade(self, side, price, size):
        """Mock failures if quantity > 100"""
        if size > 100:
            return {
                'message': 'mock failure',
            }
        else:
            return {
                'id': str(uuid.uuid4()),
                'price': str(price),
                'size': str(size),
                'side': side,
            }

    # noinspection PyMethodMayBeStatic
    def get_products(self):
        return [
            {
                'status': 'online',
                'id': 'BTC-USD',
                'quote_increment': 0.5,
                'base_currency': 'BTC',
                'quote_currency': 'USD',
            },
            {
                'status': 'online',
                'id': 'ETH-USD',
                'quote_increment': 0.01,
                'base_currency': 'ETC',
                'quote_currency': 'USD',
            },
            {
                'status': 'offline',
                'id': 'ETH-EUR',
                'quote_increment': 0.1,
                'base_currency': 'ETC',
                'quote_currency': 'EUR',
            }
        ]

    # noinspection PyMethodMayBeStatic
    def get_orders(self):
        return [[]]

    def buy(self, **kwargs):
        return self.mock_trade('buy', kwargs['price'], kwargs['size'])

    def sell(self, **kwargs):
        return self.mock_trade('sell', kwargs['price'], kwargs['size'])

    # noinspection PyMethodMayBeStatic
    def get_accounts(self):
        return [
            {
                'currency': 'BTC',
                'available': "100000.001",
            },
            {
                'currency': 'USD',
                'available': "100000.001",
            }
        ]


class AuthenticatedClientMockWithOrders(AuthenticatedClientMock):
    def get_orders(self):
        return [[
            {
                'id': 'test_id',
                'side': 'buy',
                'size': '100',
                'price': '100',
            }
        ]]


class AuthenticatedClientMockWithNoBalance(AuthenticatedClientMock):
    # noinspection PyMethodMayBeStatic
    def get_accounts(self):
        return [
            {
                'currency': 'BTC',
                'available': "0",
            }
        ]


class TestTrader(unittest.TestCase):
    def test_increment(self):
        btc_trader = Trader(AuthenticatedClientMock(), 'BTC-USD')
        btc_trader.buy_limit_ptc(50, 100.3)
        expected = {
            'side': 'buy',
            'size': '50',
            'price': '100.5',
        }
        self.assertIn(expected, [{'side': x['side'], 'size': x['size'], 'price': x['price']} for x in
                                 btc_trader.orders.values()])
        eth_trader = Trader(AuthenticatedClientMock(), 'ETH-USD')
        eth_trader.buy_limit_ptc(50, 100.03)
        expected = {
            'side': 'buy',
            'size': '50',
            'price': '100.03',
        }
        self.assertIn(expected, [{'side': x['side'], 'size': x['size'], 'price': x['price']} for x in
                                 eth_trader.orders.values()])

    def test_bad_product(self):
        self.assertRaises(ProductDefinitionFailure, Trader, AuthenticatedClientMock(), 'ETH-EUR')

    def test_good_order(self):
        trader = Trader(AuthenticatedClientMockWithOrders(), 'BTC-USD')
        trader.buy_limit_ptc(10, 100)
        self.assertTrue(len(trader.orders) == 2)
        trader.buy_limit_ptc(10, 200)
        self.assertTrue(len(trader.orders) == 3)
        trader.sell_limit_ptc(10, 200)
        self.assertTrue(len(trader.orders) == 4)

    def test_bad_order(self):
        trader = Trader(AuthenticatedClientMock(), 'BTC-USD')
        self.assertRaises(OrderPlacementFailure, trader.buy_limit_ptc, 200, 10)
        self.assertRaises(OrderPlacementFailure, trader.sell_limit_ptc, 200, 10)

    def test_insufficient_funds(self):
        trader = Trader(AuthenticatedClientMockWithNoBalance(), 'BTC-USD')
        self.assertRaises(AccountBalanceFailure, trader.buy_limit_ptc, 50, 10)
        self.assertRaises(AccountBalanceFailure, trader.sell_limit_ptc, 50, 10)


if __name__ == '__main__':
    unittest.main()
