import unittest
from unittest.mock import MagicMock
from unittest.mock import Mock

from tests.authenticated_client_mock import AuthenticatedClientMock
from trader.base_trader import *

logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)


class TestTrader(unittest.TestCase):
    def test_increment(self):
        btc_trader = Trader('BTC-USD', auth_client=AuthenticatedClientMock())
        btc_trader.buy_limit_ptc(50, 100.3)
        expected = {
            'side': 'buy',
            'size': '50',
            'price': '100.5',
            'type': 'limit',
            'post_only': True,
        }
        self.assertIn(expected, [{k: x[k] for k in expected.keys()} for x in btc_trader.orders.values()])
        eth_trader = Trader('ETH-USD', auth_client=AuthenticatedClientMock())
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
        self.assertRaises(ProductDefinitionFailure, Trader, 'ETH-EUR', auth_client=AuthenticatedClientMock())

    def test_good_order(self):
        client_with_orders = AuthenticatedClientMock()
        client_with_orders.get_orders = MagicMock(return_value=[[
            {
                'id': 'test_id',
                'side': 'buy',
                'size': '100',
                'price': '100',
            }
        ]])
        trader = Trader('BTC-USD', auth_client=client_with_orders)
        trader.buy_limit_ptc(10, 100)
        self.assertTrue(len(trader.orders) == 2)
        self.assertTrue(trader.available_balance['USD'] == 99000.001)
        trader.buy_limit_ptc(10, 200)
        self.assertTrue(len(trader.orders) == 3)
        self.assertTrue(trader.available_balance['USD'] == 97000.001)
        trader.sell_limit_ptc(10, 200)
        self.assertTrue(len(trader.orders) == 4)
        self.assertTrue(trader.available_balance['USD'] == 97000.001)
        self.assertTrue(trader.available_balance['BTC'] == 99990.001)
        trader.buy_stop(10, 100)
        self.assertTrue(len(trader.orders) == 5)
        self.assertTrue(trader.available_balance['USD'] == 96000.001)

    def test_bad_order(self):
        trader = Trader('ETH-USD', auth_client=AuthenticatedClientMock())
        self.assertRaises(OrderPlacementFailure, trader.buy_limit_ptc, 200, 10)
        self.assertRaises(OrderPlacementFailure, trader.sell_limit_ptc, 200, 10)
        self.assertRaises(OrderPlacementFailure, trader.sell_limit_ptc, 20000, 10)
        self.assertRaises(OrderPlacementFailure, trader.sell_limit_ptc, 0.001, 10)

    def test_decaying_order(self):
        client_with_order_failure = AuthenticatedClientMock()
        # Two failures then a success
        client_with_order_failure.buy = Mock(side_effect=[
            {
                'message': 'test1',
            },
            {
                'message': 'test2',
            },
            {
                'id': 'id1',
            },
        ])
        trader = Trader('BTC-USD', auth_client=client_with_order_failure)
        trader.buy_limit_ptc(10, 100)
        self.assertTrue(len(trader.orders) == 1)
        self.assertTrue(trader.available_balance['USD'] == 99010.001)
        self.assertTrue(trader.available_balance['BTC'] == 100000.001)
        client_with_order_failure.buy.assert_any_call(
            type='limit',
            product_id='BTC-USD',
            price=100.0,
            size=10,
            post_only=True,
        )
        client_with_order_failure.buy.assert_any_call(
            type='limit',
            product_id='BTC-USD',
            price=99.5,
            size=10,
            post_only=True,
        )
        client_with_order_failure.buy.assert_any_call(
            type='limit',
            product_id='BTC-USD',
            price=99.0,
            size=10,
            post_only=True,
        )

    def test_insufficient_funds(self):
        client_no_balance = AuthenticatedClientMock()
        client_no_balance.get_accounts = MagicMock(return_value=[
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
        ])
        trader = Trader('BTC-USD', auth_client=client_no_balance)
        self.assertRaises(AccountBalanceFailure, trader.buy_limit_ptc, 50, 10)
        self.assertRaises(AccountBalanceFailure, trader.sell_limit_ptc, 50, 10)

    def test_seed_wallet(self):
        trader = Trader('BTC-USD', auth_client=AuthenticatedClientMock())
        trader.seed_wallet(2000)
        expected = [
            {
                'side': 'buy',
                'size': '20.0',
                'price': '101.0',
                'type': 'stop',
                'post_only': False,
            },
            {
                'side': 'buy',
                'size': '20.0',
                'price': '99.0',
                'type': 'limit',
                'post_only': True,
            },
        ]
        for order in expected:
            self.assertIn(order, [{k: x[k] for k in order.keys()} for x in trader.orders.values()])

    def test_order_fill(self):
        trader = Trader('BTC-USD', auth_client=AuthenticatedClientMock())
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
        trader.on_order_fill({
            'order_id': 'id1',
            'type': 'done',
            'price': '101.5',
            'side': 'buy',
            'reason': 'filled',
            'remaining_size': '5',
        })
        self.assertEqual(trader.orders['id1']['size'], '20')
        self.assertEqual(trader.orders['id1']['remaining_size'], 5)
        self.assertEqual(trader.available_balance['USD'], 20 * 105)
        self.assertEqual(trader.available_balance['BTC'], 25)
        trader.on_order_fill({
            'order_id': 'id2',
            'type': 'done',
            'price': '99',
            'side': 'buy',
            'reason': 'canceled',
            'remaining_size': '0',
        })
        self.assertTrue('id2' not in trader.orders)
        self.assertEqual(trader.available_balance['USD'], 20 * 105)
        self.assertEqual(trader.available_balance['BTC'], 25)
        trader.on_order_fill({
            'order_id': 'id3',
            'type': 'done',
            'price': '90',
            'side': 'sell',
            'reason': 'filled',
            'remaining_size': '0',
        })
        self.assertTrue('id3' not in trader.orders)
        self.assertEqual(trader.available_balance['USD'], 20 * 105 + 90 * 10)
        self.assertEqual(trader.available_balance['BTC'], 25)

    def test_order_fill_failure(self):
        trader = Trader('BTC-USD', auth_client=AuthenticatedClientMock())
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
        self.assertRaises(OrderFillFailure, trader.on_order_fill, {
            'order_id': 'id1',
            'type': 'done',
            'price': '101.5',
            'side': 'buy',
            'reason': 'filled',
            'remaining_size': '5',
        })
        # Orders should be cleared out, balances goes back to start
        self.assertEqual(trader.orders, {})
        self.assertEqual(trader.available_balance, {
            'BTC': 100000.001,
            'USD': 100000.001,
        })

        # Order id correct but type is wrong
        trader = Trader('BTC-USD', auth_client=AuthenticatedClientMock())
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
        self.assertRaises(OrderFillFailure, trader.on_order_fill, {
            'order_id': 'id2',
            'price': '101.5',
            'side': 'buy',
            'reason': 'filled',
            'remaining_size': '5',
        })


if __name__ == '__main__':
    unittest.main()
