drf-saas-billing
======================================

|build-status-image| |pypi-version|

Overview
--------

Fastest app you'll ever user that provides paypal, stripe and bitcoin payment for your  django drf saas app subscription and billings.
based on https://github.com/ydaniels/drf-django-flexible-subscriptions


Requirements
------------

-  Python (2.7, 3.3, 3.4+)
-  Django (1.6, 1.7, 1.8+)
-  Django REST Framework (2.4, 3.0, 3.1+)

Installation
------------

Install using ``pip``\ …

.. code:: bash

    $ pip install django-saas-billing

Setup
-------

.. code:: python

    #    settings.py
    INSTALLED_APPS = [
                        ...,
                        'rest_framework',
                        'subscriptions_api',
                        'cryptocurrency_payment', #for crypto payments
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
                'PUBLISHABLE_KEY': 'Your Publishable Key',
                'LIVE_KEY': 'You Live key can be test or live',
                'CANCEL_URL': 'Where you want to redirect to if user cancels payment',
                'SUCCESS_URL': ' Where to redirect to if subscription is successful'
            },
            'paypal': {
                'CLIENT_ID': 'Your paypal rest client id',
                'CLIENT_SECRET': 'Your paypal rest secret id',
                'TOKEN': None,
                'ENV': 'live|development',
                'CANCEL_URL':  'Where to redirect to if subscription fails',
                'SUCCESS_URL':  'Where to redirect to if subscription is successful',
                'WEB_HOOK_ID': 'Your paypal rest webhook id'
            }
    }


.. code-block:: python

    path('', include('saas_billing.webhook_urls')) #Compulsory for webhook register url webhook on paypal and stripe
    #create webhook url https://yourdomain.com/billing/stripe/webhook/
    #https://yourdomain.com/billing/paypal/webhook/
    path('api/subscriptions/', include('subscriptions_api.urls')),
    path('api/', include('saas_billing.urls')), 
    

Usage
-----

Step 1
------

- Regsiter webhook urls on paypal and stripe

.. code-block:: bash

    https://yourdomain/billing/stripe/webhook/ #Please use ngrok on  localhost
    https://yourdomain/billing/paypal/webhook/


Step 2
-------

.. code-block:: python

        python manage.py migrate
        
- Create Your Plans and PlanCost  from django admin 

.. code-block:: python

        from subscription_api.models import SubscriptionPlan, PlanCost, MONTH
        free_plan = SubscriptionPlan(plan_name='Free Plan', features='{"can_perform_action": false, "token_limit": 3}', group=optional_already_created_group_obj_user_will_be_added_to)
        free_plan.save()

        pro_plan = SubscriptionPlan(plan_name='Pro Plan', features='{"can_perform_action": true, "token_limit": 10}', group=already_created_group_obj).save()
        pro_plan.save()
        PlanCost(plan=pro_plan, recurrence_unit=MONTH, cost=30).save() #30$/month
 
Tips
----
.. code-block:: python

    #In your code or views you can use
    if not user.subscription.plan.can_perform_action:
               print('I am a free user')
          else:
               print('I am a pro user')
     # features is a json dict that can be accessed from plan and group is normal django group that user will belong to


     # You should be able to implement most subscriptions access and permissions with the feautures and django groups


Step 3
------


- Generate Paypal and Stripe Plans and Pricing by using  command below

.. code-block:: python

   python manage.py billing gateway all # Create all plans on stripe.com and paypal.com
   python manage.py billing gateway <paypal|stripe> # Create   only on paypal.com or Stripe.com
   python manage.py billing gateway <paypal|stripe> --action <activate|deactivate> # Activate or Deactivate plans

Tips
-----


Getting Active Subscriptions Of a User
------------------------------------------

.. code-block:: python

    subscription = request.user.subscriptions.filter(active=True).first() #if you only allow a subscription per user
    subscription.transactions.all() #returns all transaction payment of this subscriptions
    request.user.subscriptions.filter(active=True).all() #for all subscriptions if you allow multiple subscription per user

.. code-block:: python

    transactions = request.user.subscription_transactions.all() #Returns all payment trasnsaction for this user

Building A  Payment And Active Subscription View
------------------------------------------------

.. code-block:: python

    from saas_billing.models import SubscriptionTransaction #import this to show crypto payments
    from subscriptions_api.base_models import BaseSubscriptionTransaction # use this to only show paypal & stripe payment

    class BillingView(ListView):
        model = BaseSubscriptionTransaction
        context_object_name = 'payment_transactions'
        template_name = 'transactions.html'

        def get_queryset(self):
              return self.request.user.subscription_transactions.order_by('-date_transaction')

        def get_context_data(self, **kwargs):
              context = super().get_context_data(**kwargs)
              context['active_subscription'] = self.request.user.subscriptions.filter(active=True).first()
              return context

.. code-block:: html

     <!-- transactions.html -->
      <table class="table table-bordernone display" id="basic-1">
                <thead>
                  <tr>
                    <th scope="col">Date</th>
                    <th scope="col">Subscription</th>
                    <th scope="col">Amount</th>
                    <th scope="col">Status</th>
                  </tr>
                </thead>
                <tbody>
                {% for tran in payment_transactions %}
                  <tr>
                    <td>{{ tran.payment_transactions }}</td>
                    <td>
                      <div class="product-name">{{ tran.subscription_name }}
                      </div>
                    </td>
                    <td>${{ tran.amount }}</td>
                    <td>Paid</td>
                  </tr>
                {% endfor %}
                </tbody>
              </table>


Step 4
--------

How To Subscribe A User to a Plan Cost
---------------------------------------
-Send a post request with data { gateway: <stripe|payment>, quantity: 1 } to url below where ${id} is the created  plan cost id '/api/plan-costs/${id}/init_gateway_subscription/'

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

Tips Api URL To use in frontend app for drf users
------------------------------------------------

.. code-block:: python

    '/api/subscriptions/plans/'  #Get all plans to display in frontend
    '/api/subscriptions/get_active_subscription/' # Returns active UserSubscription Object for the current logged in user
    '/api/subscriptions/${id}/unsubscribe_user/' # Unsubscribe user from subscription with ${id}
    '/api/transactions/' # Get payment transactions
    '/api/transactions/${id}/' # Get single payment transaction with ${id}
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
