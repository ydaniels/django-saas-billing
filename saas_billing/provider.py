import logging

logger = logging.getLogger(__name__)
import requests


class PayPalClient():

    def __init__(self, key, secret, token=None, env='development', brand_name='Paypal'):
        if env != 'live':
            self.base_url = 'https://api.sandbox.paypal.com/v1'
        else:
            self.base_url = 'https://api.paypal.com/v1'

        self.s = requests.Session()
        self.brand_name = brand_name
        if token:
            self.s.headers.update({'Authorization': 'Bearer %s' % token})
        else:
            res = self.s.post(self.base_url + '/oauth2/token', auth=(key, secret),
                              data={'grant_type': 'client_credentials'})

            token = res.json()['access_token']
            self.s.headers.update({'Authorization': 'Bearer %s' % token})
            # print(self.s.headers)

    def create_or_update_product(self, product_id=None, name='', description='', sub_type="SERVICE",
                                 category="SOFTWARE"):
        url = '{}/catalogs/products'.format(self.base_url)
        data = {
            "name": name,
            "description": description,
            "type": sub_type,
            "category": category
        }
        if product_id:
            data.pop("name")
            url = '{}/{}'.format(url, product_id)
            res = self.s.patch(url, json=data)
        else:
            res = self.s.post(url, json=data)
        return res.json()

    def create_or_update_product_plan(self, product_id, plan_id=None, name='', description=None, interval_unit='MONTH',
                                      interval_count=1, amount=0, currency='USD', include_trial=False,
                                      trial_interval_unit="WEEK", trial_interval_count=1):

        url = '{}/billing/plans'.format(self.base_url)
        data = {
            "product_id": product_id,
            "name": name,
            "description": description,
            "billing_cycles": [
            ],
            "payment_preferences": {
                "auto_bill_outstanding": True,
                "setup_fee": {
                    "value": 0,
                    "currency_code": currency.upper()
                },
                "setup_fee_failure_action": "CONTINUE",
                "payment_failure_threshold": 3
            },
            "taxes": {
                "percentage": "0",
                "inclusive": False
            }
        }
        if include_trial:
            data["billing_cycles"].append({
                "frequency": {
                    "interval_unit": trial_interval_unit,
                    "interval_count": trial_interval_count
                },
                "tenure_type": "TRIAL",
                "sequence": 1,
                "total_cycles": 1
            }, )
            data["billing_cycles"].append({
                "frequency": {
                    "interval_unit": interval_unit,
                    "interval_count": interval_count
                },
                "tenure_type": "REGULAR",
                "sequence": 2,
                "total_cycles": 0,
                "pricing_scheme": {
                    "fixed_price": {
                        "value": amount,
                        "currency_code": currency.upper()
                    }
                }
            })
        else:
            data["billing_cycles"].append({
                "frequency": {
                    "interval_unit": interval_unit,
                    "interval_count": interval_count
                },
                "tenure_type": "REGULAR",
                "sequence": 1,
                "total_cycles": 0,
                "pricing_scheme": {
                    "fixed_price": {
                        "value": amount,
                        "currency_code": currency.upper()
                    }
                }
            })
        if plan_id:
            url = '{}/billing/plans/{}'.format(self.base_url, plan_id)
            data = {
                "description": description,
            }
            res = self.s.patch(url, json=data)
        else:
            res = self.s.post(url, json=data)
        return res.json()

    def create_subscription(self, plan_id, email, first_name='', last_name='', return_url=None, cancel_url=None,
                            start_time=None):
        url = '{}/billing/subscriptions'.format(self.base_url)
        data = {
            "plan_id": plan_id,
            "start_time": start_time,
            "subscriber": {
                "name": {
                    "given_name": first_name,
                    "surname": last_name
                },
                "email_address": email
            },
            "application_context": {
                "brand_name": self.brand_name,
                "locale": "en-US",
                "shipping_preference": "SET_PROVIDED_ADDRESS",
                "user_action": "SUBSCRIBE_NOW",
                "payment_method": {
                    "payer_selected": "PAYPAL",
                    "payee_preferred": "IMMEDIATE_PAYMENT_REQUIRED"
                },
                "return_url": return_url,
                "cancel_url": cancel_url
            }
        }
        res = self.s.post(url, json=data)
        return res.json()

    def activate(self, plan_id):
        url = '{}/billing/plans/{}/activate'.format(self.base_url, plan_id)
        res = self.s.post(url)
        if res.status_code != 204:
            raise requests.ConnectionError(res.content)

    def deactivate(self, plan_id):
        url = '{}/billing/plans/{}/deactivate'.format(self.base_url, plan_id)
        res = self.s.post(url)
        if res.status_code != 204:
            raise requests.ConnectionError(res.content)

    def cancel_subscription(self, subscription_id):
        url = '{}/billing/subscriptions/{}/cancel'.format(self.base_url, subscription_id)
        res = self.s.post(url, json={})
        if res.status_code != 204:
            raise requests.ConnectionError(res.content)
        return True

    def update_plan_pricing(self, plan_id, amount, currency='USD'):
        url = '{}/billing/plans/{}/update-pricing-schemes'.format(self.base_url, plan_id)

        data = {
            "pricing_schemes": [{
                "billing_cycle_sequence": 1,
                "pricing_scheme": {
                    "fixed_price": {
                        "value": amount,
                        "currency_code": currency.upper()
                    }
                }
            }
            ]
        }
        res = self.s.post(url, json=data)
        if res.status_code != 204:
            logger.exception(res.content)

    def verify_webhook(self, data):
        url = '{}/notifications/verify-webhook-signature'.format(self.base_url)
        r = self.s.post(url, json=data)
        if r.status_code == 200 and r.json()["verification_status"] == "SUCCESS":
            return True
        return False
