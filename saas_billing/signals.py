import stripe
from django.utils import timezone
from django.db.models import ProtectedError
from django.dispatch import receiver
from django.db.models.signals import post_save, pre_delete

from cryptocurrency_payment.models import CryptoCurrencyPayment
from saas_billing.provider import PayPalClient
from saas_billing.models import StripeSubscriptionPlan, StripeSubscriptionPlanCost, PaypalSubscriptionPlanCost

from saas_billing.provider import PayPalClient
from saas_billing.app_settings import SETTINGS

auth = SETTINGS['billing_auths']
saas_billing_settings = SETTINGS['saas_billing_settings']

@receiver(post_save, sender=CryptoCurrencyPayment, dispatch_uid='update_user_subscription')
def save_profile(sender, instance, **kwargs):
    transaction = instance.content_object
    subscription = transaction.subscription
    if instance.status == CryptoCurrencyPayment.PAYMENT_CANCELLED:
        subscription.notify_payment_error(transaction=instance)
    if instance.status == CryptoCurrencyPayment.PAYMENT_PROCESSING:
        subscription.notify_processing(transaction=instance)
    if instance.status == CryptoCurrencyPayment.PAYMENT_NEW:
        subscription.notify_new(transaction=instance)
    all_payment_paid = all(
        payment.status == CryptoCurrencyPayment.PAYMENT_PAID for payment in transaction.cryptocurrency_payments.all())
    if all_payment_paid:
        current_date = timezone.now()
        if transaction.date_transaction > current_date:
            current_date = transaction.date_transaction
        subscription.activate(current_date,  no_multiple_subscription=saas_billing_settings['SAAS_BILLING_SETTINGS'])
        subscription.notify_payment_success(transaction=instance)
        subscription.notify_activate()


@receiver(pre_delete, sender=StripeSubscriptionPlan)
def delete_stripe_subscription_plan_hook(sender, instance, using, **kwargs):
    if instance.plan_ref:
        stripe.api_key = auth['stripe']['LIVE_KEY']
        obj = stripe.Product.modify(instance.plan_ref, active=False)
        if obj.active is not False:
            raise ProtectedError


@receiver(pre_delete, sender=StripeSubscriptionPlanCost)
def delete_stripe_plan_cost_hook(sender, instance, using, **kwargs):
    if instance.cost_ref:
        stripe.api_key = auth['stripe']['LIVE_KEY']
        obj = stripe.Price.modify(instance.cost_ref, active=False)
        if obj.active is not False:
            raise ProtectedError


@receiver(pre_delete, sender=PaypalSubscriptionPlanCost)
def deactivate_paypal_plan_cost(sender, instance, using, **kwargs):
    if instance.cost_ref:
        paypal = PayPalClient(auth['paypal']['CLIENT_ID'], auth['paypal']['CLIENT_SECRET'],
                              token=auth['paypal']['TOKEN'],
                              env=auth['paypal']['ENV'])
        paypal.deactivate(instance.cost_ref)
