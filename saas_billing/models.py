import stripe
import logging
from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericRelation
from subscriptions_api.base_models import BaseSubscriptionTransaction
from subscriptions_api.models import SubscriptionPlan, PlanCost, UserSubscription
from cryptocurrency_payment.models import CryptoCurrencyPayment
from cryptocurrency_payment.models import create_new_payment
from saas_billing.provider import PayPalClient
from saas_billing.app_settings import SETTINGS
from django.apps import apps
_logger = logging.getLogger(__name__)

auth = SETTINGS['billing_auths']
saas_models = SETTINGS['billing_models']
saas_billing_settings = SETTINGS['saas_billing_settings']

stripe.api_key = auth['stripe']['LIVE_KEY']
def get_paypal_client():
    paypal = PayPalClient(auth['paypal']['CLIENT_ID'], auth['paypal']['CLIENT_SECRET'], token=auth['paypal']['TOKEN'],
                      env=auth['paypal']['ENV'])
    return paypal


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




class BillingUserSubscription(UserSubscription):
    class Meta:
        proxy = True

    def deactivate_subscription(self):

        if self.reference and self.reference in saas_models:
            # deactivate on gateway
            subscription_model = saas_models[self.reference]['subscription']
            Model = apps.get_model(subscription_model)
            obj = Model.objects.get(subscription=self)
            res = obj.deactivate()
            if res is True:
                self.deactivate(activate_default=True)
        else:
            self.deactivate(activate_default=True)
            self.notify_deactivate()


class BillingPlanCost(PlanCost):
    class Meta:
        proxy = True

    def setup_subscription(self, user, gateway, quantity=1):
        cost_model_str = SETTINGS['billing_models'][gateway]['cost']
        Model = apps.get_model(cost_model_str)
        external_cost = Model.objects.get(cost=self)
        data = external_cost.setup_subscription(user, quantity=quantity)
        return data



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

    def get_or_create_subscription(self, stripe_sub_obj):
        try:
            return StripeSubscription.objects.get(subscription_ref=stripe_sub_obj.id).subscription
        except StripeSubscription.DoesNotExist:
            cost_ref =  stripe_sub_obj['plan']['id']
            cost = StripeSubscriptionPlanCost.objects.get(cost_ref=cost_ref).cost
            subscription = cost.setup_user_subscription(self.user, active=False, no_multiple_subscription=saas_billing_settings['SAAS_BILLING_SETTINGS'],
                                                        resuse=True)
            subscription.reference = 'stripe'
            subscription.quantity = stripe_sub_obj.items.data[0].quantity
            subscription.save()
            StripeSubscription.objects.update_or_create(subscription=subscription, defaults={'subscription_ref':  stripe_sub_obj.id })
            return subscription

    def __str__(self):
        return '{} {} {}'.format(self.id, self.user, self.customer_id)

class StripeSubscriptionPlanCost(models.Model):
    cost = models.OneToOneField(PlanCost, on_delete=models.CASCADE, unique=True, related_name='stripe_plan_cost')
    cost_ref = models.CharField(max_length=250, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def create_or_update(self):
        if self.cost.cost <= 0:
            #Dont create plan with 0 cost they are free plan
            return
        if not self.cost_ref and self.cost.plan.stripe_subscription_plan.plan_ref:
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

    def get_or_create_stripe_customer_id(self, user):
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

    def pre_process_subscription(self, user, quantity=1):
        auth = SETTINGS['billing_auths']['stripe']
        customer = self.get_or_create_stripe_customer_id(user)
        session = stripe.checkout.Session.create(
            cancel_url=auth['CANCEL_URL'],
            mode='subscription',
            customer=customer,
            success_url=auth['SUCCESS_URL'],
            line_items=[{
                'price': self.cost_ref,
                'quantity': quantity,
            }],
            allow_promotion_codes=True,
            payment_method_types=["card"]
        )
        return {'session_id': session.id, 'cost_id': self.cost_ref}

    def setup_subscription(self, user, quantity=1):
        return self.pre_process_subscription(user, quantity)


class StripeSubscription(models.Model):
    subscription = models.OneToOneField(UserSubscription, on_delete=models.CASCADE,
                                        related_name='stripe_subscription')
    subscription_ref = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def deactivate(self):
        res = stripe.Subscription.delete(self.subscription_ref, invoice_now=True, prorate=True)
        if res.status == 'canceled':
            return True

    def activate(self):
        self.subscription.activate()

    def __str__(self):
        return '{}|{}|{}'.format(self.id, self.subscription, self.subscription_ref)



class PaypalSubscriptionPlan(models.Model):
    plan = models.OneToOneField(SubscriptionPlan, on_delete=models.CASCADE, unique=True,
                                related_name='paypal_subscription_plan')
    plan_ref = models.CharField(max_length=250)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def create_or_update(self):
        paypal = get_paypal_client()
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
        if self.cost.cost <= 0:
            #Dont create plan with 0 cost they are free plan
            return
        paypal = get_paypal_client()
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
        paypal = get_paypal_client()
        if self.cost_ref:
            return paypal.activate(self.cost_ref)

    def deactivate(self):
        paypal = get_paypal_client()
        if self.cost_ref:
            return paypal.deactivate(self.cost_ref)

    def setup_subscription(self, user, quantity=1):
        paypal = get_paypal_client()
        res = paypal.create_subscription(self.cost_ref, user.email, user.first_name, user.last_name,
                                         return_url=auth['paypal']['SUCCESS_URL'],
                                         cancel_url=auth['paypal']['CANCEL_URL'])
        subscription_link = None
        for link in res['links']:
            if link['rel'].lower() == 'approve':
                subscription_link = link['href']
        subscription = self.cost.setup_user_subscription(user, active=False, no_multiple_subscription=saas_billing_settings['SAAS_BILLING_SETTINGS'],
                                                         resuse=True)
        subscription.reference = 'paypal'
        subscription.quantity =  quantity
        subscription.save()
        #subscription.notify_new()
        #subscription.record_transaction()
        obj, created = PaypalSubscription.objects.update_or_create(subscription=subscription, defaults={'subscription_ref': res['id'],'payment_link':subscription_link})
        _logger.debug("Created or updated subscription for paypal sub=%s created=%s obj=%s subscription=%s ",res['id'], created, obj, subscription)
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
        paypal = get_paypal_client()
        return paypal.cancel_subscription(self.subscription_ref)

    def __str__(self):
        return '{}|{}|{}'.format(self.id, self.subscription, self.subscription_ref)

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
