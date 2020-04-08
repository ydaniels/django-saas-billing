from django.contrib.contenttypes.fields import GenericRelation
from subscriptions import models
from subscriptions_api.models import UserSubscription

from cryptocurrency_payment.models import CryptoCurrencyPayment
from cryptocurrency_payment.models import create_new_payment


class SubscriptionTransaction(models.SubscriptionTransaction):
    cryptocurrency_payments = GenericRelation(CryptoCurrencyPayment)

    class Meta:
        proxy = True

    def create_payment(self, crypto_payment):
        plan_cost = self.subscription

        payment_title = '{} {} {}'.format(plan_cost.recurrence_period, plan_cost.recurrence_unit,
                                          plan_cost.plan.plan_name)
        payment = create_new_payment(crypto_payment, fiat_amount=self.amount, fiat_currency='USD',
                                     payment_title=payment_title,
                                     payment_description=plan_cost.plan.plan_description,
                                     related_object=self, user=self.user)
        return payment


class UserSubscriptionProxy(UserSubscription):
    class Meta:
        proxy = True

    def auto_activate_subscription(self, amount, transaction_date=None):

        if amount > 0:
            # Search if old transaction can pay for new subscription
            # print(SubscriptionTransaction.objects.filter(user=self.request.user, amount__lt=0))
            for prev_transaction in SubscriptionTransaction.objects.filter(user=self.user, amount__lt=0).all():
                print(amount, prev_transaction.amount)
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
        self.SubscriptionTransactionClass = SubscriptionTransaction
        transaction = self.record_transaction(amount=amount, transaction_date=transaction_date)
        return transaction
