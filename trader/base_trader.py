import base64
import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timedelta

from ws4py.client.threadedclient import WebSocketClient

from gdax.authenticated_client import AuthenticatedClient

module_logger = logging.getLogger(__name__)


class Trader(WebSocketClient):
    def __init__(self, product_id, delta=0.01,
                 auth_client=None, api_key='', secret_key='', pass_phrase='', api_url='', ws_url=''):
        if delta > 0.05:
            raise AlgoStateException('Delta very high @ {}, please check your config'.format(delta))
        self.last_heartbeat = datetime.now()
        self.heartbeat_log_interval = timedelta(minutes=5)
        self.delta = delta
        self.product_id = product_id
        self.api_key = api_key
        self.secret_key = secret_key
        self.pass_phrase = pass_phrase
        if auth_client is None:
            self.client = AuthenticatedClient(api_key, secret_key, pass_phrase, api_url=api_url)
        else:
            self.client = auth_client  # Easier to test via mock

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
        # Account information including ID and available balance
        self.accounts = {}
        # Query for account balances
        self.reset_account_balances()
        # Queue of last (1000ish) filled orders for checking missed fills
        self.opened_orders = []
        # Flag for when we're waiting for an order to settle, ignore HB/state reconcilation requests
        self.is_filling_order = False
        # Bind to websocket
        if ws_url != '':
            WebSocketClient.__init__(self, ws_url)

    def opened(self):
        """Called when the websocket handshake has been established, sends
        the initial subscribe message to gdax.
        """
        timestamp = str(time.time())
        message = timestamp + 'GET' + '/users/self/verify'
        message = message.encode('ascii')
        hmac_key = base64.b64decode(self.secret_key)
        signature = hmac.new(hmac_key, message, hashlib.sha256)
        signature_b64 = base64.b64encode(signature.digest())
        params = {
            'type': 'subscribe',
            'product_ids': [
                self.product_id,
            ],
            'signature': signature_b64.decode('utf-8'),
            'key': self.api_key,
            'passphrase': self.pass_phrase,
            'timestamp': timestamp,
            'channels': [
                'heartbeat',
                'user'
            ],
        }
        self.send(json.dumps(params))

    def closed(self, code, reason=None):
        module_logger.info('{}|Closed down. Code: {} Reason: {}'.format(self.product_id, code, reason))

    def cache_orders(self, order_id):
        """Sliding window of IDs
        """
        self.opened_orders.append(order_id)
        if len(self.opened_orders) > 1200:
            self.opened_orders.pop(0)

    def remove_order(self, order_id):
        self.opened_orders = [x for x in self.opened_orders if x != order_id]

    def received_message(self, message):
        message = json.loads(str(message))
        # Ignore messages for different products since we're subscribing to user channel
        if message.get('product_id', '') != self.product_id:
            return
        message_type = message.get('type', '')
        log_message = '{}|Message from websocket:{}'.format(self.product_id,
                                                            json.dumps(message, indent=4, sort_keys=True))
        if message_type == 'heartbeat':
            if self.last_heartbeat + self.heartbeat_log_interval <= datetime.now():
                orders = self.get_orders()
                module_logger.debug(
                    '{}|Heartbeat:{}:{} orders'.format(self.product_id, message.get('sequence', 0), len(orders)))
                for order in orders:
                    module_logger.debug(
                        '{}|{} {} @ {}:{}'.format(self.product_id, order['side'], order['size'], order['price'],
                                                  order['id']))
                self.last_heartbeat = datetime.now()
                # Also take opportunity to check for missed messages
                self.check_missed_fills()
                if not self.is_filling_order:
                    self.check_orders(orders)

            else:
                module_logger.debug(log_message)
        # Order fill message
        elif message_type == 'done':
            module_logger.info(log_message)
            self.is_filling_order = True
            self.on_order_done(message)
            self.is_filling_order = False

    def check_orders(self, orders):
        """Validate that we have the proper orders set for our current status
        """
        pass

    def check_missed_fills(self):
        """Queries for transactions by going against account history api
        https://docs.gdax.com/#get-account-history
        [
            {
                "id": "100",
                "created_at": "2014-11-07T08:19:27.028459Z",
                "amount": "0.001",
                "balance": "239.669",
                "type": "fee",
                "details": {
                    "order_id": "d50ec984-77a8-460a-b958-66f114b0de9b",
                    "trade_id": "74",
                    "product_id": "BTC-USD"
                }
            }
        ]
        https://docs.gdax.com/#get-an-order
        {
            "id": "68e6a28f-ae28-4788-8d4f-5ab4e5e5ae08",
            "size": "1.00000000",
            "product_id": "BTC-USD",
            "side": "buy",
            "stp": "dc",
            "funds": "9.9750623400000000",
            "specified_funds": "10.0000000000000000",
            "type": "market",
            "post_only": false,
            "created_at": "2016-12-08T20:09:05.508883Z",
            "done_at": "2016-12-08T20:09:05.527Z",
            "done_reason": "filled",
            "fill_fees": "0.0249376391550000",
            "filled_size": "0.01291771",
            "executed_value": "9.9750556620000000",
            "status": "done",
            "settled": true
        }
        """
        accounts = [v['id'] for v in self.accounts.values()]
        for account in accounts:
            history = self.client.get_account_history(account)[0]
            matches = [x for x in history if x['type'] == 'match']
            matches = [x for x in matches if x['details']['product_id'] == self.product_id]
            order_ids = [x['details']['order_id'] for x in matches]
            for order_id in order_ids:
                if order_id in self.opened_orders:
                    order = self.client.get_order(order_id)
                    # Done? Or just partially filled
                    if order['status'] == 'done' and order['done_reason'] == 'filled':
                        # We've missed a fill, rectify that
                        module_logger.info('{}|Missed fill for {}'.format(self.product_id, order_id))
                        self.on_order_done({
                            'order_id': order_id,
                            'reason': order['done_reason'],
                            'product_id': self.product_id,
                        })

    def reset_account_balances(self):
        """Query rest endpoint for available account balance
        https://docs.gdax.com/#accounts
        [
            {
                "id": "71452118-efc7-4cc4-8780-a5e22d4baa53",
                "currency": "BTC",
                "balance": "0.0000000000000000",
                "available": "0.0000000000000000",
                "hold": "0.0000000000000000",
                "profile_id": "75da88c5-05bf-4f54-bc85-5c775bd68254"
            },
            {
                "id": "e316cb9a-0808-4fd7-8914-97829c1925de",
                "currency": "USD",
                "balance": "80.2301373066930000",
                "available": "79.2266348066930000",
                "hold": "1.0035025000000000",
                "profile_id": "75da88c5-05bf-4f54-bc85-5c775bd68254"
            }
        ]
        """
        accounts = self.client.get_accounts()
        for currency in [self.base_currency, self.quote_currency]:
            account = [x for x in accounts if x['currency'] == currency]
            if len(account) != 1 or 'available' not in account[0]:
                module_logger.error('Account lookup failure for {} from {}'.format(
                    currency, json.dumps(accounts, indent=4, sort_keys=True)))
                raise AccountBalanceFailure(currency + ' not found in active accounts')
            self.accounts[currency] = {
                'available': float(account[0]['available']),
                'id': account[0]['id'],
            }
            module_logger.debug(
                'Set available account balances: {}'.format(json.dumps(accounts, indent=4, sort_keys=True)))

    def seed_wallet(self, quote_ccy_size):
        """At the start of the day or when the wallet is empty, need something to trade
        Place a stop buy at 1% above current market and a limit post buy at 1% below to minimize fees
        """
        ticker = self.client.get_product_ticker(self.product_id)
        if 'price' not in ticker:
            module_logger.exception('Unable to get current market quote')
            raise OrderPlacementFailure(
                'Unable to get market quote, api message: {}'.format(ticker.get('message', 'unknown error')))
        current_price = float(ticker['price'])
        size = self.to_size_increment(quote_ccy_size / current_price)
        delta = current_price * self.delta
        module_logger.info(
            '{}|Seeding wallet: {} {} @ {}/{}'.format(self.product_id, size, self.product_id, current_price + delta,
                                                      current_price - delta))
        self.buy_stop(size, current_price + delta)
        self.buy_limit_ptc(size, current_price - delta)

    def wait_for_settle(self, order_id):
        """Funds aren't available until order is in settled state. Return the full order message
        """
        settled = False
        order = None
        while not settled:
            order = self.client.get_order(order_id)
            settled = order.get('settled', False)
            if not settled:
                module_logger.info('{}|Waiting for {} to settled'.format(self.product_id, order_id))
                time.sleep(1)  # Takes a few seconds
        # Once we know order is settled, re-query account balances
        self.reset_account_balances()
        module_logger.info('{}|{} settled'.format(self.product_id, order_id))
        return order

    def place_decaying_order(self, side, order_type, size, price, retries=3, spread=0.006):
        """Makes a call to the rest order endpoint. On failure, tries again n times widening the bid/ask
        by 0.6% each time in case the order would result in taking liquidity (and thus accruing fees)
        """
        size = self.to_size_increment(size)
        if size < self.base_min_size or size > self.base_max_size:
            raise OrderPlacementFailure('Size of {} outside of exchange limits'.format(size))
        if side is 'buy':
            direction = -1
        elif side is 'sell':
            direction = 1
        else:
            raise OrderPlacementFailure('Side {} not expected, what are you doing?'.format(side))

        for i in range(retries):
            price = self.to_price_increment(price + (price * direction * i * spread))
            if side is 'buy':
                if order_type is 'limit':
                    result = self.client.buy(
                        type='limit',
                        product_id=self.product_id,
                        price=price,
                        size=size,
                        post_only=True,
                    )
                elif order_type is 'stop':
                    # Stop order will accrue fees, but can't really avoid that
                    result = self.client.buy(
                        type='stop',
                        product_id=self.product_id,
                        price=price,
                        size=size,
                        # If not specified, will hold entire account balance!
                        funds=self.to_size_increment(size * price, self.quote_currency)
                    )
                else:
                    raise OrderPlacementFailure('{} of type {} not supported'.format(side, order_type))
            else:
                if order_type is 'limit':
                    result = self.client.sell(
                        type='limit',
                        product_id=self.product_id,
                        price=price,
                        size=size,
                        # Post Only to avoid fees, order fails if it would result in taking liquidity
                        post_only=True,
                    )
                else:
                    raise OrderPlacementFailure('{} of type {} not supported'.format(side, order_type))
            if 'message' in result:
                module_logger.warning(
                    'Error placing {} {} order for {} {} @ {}, retrying. Message from api: {}'.format(
                        side, order_type, size, self.product_id, price, result['message']))
                time.sleep(1)
            else:
                self.cache_orders(result['id'])
                module_logger.info(
                    '{}|Placed {} {} order {} @ {}'.format(self.product_id, side, order_type, size, price))
                return
        # Failed on decaying price, raise an exception
        message = '{}|Error placing {} order of type {}. Retried {} times, giving up'.format(self.product_id, side,
                                                                                             order_type, retries)
        module_logger.exception(message)
        raise OrderPlacementFailure(message)

    def buy_stop(self, size, price, retries=3, spread=0.003):
        self.place_decaying_order('buy', 'stop', size, price, retries=retries, spread=spread)

    def buy_limit_ptc(self, size, price, retries=3, spread=0.003):
        self.place_decaying_order('buy', 'limit', size, price, retries=retries, spread=spread)

    def sell_limit_ptc(self, size, price, retries=3, spread=0.003):
        self.place_decaying_order('sell', 'limit', size, price, retries=retries, spread=spread)

    def get_orders(self):
        return [x for x in self.client.get_orders()[0] if x['product_id'] == self.product_id]

    def cancel_all(self):
        """BAIL!!!
        """
        orders = [x['id'] for x in self.get_orders()]
        for order_id in orders:
            result = self.client.cancel_order(order_id)
            module_logger.info('{}|Canceling {}, result: {}'.format(self.product_id, order_id,
                                                                    json.dumps(result, indent=4, sort_keys=True)))

    def on_order_done(self, message):
        """Action to take on order complete. Orders may be considered done even if they have a small amount
        of remaining size. Base implementation blocks until order settles then resets account balances
        {
            "order_id": "6decaa0f-1a71-40c1-a665-4613e6312e9f",
            "product_id": "ETH-USD",
            "profile_id": "bleh",
            "reason": "filled",
            "remaining_size": "0.00007585",
            "sequence": 2066310881,
            "side": "buy",
            "time": "2018-01-17T10:38:00.203000Z",
            "type": "done",
            "user_id": "bah"
        }
        """
        order_id = message['order_id']
        reason = message['reason']
        if reason == 'filled' and message['product_id'] == self.product_id:
            module_logger.info('{}|Order {} {}'.format(self.product_id, order_id, reason))
            if order_id not in self.opened_orders:
                module_logger.info('{}|Order not in cached orders, ignoreing'.format(self.product_id))
            else:
                self.remove_order(order_id)
                settled_order = self.wait_for_settle(order_id)
                self.reset_account_balances()
                self.place_next_orders(settled_order)

    def on_start(self):
        """Intended to be overriden.
        """
        pass

    def place_next_orders(self, message):
        """Intended to be overriden. Main algo logic goes here
        """
        pass

    def get_balance(self, currency):
        if currency in self.accounts:
            return self.accounts[currency]['available']
        else:
            return 0.0

    def to_price_increment(self, price):
        """Round to nearest price increment.
        https://docs.gdax.com/#get-products
        Otherwise order will be rejected.
        """
        diff = price - round(price)
        increments = round(diff / self.quote_increment)
        return round(price) + (increments * self.quote_increment)

    def to_size_increment(self, size_base_ccy, base_currency=''):
        if base_currency == '':
            base_currency = self.base_currency
        if base_currency in ['BTC', 'ETH', 'LTC', 'BCH']:
            return max(round(size_base_ccy, 8), self.base_min_size)
        else:
            return round(size_base_ccy, 2)


class AlgoStateException(Exception):
    def __init__(self, value):
        self.parameter = value

    def __str__(self):
        return repr(self.parameter)


class OrderFillFailure(Exception):
    def __init__(self, value):
        self.parameter = value

    def __str__(self):
        return repr(self.parameter)


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
    logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)

    # with open('../config/sandbox.json') as config:
    with open('../config/prod.json') as config:
        data = json.load(config)

    t = Trader(
        'BTC-USD',
        api_key=data['auth']['key'],
        secret_key=data['auth']['secret'],
        pass_phrase=data['auth']['phrase'],
        api_url=data['endpoints']['rest'],
        ws_url=data['endpoints']['socket']
    )
    try:
        t.connect()
        t.run_forever()
    except KeyboardInterrupt:
        t.close()
