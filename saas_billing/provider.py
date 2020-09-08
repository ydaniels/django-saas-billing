import requests

class PayPalClient():

    def __init__(self, key, secret, token=None, env='development'):
        if env != 'live':
            self.base_url = 'https://api.sandbox.paypal.com/v1'
        else:
            self.base_url = 'https://api.paypal.com/v1'

        self.s = requests.Session()
        if token:
            self.s.headers.update({'Authorization': 'Bearer %s'%token})
        else:
            res = self.s.post(self.base_url+'/oauth2/token', auth=(key, secret), data={'grant_type':'client_credentials'})
            print(res.json())
            token = res.json()['access_token']
            self.s.headers.update({'Authorization': 'Bearer %s' % token})
    def create_or_update_product(self, product_id=None, name='', description='', sub_type="SERVICE",
                                 category="SOFTWARE"):
        url = '{}/catalogs/products'.format(self.base_url)
        data = {
            "name": name,
            "description": description,
            "type": sub_type,
            "category": category
        }
        print(self.s.headers)
        print(product_id)
        if product_id:
            data.pop("name")
            url = '{}/{}'.format(url, product_id)
            res = self.s.patch(url, json=data)
        else:
            res = self.s.post(url, json=data)
        return res.json()

    def create_or_update_product_plan(self, product_id, plan_id=None, name='', description='', interval_unit='MONTH',
                                      interval_count=1, amount=0, currency='USD', include_trial=False,
                                      trial_interval="WEEK", trial_interval_count=1):

        url = '{}/billing/plans'.format(self.base_url)
        data = {
            "product_id": product_id,
            "name": name,
            "description": description,
            "billing_cycles": [
                {
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
                            "currency_code": "USD"
                        }
                    }
                }
            ],
            "payment_preferences": {
                "auto_bill_outstanding": True,
                "setup_fee": {
                    "value": amount,
                    "currency_code": currency
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
                    "interval_unit": trial_interval,
                    "interval_count": trial_interval_count
                },
                "tenure_type": "TRIAL",
                "sequence": 2,
                "total_cycles": 1
            }, )
        if plan_id:
            url = '{}/billing/plans/{}'.format(self.base_url, plan_id)
            data = {
                "description": description,
            }
            res = self.s.patch(url, data)
        else:
            res = self.s.post(url, data)
        return res.json()

    def activate(self, plan_id):
        url = '{}/billing/plans/{}/activate'.format(self.base_url, plan_id)
        res = self.s.post(url)
        return res.json()

    def deactivate(self, plan_id):
        url = '{}/billing/plans/{}/deactivate'.format(self.base_url, plan_id)
        res = self.s.post(url)
        return res.json()

    def update_plan_pricing(self, plan_id, amount, currency='USD'):
        url = '{}/billing/plans/{}/update-pricing-schemes'.format(self.base_url, plan_id)

        data = {
            "pricing_schemes": [{
                "billing_cycle_sequence": 1,
                "pricing_scheme": {
                    "fixed_price": {
                        "value": amount,
                        "currency_code": currency
                    }
                }
            }
            ]
        }
        res = self.s.post(url, data)
        return res.json()
