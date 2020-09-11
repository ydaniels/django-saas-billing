"""Utility/helper functions for Django Flexible Subscriptions."""
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta
from saas_billing.models import UserSubscription
from saas_billing.models import auto_activate_subscription
from saas_billing.app_settings import SETTINGS

billing_models = SETTINGS['billing_models']
payment_references = [key for key in billing_models.keys()]


class Manager():
    """Manager object to help manage subscriptions & billing."""

    def process_expired_subscriptions(self, date):
        expired_subscriptions = UserSubscription.objects.filter(
            Q(active=True) & Q(cancelled=False)
            & Q(date_billing_end__lte=date)
        ).exclude(reference__in=payment_references)

        for subscription in expired_subscriptions:
            subscription.deactivate()
            subscription.notify_expired()

    def process_one_week_due_subscriptions(self, date):
        date = date + timedelta(days=7)
        due_subscriptions = UserSubscription.objects.filter(
            Q(active=True) & Q(due=False)
            & Q(date_billing_next__lte=date)
        ).exclude(reference__in=payment_references)
        for subscription in due_subscriptions:

            transaction = auto_activate_subscription(subscription, amount=subscription.plan_cost.cost,
                                                     transaction_date=subscription.date_billing_next)
            if transaction.amount <= 0:
                subscription.activate(subscription_date=subscription.date_billing_next)
                subscription.notify_activate(auto=True)
            else:
                crypto = self.get_previous_transaction_crypto(subscription, )
                transaction.create_payment(crypto or "BITCOIN")
                subscription.due = True
                subscription.notify_overdue()
            subscription.save()

    def process_new_subscriptions(self, date):
        UserSubscription.objects.filter(
            Q(active=False) & Q(cancelled=False)
            & Q(date_billing_start__lte=date
                )
        ).exclude(reference__in=payment_references)

    def process_subscriptions(self):
        """Calls all required subscription processing functions."""
        current = timezone.now()

        # Handle expired subscriptions

        self.process_expired_subscriptions(current)
        self.process_one_week_due_subscriptions(current)
        # self.process_new_subscriptions(current)
        # Handle new subscriptions

        # Handle subscriptions with billing due

    def get_previous_transaction_crypto(self, subscription):
        for transaction in subscription.transactions.all():
            # transaction = SubscriptionTransaction.objects.get(pk=transaction.pk)
            for payment in transaction.cryptocurrency_payments.all():
                return payment.crypto
