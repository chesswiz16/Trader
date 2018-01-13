import json
import logging

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
        self.available_balance = {}
        self.orders = {}

        # Query for account balances
        self.reset_account_balances()

        # Query for current open orders
        self.reset_open_orders()

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
            self.available_balance[currency] = float(account[0]['available'])
            module_logger.info(
                'Set available account balances: {}'.format(json.dumps(accounts, indent=4, sort_keys=True)))

    def reset_open_orders(self):
        """Query rest endpoint for all open orders.
        https://docs.gdax.com/#place-a-new-order
        [
            {
                "id": "d0c5340b-6d6c-49d9-b567-48c4bfca13d2",
                "price": "0.10000000",
                "size": "0.01000000",
                "product_id": "BTC-USD",
                "side": "buy",
                "stp": "dc",
                "type": "limit",
                "time_in_force": "GTC",
                "post_only": false,
                "created_at": "2016-12-08T20:02:28.53864Z",
                "fill_fees": "0.0000000000000000",
                "filled_size": "0.00000000",
                "executed_value": "0.0000000000000000",
                "status": "open",
                "settled": false
            },
            {
                "id": "8b99b139-58f2-4ab2-8e7a-c11c846e3022",
                "price": "1.00000000",
                "size": "1.00000000",
                "product_id": "BTC-USD",
                "side": "buy",
                "stp": "dc",
                "type": "limit",
                "time_in_force": "GTC",
                "post_only": false,
                "created_at": "2016-12-08T20:01:19.038644Z",
                "fill_fees": "0.0000000000000000",
                "filled_size": "0.00000000",
                "executed_value": "0.0000000000000000",
                "status": "open",
                "settled": false
            }
        ]
        """
        orders = self.client.get_orders()[0]
        self.orders = dict(zip([x['id'] for x in orders], orders))
        module_logger.info(
            'Set orders on {} with increment {} and {} open orders: {}'.format(
                self.product_id, self.quote_increment, len(self.orders),
                json.dumps(self.orders, indent=4, sort_keys=True)))

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
        delta = current_price * 0.01
        module_logger.info(
            'Seeding wallet: {} {} @ {}/{}'.format(size, self.product_id, current_price + delta, current_price - delta))
        self.buy_stop(size, current_price + delta)
        self.buy_limit_ptc(size, current_price - delta)

    def place_decaying_order(self, side, order_type, size, price, retries=3, spread=0.006):
        """Makes a call to the rest order endpoint. On failure, tries again n times widening the bid/ask
        by 0.6% each time in case the order would result in taking liquidity (and thus accruing fees)
        """
        if size < self.base_min_size or size > self.base_max_size:
            raise OrderPlacementFailure('Size of {} outside of exchange limits'.format(size))
        if side is 'buy':
            balance = self.get_balance(self.quote_currency)
            direction = -1
        elif side is 'sell':
            balance = self.get_balance(self.base_currency)
            direction = 1
        else:
            raise OrderPlacementFailure('Side {} not expected, what are you doing?'.format(side))

        for i in range(retries):
            price = self.to_price_increment(price + (price * direction * i * spread))
            if side is 'buy':
                if balance < size * price:
                    module_logger.exception(
                        'Insufficient funds for buy of {}, current balance {}'.format(size, balance))
                    raise AccountBalanceFailure('Needed {} have {}'.format(size * price, balance))
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
                if balance < size:
                    module_logger.exception(
                        'Insufficient funds for sell of {}, current balance {}'.format(size, balance))
                    raise AccountBalanceFailure('Needed {} have {}'.format(size, balance))
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
            else:
                self.orders[result['id']] = result
                module_logger.info(
                    'Placed {} {} order for {} {} @ {}'.format(side, order_type, size, self.product_id, price))
                # Update account balances
                if side is 'buy':
                    self.available_balance[self.quote_currency] -= size * price
                else:
                    self.available_balance[self.base_currency] -= size
                return
        # Failed on decaying price, raise an exception
        message = 'Error placing {} order of type {}. Retried {} times, giving up'.format(side, order_type, retries)
        module_logger.exception(message)
        raise OrderPlacementFailure(message)

    def buy_stop(self, size, price, retries=3, spread=0.003):
        self.place_decaying_order('buy', 'stop', size, price, retries=retries, spread=spread)

    def buy_limit_ptc(self, size, price, retries=3, spread=0.003):
        self.place_decaying_order('buy', 'limit', size, price, retries=retries, spread=spread)

    def sell_limit_ptc(self, size, price, retries=3, spread=0.003):
        self.place_decaying_order('sell', 'limit', size, price, retries=retries, spread=spread)

    def cancel_all(self):
        """BAIL!!!
        """
        for order_id in self.orders:
            result = self.client.cancel_order(order_id)
            module_logger.info(
                'Canceling {}, result: {}'.format(order_id, json.dumps(result, indent=4, sort_keys=True)))
        # Call cancel all for good measure (don't think it actually works)
        self.client.cancel_all()

    def on_order_done(self, message):
        """Action to take on order fill/cancel. Base implementation simply updates the order cache and currency balances.
        Assumes messages come from the "user" channel documented in
        https://docs.gdax.com/#the-code-classprettyprintfullcode-channel.

        Any order_id's not saved already are assumed to be an error condition triggering a new call to the
        authenticated rest endpoint.
        Expects a json message of the below format:
        {
            "type": "done",
            "time": "2014-11-07T08:19:27.028459Z",
            "product_id": "BTC-USD",
            "sequence": 10,
            "price": "200.2",
            "order_id": "d50ec984-77a8-460a-b958-66f114b0de9b",
            "reason": "filled", // or "canceled"
            "side": "sell",
            "remaining_size": "0"
        }
        """
        try:
            if 'type' not in message or message['type'] is not 'done':
                raise OrderFillFailure(
                    'Unexpected type {}, resetting order/account status'.format(message.get('type', 'unknown')))
            expected_keys = ['order_id', 'reason', 'side', 'remaining_size', 'price']
            checked_order_message = {}
            for expected_key in expected_keys:
                if expected_key not in message:
                    raise OrderFillFailure(
                        'Expected key {} not received in order message, calling rest endpoint to reset: {}'.format(
                            expected_key, message))
                else:
                    checked_order_message[expected_key] = message[expected_key]

            # Check order id has been saved
            order_id = checked_order_message['order_id']
            if order_id not in self.orders:
                raise OrderFillFailure(
                    'Order Id {} not in saved orders, calling rest endpoint to reset'.format(
                        checked_order_message['order_id']))

            # Update account/order status
            if checked_order_message['reason'] == 'canceled':
                self.orders.pop(order_id)
                return {}
            elif checked_order_message['reason'] == 'filled':
                # Check fill price and remaining size
                side = checked_order_message['side']
                price = float(checked_order_message['price'])
                remaining = float(checked_order_message['remaining_size'])
                original = float(self.orders[order_id]['size'])
                filled = original - remaining
                module_logger.info('Order {} filled for {} {} {} @ {}, remaining {}'.format(
                    order_id, side, original, self.base_currency, price, remaining))
                if remaining == 0:
                    self.orders.pop(order_id)
                else:
                    self.orders[order_id]['size'] = remaining

                if side == 'buy':
                    if self.base_currency not in self.available_balance:
                        self.available_balance[self.base_currency] = filled
                    else:
                        self.available_balance[self.base_currency] += filled
                    # Must have had funds available to place order in the first place
                    if self.quote_currency not in self.available_balance:
                        raise OrderFillFailure(
                            'No available balance in quote currency {} on buy, resetting order status'.format(
                                self.quote_currency))
                    else:
                        self.available_balance[self.quote_currency] -= filled * price
                elif side == 'sell':
                    # Must have had funds available to place order in the first place
                    if self.base_currency not in self.available_balance:
                        raise OrderFillFailure(
                            'No available balance in base currency {} on sell, resetting order status'.format(
                                self.base_currency))
                    else:
                        self.available_balance[self.base_currency] -= filled

                    if self.quote_currency not in self.available_balance:
                        self.available_balance[self.quote_currency] = filled * price
                    else:
                        self.available_balance[self.quote_currency] += filled * price
                else:
                    raise OrderFillFailure('Unexpected side {}, resetting order status'.format(side))
                return checked_order_message
            else:
                raise OrderFillFailure(
                    'Unknown order done reason {}, calling rest endpoint to reset'.format(
                        checked_order_message['reason']))
        except OrderFillFailure as e:
            module_logger.exception(e.parameter)
            self.reset_open_orders()
            self.reset_account_balances()
            raise e

    def get_balance(self, currency):
        return self.available_balance.get(currency, 0.0)

    def to_price_increment(self, price):
        """Round to nearest price increment.
        https://docs.gdax.com/#get-products
        Otherwise order will be rejected.
        """
        diff = price - round(price)
        increments = round(diff / self.quote_increment)
        return round(price) + (increments * self.quote_increment)

    def to_size_increment(self, size_base_ccy, base_currency=''):
        """1 satoshi or wei
        """
        if base_currency == '':
            base_currency = self.base_currency
        if base_currency == 'BTC':
            return round(size_base_ccy, 8)
        elif base_currency == 'ETH':
            return round(size_base_ccy, 18)
        else:
            return round(size_base_ccy, 2)


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
    from gdax.authenticated_client import AuthenticatedClient

    with open('../config/sandbox.json') as config:
        data = json.load(config)

    auth_client = AuthenticatedClient(
        data['auth']['key'],
        data['auth']['secret'],
        data['auth']['phrase'],
        api_url=data['endpoints']['rest'],
    )
    res = auth_client.get_accounts()
    print(json.dumps(res, indent=4, sort_keys=True))
    res = auth_client.get_products()
    print(json.dumps(res, indent=4, sort_keys=True))
    res = auth_client.get_product_ticker('BTC-USD')
    print(json.dumps(res, indent=4, sort_keys=True))
    # res = auth_client.get_product_trades('BTC-USD')
    # print(json.dumps(res, indent=4, sort_keys=True))
