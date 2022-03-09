drf-saas-billing
======================================

|build-status-image| |pypi-version|

Overview
--------

Simplest app you'll ever user that provides paypal, stripe and bitcoin payment for your  django drf saas app subscription and billings.
based on https://github.com/ydaniels/drf-django-flexible-subscriptions
Requirements
------------

-  Python (2.7, 3.3, 3.4)
-  Django (1.6, 1.7, 1.8)
-  Django REST Framework (2.4, 3.0, 3.1)

Installation
------------

Install using ``pip``\ …

.. code:: bash

    $ pip install drf-saas-billing

Example
-------
To use in
   *settings.py*

.. code:: python
    INSTALLED_APPS = [
                        ...,
                        'rest_framework',
                        'subscriptions_api',
                        'cryptocurrency_payment', #To accept bitcoin payment
                        'saas_billing'
                        ]
    SUBSCRIPTIONS_API_SUBSCRIPTIONTRANSACTION_MODEL = 'saas_billing.SubscriptionTransaction'
    SAAS_BILLING_MODELS = {
            'stripe': {
                'plan': 'saas_billing.StripeSubscriptionPlan',
                'cost': 'saas_billing.StripeSubscriptionPlanCost',
                'subscription': 'saas_billing.StripeSubscription'
            },
            'paypal': {
                'plan': 'saas_billing.PaypalSubscriptionPlan',
                'cost': 'saas_billing.PaypalSubscriptionPlanCost',
                'subscription': 'saas_billing.PaypalSubscription'
            }
        }
    SAAS_BILLING_AUTH = {
            'stripe': {
                'PUBLISHABLE_KEY': env.str('STRIPE_PUBLISHABLE_KEY'),
                'LIVE_KEY': env.str('STRIPE_LIVE_KEY'),
                'CANCEL_URL': env.str('PAYMENT_WEBHOOK_CANCEL_URL'),
                'SUCCESS_URL': env.str('PAYMENT_WEBHOOK_SUCCESS_URL')
            },
            'paypal': {
                'CLIENT_ID': env.str('PAYPAL_CLIENT_ID'),
                'CLIENT_SECRET': env.str('PAYPAL_CLIENT_SECRET'),
                'TOKEN': None,
                'ENV': env.str('PAYPAL_CLIENT_ENV'),
                'CANCEL_URL': env.str('PAYMENT_WEBHOOK_CANCEL_URL'),
                'SUCCESS_URL': env.str('PAYMENT_WEBHOOK_SUCCESS_URL'),
                'WEB_HOOK_ID': env.str('PAYPAL_WEB_HOOK_ID')
            }
    }

*urls.py**

.. code-block:: python
    url(r'^api/', include('saas_billing.urls')),

**How To Use**
**Step 1**
- Create Your Plans and PlanCost Using drf-django-flexible-subscriptions or from django admin
** Step 2**
- Generate Paypal and Stripe Plans and Pricing by using command any of the command below
.. code-block:: python
   python manage.py billing gateway all # Create all plans for stripe and paypal
   python manage.py billing gateway <paypal|stripe> # Create   for paypal or Stripe
   python manage.py billing gateway <paypal|stripe> --action <activate|deactivate> # Activate or Deactivate plans

**Step 3**
-- Api URL To use in frontend app

.. code-block:: python
    '/api/subscriptions/get_active_subscription/' # Returns active UserSubscription Object for the current logged in user
    '/api/subscriptions/${id}/unsubscribe_user/' # Unsubscribe user from subscription with ${id}
    '/api/transactions/' # Get payment transactions
    '/api/transactions/${id}/' # Get single payment transaction with ${id}
**How To Subscribe A User to a Plan Cost**
-Send a post request with data { gateway: <stripe|payment>} to url below where ${id} is the created  plan cost id
'/api/plan-costs/${id}/init_gateway_subscription/'
- For paypal redirect user to payment_link value from returned data
.. code-block:: javascript
   (post_return_data) => {
    window.open(post_return_data.payment_link, '_blank').focus();
    }
- For stripe start session with session id returned from post requsest using stripe javascript sdk
.. code-block:: javascript
   (post_return_data) => {
    var stripe = window.Stripe(YOUR_STRIPE_PUBLIC_KEY)
    return stripe.redirectToCheckout({ sessionId: post_return_data.session_id })
    }
**Thats all you need to start accepting payment**
**Extra API URL**
-

Testing
-------

Install testing requirements.

.. code:: bash

    $ pip install -r requirements.txt

Run with runtests.

.. code:: bash

    $ ./runtests.py

You can also use the excellent `tox`_ testing tool to run the tests
against all supported versions of Python and Django. Install tox
globally, and then simply run:

.. code:: bash

    $ tox

Documentation
-------------

To build the documentation, you’ll need to install ``mkdocs``.

.. code:: bash

    $ pip install mkdocs

To preview the documentation:

.. code:: bash

    $ mkdocs serve
    Running at: http://127.0.0.1:8000/

To build the documentation:

.. code:: bash

    $ mkdocs build

.. _tox: http://tox.readthedocs.org/en/latest/

.. |build-status-image| image:: https://secure.travis-ci.org/ydaniels/drf-saas-billing.svg?branch=master
   :target: http://travis-ci.org/ydaniels/drf-saas-billing?branch=master
.. |pypi-version| image:: https://img.shields.io/pypi/v/drf-saas-billing.svg
   :target: https://pypi.python.org/pypi/drf-saas-billing
