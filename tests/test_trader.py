import unittest
import uuid

from trader.base_trader import *

logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)


class AuthenticatedClientMock(object):
    # noinspection PyMethodMayBeStatic
    def mock_trade(self, side, price, size, order_type, post_only):
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
                'type': order_type,
                'post_only': post_only,
            }

    # noinspection PyMethodMayBeStatic
    def get_products(self):
        return [
            {
                'status': 'online',
                'id': 'BTC-USD',
                'quote_increment': '0.5',
                'base_currency': 'BTC',
                'quote_currency': 'USD',
                'base_min_size': '0.5',
                'base_max_size': '10000',
            },
            {
                'status': 'online',
                'id': 'ETH-USD',
                'quote_increment': '0.01',
                'base_currency': 'ETC',
                'quote_currency': 'USD',
                'base_min_size': '0.01',
                'base_max_size': '100000',
            },
            {
                'status': 'offline',
                'id': 'ETH-EUR',
                'quote_increment': '0.1',
                'base_currency': 'ETC',
                'quote_currency': 'EUR',
                'base_min_size': '0.01',
                'base_max_size': '100000',
            }
        ]

    # noinspection PyMethodMayBeStatic
    def get_orders(self):
        return [[]]

    def buy(self, **kwargs):
        return self.mock_trade('buy', kwargs['price'], kwargs['size'], kwargs['type'], kwargs.get('post_only', False))

    def sell(self, **kwargs):
        return self.mock_trade('sell', kwargs['price'], kwargs['size'], kwargs['type'], kwargs.get('post_only', False))

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
            },
            {
                'currency': 'ETC',
                'available': "100000.001",
            },
        ]

    # noinspection PyUnusedLocal,PyMethodMayBeStatic
    def get_product_ticker(self, product_id):
        return {
            'price': '100'
        }


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
            },
            {
                'currency': 'USD',
                'available': "0",
            },
            {
                'currency': 'ETC',
                'available': "0",
            },
        ]


class TestTrader(unittest.TestCase):
    def test_increment(self):
        btc_trader = Trader(AuthenticatedClientMock(), 'BTC-USD')
        btc_trader.buy_limit_ptc(50, 100.3)
        expected = {
            'side': 'buy',
            'size': '50',
            'price': '100.5',
            'type': 'limit',
            'post_only': True,
        }
        self.assertIn(expected, [{k: x[k] for k in expected.keys()} for x in btc_trader.orders.values()])
        eth_trader = Trader(AuthenticatedClientMock(), 'ETH-USD')
        eth_trader.buy_limit_ptc(50, 100.03)
        expected = {
            'side': 'buy',
            'size': '50',
            'price': '100.03',
            'type': 'limit',
            'post_only': True,
        }
        self.assertIn(expected, [{k: x[k] for k in expected.keys()} for x in eth_trader.orders.values()])

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
        trader.buy_stop(10, 100)
        self.assertTrue(len(trader.orders) == 5)

    def test_bad_order(self):
        trader = Trader(AuthenticatedClientMock(), 'ETH-USD')
        self.assertRaises(OrderPlacementFailure, trader.buy_limit_ptc, 200, 10)
        self.assertRaises(OrderPlacementFailure, trader.sell_limit_ptc, 200, 10)
        self.assertRaises(OrderPlacementFailure, trader.sell_limit_ptc, 20000, 10)
        self.assertRaises(OrderPlacementFailure, trader.sell_limit_ptc, 0.001, 10)

    def test_insufficient_funds(self):
        trader = Trader(AuthenticatedClientMockWithNoBalance(), 'BTC-USD')
        self.assertRaises(AccountBalanceFailure, trader.buy_limit_ptc, 50, 10)
        self.assertRaises(AccountBalanceFailure, trader.sell_limit_ptc, 50, 10)

    def test_seed_wallet(self):
        trader = Trader(AuthenticatedClientMock(), 'BTC-USD')
        trader.seed_wallet(20)
        expected = [
            {
                'side': 'buy',
                'size': '20',
                'price': '101.0',
                'type': 'stop',
                'post_only': False,
            },
            {
                'side': 'buy',
                'size': '20',
                'price': '99.0',
                'type': 'limit',
                'post_only': True,
            },
        ]
        for order in expected:
            self.assertIn(order, [{k: x[k] for k in order.keys()} for x in trader.orders.values()])

    def test_order_fill(self):
        trader = Trader(AuthenticatedClientMock(), 'BTC-USD')
        trader.orders = {
            'id1': {
                'side': 'buy',
                'size': '20',
                'price': '101.0',
                'type': 'stop',
                'post_only': False,
            },
            'id2': {
                'side': 'buy',
                'size': '20',
                'price': '99.0',
                'type': 'limit',
                'post_only': True,
            },
            'id3': {
                'side': 'sell',
                'size': '10',
                'price': '90.0',
                'type': 'limit',
                'post_only': True,
            },
        }
        trader.available_balance = {
            'USD': 20 * 105,
            'BTC': 10,
        }
        trader.on_order_done({
            'order_id': 'id1',
            'type': 'done',
            'price': '101.5',
            'side': 'buy',
            'reason': 'filled',
            'remaining_size': '5',
        })
        self.assertEqual(trader.orders['id1']['size'], 5)
        self.assertEqual(trader.available_balance['USD'], 577.5)
        self.assertEqual(trader.available_balance['BTC'], 25)
        trader.on_order_done({
            'order_id': 'id2',
            'type': 'done',
            'price': '99',
            'side': 'buy',
            'reason': 'canceled',
            'remaining_size': '0',
        })
        self.assertTrue('id2' not in trader.orders)
        self.assertEqual(trader.available_balance['USD'], 577.5)
        self.assertEqual(trader.available_balance['BTC'], 25)
        trader.on_order_done({
            'order_id': 'id3',
            'type': 'done',
            'price': '90',
            'side': 'sell',
            'reason': 'filled',
            'remaining_size': '0',
        })
        self.assertTrue('id3' not in trader.orders)
        self.assertEqual(trader.available_balance['USD'], 1477.5)
        self.assertEqual(trader.available_balance['BTC'], 15)

    def test_order_fill_failure(self):
        trader = Trader(AuthenticatedClientMock(), 'BTC-USD')
        trader.orders = {
            'id3': {
                'side': 'sell',
                'size': '10',
                'price': '90.0',
                'type': 'limit',
                'post_only': True,
            },
        }
        trader.available_balance = {}
        self.assertRaises(OrderFillFailure, trader.on_order_done, {
            'order_id': 'id1',
            'type': 'done',
            'price': '101.5',
            'side': 'buy',
            'reason': 'filled',
            'remaining_size': '5',
        })
        # Orders should be cleared out, balances goes back to start
        self.assertEquals(trader.orders, {})
        self.assertEquals(trader.available_balance, {
            'BTC': 100000.001,
            'USD': 100000.001,
        })

        # Order id correct but type is wrong
        trader = Trader(AuthenticatedClientMock(), 'BTC-USD')
        trader.orders = {
            'id3': {
                'side': 'sell',
                'size': '10',
                'price': '90.0',
                'type': 'limit',
                'post_only': True,
            },
        }
        trader.available_balance = {}
        self.assertRaises(OrderFillFailure, trader.on_order_done, {
            'order_id': 'id2',
            'price': '101.5',
            'side': 'buy',
            'reason': 'filled',
            'remaining_size': '5',
        })


if __name__ == '__main__':
    unittest.main()
