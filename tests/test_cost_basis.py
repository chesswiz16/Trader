import logging
import unittest
from unittest.mock import Mock, MagicMock

from tests.authenticated_client_regression import AuthenticatedClientRegression
from trader.cost_basis import CostBasisTrader

logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)


class TestCostBasis(unittest.TestCase):
    def test_on_order_done(self):
        auth_client_mock = AuthenticatedClientRegression('ETH-USD', [100, 100, 100, 100], starting_balance=10000)
        auth_client_mock.cancel_all = Mock()
        auth_client_mock.get_product_ticker = MagicMock(return_value={
            'price': '100',
        })
        trader = CostBasisTrader('ETH-USD', 3, 0.1, auth_client=auth_client_mock)
        trader.on_start()
        # Get limit order and mock it's been filled
        limit_order = [x for x in auth_client_mock.orders if x['type'] == 'limit'][0]
        self.assertEqual(len(auth_client_mock.orders), 2)
        trader.on_order_done({
            'order_id': limit_order['id'],
            'reason': 'filled',
            'product_id': 'ETH-USD',
        })
        self.assertEqual(trader.current_order_depth, 1)
        self.assertEqual(trader.quote_currency_paid, 10 * 99.0)
        self.assertEqual(trader.base_currency_bought, 10)
        self.assertEqual(len(auth_client_mock.orders), 2)
        expected = {
            'side': 'sell',
            'size': '10.0',
            'price': '99.99',
            'type': 'limit',
            'post_only': True,
        }
        self.assertIn(expected, [{k: x[k] for k in expected.keys()} for x in auth_client_mock.orders])
        expected = {
            'side': 'buy',
            'size': '10.30405061',
            'price': '97.05',
            'type': 'limit',
            'post_only': True,
        }
        self.assertIn(expected, [{k: x[k] for k in expected.keys()} for x in auth_client_mock.orders])

        # Get the buy order and mock that it's filled
        buy_order = [x for x in auth_client_mock.orders if x['side'] == 'buy'][0]
        trader.on_order_done({
            'order_id': buy_order['id'],
            'reason': 'filled',
            'product_id': 'ETH-USD',
        })
        self.assertEqual(trader.current_order_depth, 2)
        self.assertEqual(trader.quote_currency_paid, 1990.0081117005002)
        self.assertEqual(trader.base_currency_bought, 20.30405061)
        self.assertEqual(len(auth_client_mock.orders), 2)
        expected = {
            'side': 'sell',
            'size': '20.30405061',
            'price': '98.99',
            'type': 'limit',
            'post_only': True,
        }
        self.assertIn(expected, [{k: x[k] for k in expected.keys()} for x in auth_client_mock.orders])
        expected = {
            'side': 'buy',
            'size': '10.51115093',
            'price': '95.14',
            'type': 'limit',
            'post_only': True,
        }
        self.assertIn(expected, [{k: x[k] for k in expected.keys()} for x in auth_client_mock.orders])

        # 3 deep now
        buy_order = [x for x in auth_client_mock.orders if x['side'] == 'buy'][0]
        trader.on_order_done({
            'order_id': buy_order['id'],
            'reason': 'filled',
            'product_id': 'ETH-USD',
        })
        self.assertEqual(trader.current_order_depth, 3)
        self.assertEqual(trader.quote_currency_paid, 2990.0390111807)
        self.assertEqual(trader.base_currency_bought, 30.81520154)
        self.assertEqual(len(auth_client_mock.orders), 2)
        expected = {
            'side': 'sell',
            'size': '30.81520154',
            'price': '98.0',
            'type': 'limit',
            'post_only': True,
        }
        self.assertIn(expected, [{k: x[k] for k in expected.keys()} for x in auth_client_mock.orders])
        expected = {
            'side': 'buy',
            'size': '10.72131821',
            'price': '93.27',
            'type': 'limit',
            'post_only': True,
        }
        self.assertIn(expected, [{k: x[k] for k in expected.keys()} for x in auth_client_mock.orders])

        # 4 deep, sell should go out but no buy
        buy_order = [x for x in auth_client_mock.orders if x['side'] == 'buy'][0]
        trader.on_order_done({
            'order_id': buy_order['id'],
            'reason': 'filled',
            'product_id': 'ETH-USD',
        })
        self.assertEqual(trader.current_order_depth, 4)
        self.assertEqual(trader.quote_currency_paid, 3990.0163606274)
        self.assertEqual(trader.base_currency_bought, 41.53651975)
        self.assertEqual(len(auth_client_mock.orders), 1)
        expected = {
            'side': 'sell',
            'size': '41.53651975',
            'price': '97.02',
            'type': 'limit',
            'post_only': True,
        }
        self.assertIn(expected, [{k: x[k] for k in expected.keys()} for x in auth_client_mock.orders])

        # Sell comes in, should reset the cost basis to market
        sell_order = [x for x in auth_client_mock.orders if x['side'] == 'sell'][0]
        trader.place_next_orders({
            'maker_order_id': sell_order['id'],
            'taker_order_id': '',
            'type': 'match',
            'price': sell_order['price'],
            'side': 'sell',
            'size': sell_order['size'],
        })
        self.assertTrue(sell_order['id'] not in auth_client_mock.orders)
        self.assertEqual(trader.current_order_depth, 0)
        self.assertEqual(trader.quote_currency_paid, 0.0)
        self.assertEqual(trader.base_currency_bought, 0.0)
        self.assertEqual(len(auth_client_mock.orders), 2)
        expected = {
            'side': 'buy',
            'size': '10.0',
            'price': '101.0',
            'type': 'stop',
            'post_only': False,
        }
        self.assertIn(expected, [{k: x[k] for k in expected.keys()} for x in auth_client_mock.orders])
        expected = {
            'side': 'buy',
            'size': '10.0',
            'price': '99.0',
            'type': 'limit',
            'post_only': True,
        }
        self.assertIn(expected, [{k: x[k] for k in expected.keys()} for x in auth_client_mock.orders])
        wallet_value = trader.get_balance('USD')
        for order in auth_client_mock.orders:
            wallet_value += float(order['size']) * float(order['price'])
        # Make sure we actually made money...
        self.assertGreater(wallet_value, 10000)

    def test_recovery(self):
        auth_client_mock = AuthenticatedClientRegression('ETH-USD', [100, 100, 100, 100])
        auth_client_mock.get_accounts = MagicMock(return_value=[
            {
                'currency': 'ETH',
                'available': '0',
                'id': '1',
            },
            {
                'currency': 'USD',
                'available': '10000',
                'id': '2',
            },
        ])
        auth_client_mock.cancel_order = MagicMock(return_value={})
        auth_client_mock.cancel_all = Mock()
        auth_client_mock.get_product_ticker = MagicMock(return_value={
            'price': '100',
        })
        trader = CostBasisTrader('ETH-USD', 3, 0.1, auth_client=auth_client_mock)
        trader.on_start()
        self.assertTrue(len(auth_client_mock.orders), 2)
        self.assertEqual(trader.base_currency_bought, 0.0)
        self.assertEqual(trader.quote_currency_paid, 0.0)
        self.assertEqual(trader.current_order_depth, 0)

        # Has seeding orders, assert orders are the same
        trader = CostBasisTrader('ETH-USD', 3, 0.1, auth_client=auth_client_mock)
        orders = [
            {
                'id': 'id1',
                'side': 'buy',
                'size': '20',
                'price': '101.0',
                'type': 'stop',
                'product_id': 'ETH-USD',
                'post_only': False,
            },
            {
                'id': 'id1',
                'side': 'buy',
                'size': '20',
                'price': '99.0',
                'type': 'limit',
                'product_id': 'ETH-USD',
                'post_only': True,
            },
        ]
        auth_client_mock.orders = orders
        trader.on_start()
        self.assertTrue(len(auth_client_mock.orders), 2)
        self.assertEqual(trader.base_currency_bought, 0.0)
        self.assertEqual(trader.quote_currency_paid, 0.0)
        self.assertEqual(trader.current_order_depth, 0)
        self.assertEqual(auth_client_mock.orders, orders)

        # Has limit buy and sell, pick up where we were
        trader = CostBasisTrader('ETH-USD', 3, 0.1, auth_client=auth_client_mock)
        orders = [
            {
                'id': 'id1',
                'side': 'sell',
                'size': '20',
                'price': '101.0',
                'type': 'limit',
                'product_id': 'ETH-USD',
                'post_only': True,
            },
            {
                'id': 'id1',
                'side': 'buy',
                'size': '20',
                'price': '99.0',
                'type': 'limit',
                'product_id': 'ETH-USD',
                'post_only': True,
            },
        ]
        auth_client_mock.orders = orders
        trader.on_start()
        self.assertTrue(len(auth_client_mock.orders), 2)
        self.assertEqual(trader.base_currency_bought, 20)
        self.assertEqual(trader.quote_currency_paid, 20 * 100)
        self.assertEqual(trader.current_order_depth, 2)
        self.assertEqual(auth_client_mock.orders, orders)

        # Has limit sell, pick up where we were
        trader = CostBasisTrader('ETH-USD', 3, 0.1, auth_client=auth_client_mock)
        orders = [
            {
                'id': 'id1',
                'side': 'sell',
                'size': '20',
                'price': '101.0',
                'type': 'limit',
                'product_id': 'ETH-USD',
                'post_only': True,
            },
        ]
        auth_client_mock.orders = orders
        trader.on_start()
        self.assertTrue(len(auth_client_mock.orders), 2)
        self.assertEqual(trader.base_currency_bought, 20)
        self.assertEqual(trader.quote_currency_paid, 20 * 100)
        self.assertEqual(trader.current_order_depth, 2)
        self.assertEqual(auth_client_mock.orders, orders)

        # Only has buy, reset
        trader = CostBasisTrader('ETH-USD', 3, 0.1, auth_client=auth_client_mock)
        orders = [
            {
                'id': 'id1',
                'side': 'buy',
                'size': '20',
                'price': '99.0',
                'type': 'limit',
                'product_id': 'ETH-USD',
                'post_only': True,
            },
        ]
        auth_client_mock.orders = orders
        trader.on_start()
        self.assertTrue(len(auth_client_mock.orders), 2)
        self.assertEqual(trader.base_currency_bought, 0.0)
        self.assertEqual(trader.quote_currency_paid, 0.0)
        self.assertEqual(trader.current_order_depth, 0)

        # Weird order state, resets status
        trader = CostBasisTrader('ETH-USD', 3, 0.1, auth_client=auth_client_mock)
        orders = [
            {
                'id': 'id1',
                'side': 'sell',
                'size': '20',
                'price': '101.0',
                'type': 'limit',
                'product_id': 'ETH-USD',
                'post_only': True,
            },
            {
                'id': 'id1',
                'side': 'buy',
                'size': '20',
                'price': '99.0',
                'type': 'limit',
                'product_id': 'ETH-USD',
                'post_only': True,
            },
            {
                'id': 'id1',
                'side': 'buy',
                'size': '20',
                'price': '99.0',
                'type': 'limit',
                'product_id': 'ETH-USD',
                'post_only': True,
            },
        ]
        auth_client_mock.orders = orders
        self.assertTrue(len(auth_client_mock.orders), 2)
        self.assertEqual(trader.base_currency_bought, 0.0)
        self.assertEqual(trader.quote_currency_paid, 0.0)
        self.assertEqual(trader.current_order_depth, 0)
