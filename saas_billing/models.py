from django.db import models
from django.contrib.contenttypes.fields import GenericRelation
from subscriptions_api.base_models import BaseSubscriptionTransaction
from subscriptions_api.models import SubscriptionPlan, PlanCost
from cryptocurrency_payment.models import CryptoCurrencyPayment
from cryptocurrency_payment.models import create_new_payment
from saas_billing.app_settings import SETTINGS
from saas_billing.provider import stripe, paypal

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



class StripeSubscriptionPlan(models.Model):


    plan = models.OneToOneField(SubscriptionPlan, on_delete=models.CASCADE, unique=True, related_name='stripe_subscription_plan')
    plan_ref = models.CharField(max_length=250, null=True, blank=True)

    def create_or_update(self):
        if not self.plan_ref:
            res = stripe.Product.create(name=self.plan.plan_name, description=self.plan.plan_description)
            self.plan_ref = res.id
            self.save()
        else:
            stripe.Product.modify(
                self.plan_ref,
                name=self.plan.plan_name, description=self.plan.plan_description,
            )

    def __str__(self):
        return '{}|{}'.format(self.plan.plan_name, self.plan_ref)


class StripeSubscriptionPlanCost(models.Model):

    cost = models.OneToOneField(PlanCost, on_delete=models.CASCADE, unique=True, related_name='stripe_plan_cost')
    cost_ref = models.CharField(max_length=250, null=True, blank=True)

    def create_or_update(self):
        if not self.cost_ref:
            res = stripe.Price.create(unit_amount=self.cost.cost * 100, currency="usd",
                                recurring={"interval": self.cost.recurrence_unit, 'interval_count': self.cost.recurrence_period}, product=self.cost.plan.stripe_subscription_plan.plan_ref)
            self.cost_ref = res.id
            self.save()
        else:
            stripe.Price.modify(self.cost_ref, unit_amount=self.cost.cost * 100, currency="usd",
                                recurring={"interval": self.cost.recurrence_unit,
                                           'interval_count': self.cost.recurrence_period},
                                product=self.cost.plan.stripe_subscription_plan.plan_ref)

    def __str__(self):
        return '{}|{}|{}|{}'.format(self.cost.plan.plan, self.cost.recurrence_unit, self.cost.recurrence_period, self.cost_ref)

    def pre_process_subscription(self, user):
        auth = SETTINGS['billing_auths']['stripe']
        session = stripe.checkout.Session.create(
            cancel_url = auth['CANCEL_URL'],
            mode = 'subscription',
            success_url = auth['SUCCESS_URL'],
            client_reference_id = user.id,
            email = user.email,
            allow_promotion_codes = True
        )
        return session.id

class PaypalSubscriptionPlan(models.Model):


    plan = models.OneToOneField(SubscriptionPlan, on_delete=models.CASCADE, unique=True, related_name='paypal_subscription_plan')
    plan_ref = models.CharField(max_length=250)

    def create_or_update(self):
        if not self.plan_ref:
            res = paypal.create_or_update_product(name=self.plan.plan_name, description=self.plan.plan_description)
            self.plan_ref = res['id']
            self.save()
        else:
            paypal.create_or_update_product(self.plan_ref, name=self.plan.plan_name, description=self.plan.plan_description)

    def __str__(self):
        return '{}|{}'.format(self.plan.plan_name, self.plan_ref)

class PaypalSubscriptionPlanCost(models.Model):

    cost = models.OneToOneField(PlanCost, on_delete=models.CASCADE, unique=True, related_name='paypal_plan_cost')
    cost_ref = models.CharField(max_length=250, null=True, blank=True)

    def create_or_update(self):
        if not self.cost_ref:
            res = paypal.create_or_update_product_plan(product_id=self.cost.plan.paypal_subscription_plan.plan_ref, interval_unit=self.cost.recurrence_unit,
                                                       interval_count=self.cost.recurrence_period, amount=self.cost.cost, currency="usd", include_trial=True)
            self.cost_ref = res['id']
            self.save()
        else:
            paypal.update_plan_pricing(self.cost_ref, amount=self.cost.cost, currency="usd")

    def activate(self):
        if self.cost_ref:
            paypal.activate(self.cost_ref)

    def deactivate(self):
        if self.cost_ref:
            paypal.deactivate(self.cost_ref)

    def __str__(self):
        return '{}|{}|{}|{}'.format(self.cost.plan.plan, self.cost.recurrence_unit, self.cost.recurrence_period, self.cost_ref)