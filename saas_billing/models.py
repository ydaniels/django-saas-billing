import stripe
from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericRelation
from subscriptions_api.base_models import BaseSubscriptionTransaction
from subscriptions_api.models import SubscriptionPlan, PlanCost, UserSubscription
from cryptocurrency_payment.models import CryptoCurrencyPayment
from cryptocurrency_payment.models import create_new_payment
from saas_billing.provider import PayPalClient
from saas_billing.app_settings import SETTINGS

auth = SETTINGS['billing_auths']

stripe.api_key = auth['stripe']['LIVE_KEY']
paypal = PayPalClient(auth['paypal']['CLIENT_ID'], auth['paypal']['CLIENT_SECRET'], token=auth['paypal']['TOKEN'],
                      env=auth['paypal']['ENV'])


def auto_activate_subscription(subscription, amount, transaction_date=None):
    if amount > 0:
        # Search if old transaction can pay for new subscription
        for prev_transaction in subscription.user.subscription_transactions.filter(amount__lt=0).all():
            amount = float(amount) + float(prev_transaction.amount)
            if amount < 0 or amount == 0:
                prev_transaction.amount = amount
                prev_transaction.save()
                amount = 0
            else:
                prev_transaction.amount = 0
                prev_transaction.save()
    else:
        amount = 0
    transaction = subscription.record_transaction(amount=amount, transaction_date=transaction_date)
    return transaction


