from django.utils import timezone

from cryptocurrency_payment.models import CryptoCurrencyPayment
from django.dispatch import receiver
from django.db.models.signals import post_save

from subscriptions_api.models import UserSubscription
from saas_billing.models import SubscriptionTransaction


@receiver(post_save, sender=CryptoCurrencyPayment, dispatch_uid='update_user_subscription')
def save_profile(sender, instance, **kwargs):
    subscription = UserSubscription.objects.filter(subscription=instance.content_object.subscription.pk,
                                                   user=instance.content_object.user).all().order_by('-id')[0]
    transaction = SubscriptionTransaction.objects.get(pk=instance.content_object.pk)

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
        subscription.activate(current_date)
        subscription.notify_payment_success(transaction=instance)
        subscription.notify_activate()
