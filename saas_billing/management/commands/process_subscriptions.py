"""Utility/helper functions for Django Flexible Subscriptions."""
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta
from subscriptions_api import models

from saas_billing.models import UserSubscriptionProxy, SubscriptionTransaction


class Manager():
    """Manager object to help manage subscriptions & billing."""

    def process_expired_subscriptions(self, date):
        expired_subscriptions = models.UserSubscription.objects.filter(
            Q(active=True) & Q(cancelled=False)
            & Q(date_billing_end__lte=date)
        )

        for subscription in expired_subscriptions:
            print(subscription.date_billing_end)
            subscription.deactivate()
            subscription.notify_expired()

    def process_one_week_due_subscriptions(self, date):
        date = date + timedelta(days=7)
        due_subscriptions = UserSubscriptionProxy.objects.filter(
            Q(active=True) & Q(cancelled=False)
            & Q(date_billing_next__lte=date)
        )
        for subscription in due_subscriptions:

            transaction = subscription.auto_activate_subscription(amount=subscription.subscription.cost,
                                                                  transaction_date=subscription.date_billing_next)
            if transaction.amount <= 0:
                subscription.activate(subscription_date=subscription.date_billing_next)
                subscription.notify_new()
            else:
                crypto = self.get_previous_transaction_crypto(subscription, )
                transaction.create_payment(crypto or "BITCOIN")
                subscription.cancelled = True
                subscription.notify_overdue()
            subscription.save()

    def process_new_subscriptions(self, date):
        models.UserSubscription.objects.filter(
            Q(active=False) & Q(cancelled=False)
            & Q(date_billing_start__lte=date
                )
        )

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
        for transaction in SubscriptionTransaction.objects.filter(subscription=subscription.subscription,
                                                                  user=subscription.user).all():
            for payment in transaction.cryptocurrency_payments.all():
                return payment.crypto