class StripeSubscriptionPlan(models.Model):
    plan = models.OneToOneField(SubscriptionPlan, on_delete=models.CASCADE, unique=True,
                                related_name='stripe_subscription_plan')
    plan_ref = models.CharField(max_length=250, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def create_or_update(self):
        if not self.plan_ref:
            res = stripe.Product.create(name=self.plan.plan_name, description=self.plan.plan_description,
                                        type='service')
            self.plan_ref = res.id
            self.save()
        else:
            res = stripe.Product.modify(
                self.plan_ref,
                name=self.plan.plan_name, description=self.plan.plan_description,
            )
        return res

    def __str__(self):
        return '{}|{}'.format(self.plan.plan_name, self.plan_ref)


class StripeCustomer(models.Model):
    user = models.OneToOneField(get_user_model(), on_delete=models.CASCADE, unique=True, related_name='stripe_customer')
    customer_id = models.CharField(max_length=250, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def get_or_create_subscription(self, user, stripe_sub_obj):
        try:
            return StripeSubscription.objects.get(subscription_ref=stripe_sub_obj.id).subscription
        except StripeSubscription.DoesNotExist:
            cost_ref = stripe_sub_obj.items.data[0].price.id
            cost = StripeSubscriptionPlanCost.objects.get(cost_ref=cost_ref).cost
            subscription = cost.setup_user_subscription(user, active=False, no_multipe_subscription=True,
                                                        resuse=True)
            subscription.notify_new()
            subscription.record_transaction()
            subscription.reference = 'stripe'
            subscription.save()
            StripeSubscription(subscription_ref=stripe_sub_obj.items.data[0].subscription,
                               subscription=subscription).save()
            return subscription


class StripeSubscriptionPlanCost(models.Model):
    cost = models.OneToOneField(PlanCost, on_delete=models.CASCADE, unique=True, related_name='stripe_plan_cost')
    cost_ref = models.CharField(max_length=250, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def create_or_update(self):
        if not self.cost_ref:
            res = stripe.Price.create(unit_amount_decimal=self.cost.cost * 100, currency="usd", nickname=str(self.cost),
                                      recurring={"interval": self.cost.get_recurrence_unit_display(),
                                                 'interval_count': self.cost.recurrence_period},
                                      product=self.cost.plan.stripe_subscription_plan.plan_ref)
            self.cost_ref = res.id
            self.save()
            return res

    def __str__(self):
        return '{}|{}|{}|{}'.format(self.cost.plan.plan_name, self.cost.get_recurrence_unit_display(),
                                    self.cost.recurrence_period,
                                    self.cost_ref)

    def get_or_creeate_stripe_customer_id(self, user):
        try:
            customer_id = StripeCustomer.objects.get(user=user).customer_id
        except StripeCustomer.DoesNotExist:
            customer_id = stripe.Customer.create(
                name=user.first_name + ' ' + user.last_name,
                email=user.email
            ).id
            sc = StripeCustomer(customer_id=customer_id, user=user)
            sc.save()
        return customer_id

    def pre_process_subscription(self, user):
        auth = SETTINGS['billing_auths']['stripe']
        customer = self.get_or_creeate_stripe_customer_id(user)
        session = stripe.checkout.Session.create(
            cancel_url=auth['CANCEL_URL'],
            mode='subscription',
            customer=customer,
            success_url=auth['SUCCESS_URL'],
            line_items=[{
                'price': self.cost_ref,
                'quantity': 1,
            }],
            allow_promotion_codes=True,
            payment_method_types=["card"]
        )
        return {'session_id': session.id, 'cost_id': self.cost_ref}

    def setup_subscription(self, user):
        return self.pre_process_subscription(user)


class StripeSubscription(models.Model):
    subscription = models.OneToOneField(UserSubscription, on_delete=models.CASCADE, unique=True,
                                        related_name='stripe_subscription')
    subscription_ref = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def deactivate(self):
        res = stripe.Subscription.delete(self.subscription_ref, invoice_now=True, prorate=True)
        if res.status == 'cancelled':
            return True

    def activate(self):
        self.subscription.activate()


class PaypalSubscriptionPlan(models.Model):
    plan = models.OneToOneField(SubscriptionPlan, on_delete=models.CASCADE, unique=True,
                                related_name='paypal_subscription_plan')
    plan_ref = models.CharField(max_length=250)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def create_or_update(self):
        if not self.plan_ref:
            res = paypal.create_or_update_product(name=self.plan.plan_name, description=self.plan.plan_description)
            self.plan_ref = res['id']
            self.save()
        else:
            res = paypal.create_or_update_product(self.plan_ref, name=self.plan.plan_name,
                                                  description=self.plan.plan_description)
        return res

    def __str__(self):
        return '{}|{}'.format(self.plan.plan_name, self.plan_ref)


class PaypalSubscriptionPlanCost(models.Model):
    cost = models.OneToOneField(PlanCost, on_delete=models.CASCADE, unique=True, related_name='paypal_plan_cost')
    cost_ref = models.CharField(max_length=250, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def create_or_update(self):
        if not self.cost_ref:
            trial = True
            if self.cost.plan.trial_period > 0 and self.cost.plan.trial_period < 7:
                trial_interval_unit = 'DAY'
                trial_interval_count = self.cost.plan.trial_period
            elif self.cost.plan.trial_period > 6 and self.cost.plan.trial_period < 30:
                trial_interval_unit = 'WEEK'
                trial_interval_count = int(self.cost.plan.trial_period / 7)
            elif self.cost.plan.trial_period > 29:
                trial_interval_unit = 'MONTH'
                trial_interval_count = int(self.cost.plan.trial_period / 30)
            else:
                trial_interval_unit = None
                trial_interval_count = 0
                trial = False

            res = paypal.create_or_update_product_plan(product_id=self.cost.plan.paypal_subscription_plan.plan_ref,
                                                       name=str(self.cost),
                                                       interval_unit=self.cost.get_recurrence_unit_display(),
                                                       interval_count=self.cost.recurrence_period,
                                                       amount=self.cost.cost, currency="usd", include_trial=trial,
                                                       trial_interval_unit=trial_interval_unit,
                                                       trial_interval_count=trial_interval_count)

            self.cost_ref = res['id']
            self.save()
        else:
            res = paypal.update_plan_pricing(self.cost_ref, amount=self.cost.cost, currency="usd")
        return res

    def activate(self):
        if self.cost_ref:
            return paypal.activate(self.cost_ref)

    def deactivate(self):
        if self.cost_ref:
            return paypal.deactivate(self.cost_ref)

    def setup_subscription(self, user):
        res = paypal.create_subscription(self.cost_ref, user.email, user.first_name, user.last_name,
                                         return_url=auth['paypal']['SUCCESS_URL'],
                                         cancel_url=auth['paypal']['CANCEL_URL'])
        subscription_link = None
        for link in res['links']:
            if link['rel'].lower() == 'approve':
                subscription_link = link['href']
        subscription = self.cost.setup_user_subscription(user, active=False, no_multipe_subscription=True,
                                                         resuse=True)
        subscription.reference = 'paypal'
        subscription.save()
        subscription.notify_new()
        subscription.record_transaction()
        PaypalSubscription(subscription=subscription, subscription_ref=res['id'], payment_link=subscription_link).save()
        return {'cost_id': self.cost_ref, 'payment_link': subscription_link, 'subscription_ref': res['id'],
                'id': subscription.pk}

    def __str__(self):
        return '{}|{}|{}|{}'.format(self.cost.plan.plan_name, self.cost.recurrence_unit, self.cost.recurrence_period,
                                    self.cost_ref)


class PaypalSubscription(models.Model):
    subscription = models.OneToOneField(UserSubscription, on_delete=models.CASCADE, unique=True,
                                        related_name='paypal_subscription')
    subscription_ref = models.CharField(max_length=100)
    payment_link = models.URLField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def deactivate(self):
        return paypal.cancel_subscription(self.subscription_ref)


class SubscriptionTransaction(BaseSubscriptionTransaction):
    cryptocurrency_payments = GenericRelation(CryptoCurrencyPayment)

    def create_payment(self, crypto_payment):
        plan_cost = self.subscription.plan_cost

        payment_title = '{} {}'.format(plan_cost.plan.plan_name, plan_cost.display_billing_frequency_text)
        payment = create_new_payment(crypto_payment, fiat_amount=self.amount, fiat_currency='USD',
                                     payment_title=payment_title,
                                     payment_description=plan_cost.plan.plan_description,
                                     related_object=self, user=self.user)
        return payment
