import pytest
from datetime import timedelta
from django.utils import timezone
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from unittest.mock import patch

from django.contrib.auth.models import User
from subscriptions_api.models import PlanCost, SubscriptionPlan, UserSubscription

from saas_billing.models import SubscriptionTransaction
from saas_billing.management.commands.process_subscriptions import Manager
from cryptocurrency_payment.models import CryptoCurrencyPayment


@pytest.mark.django_db
class BaseTest(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user('demo_user')
        self.client.force_authenticate(self.user)
        self.cost = self.create_plan_cost("Basic Plan", cost=10)

    def create_plan_cost(self, name, cost=9.99):
        plan = SubscriptionPlan(plan_name=name)
        plan.save()
        cost = PlanCost(cost=cost, plan=plan)
        cost.save()
        return cost

    def test_error_on_wrong_backend(self):
        pass

    def test_subscription_amount_removed_from_unsed_balance(self):
        basic_cost = self.create_plan_cost("Basic Plan", cost=100)
        subsription_date = timezone.now() - timedelta(days=15)
        subscription = basic_cost.setup_user_subscription(user=self.user, active=True,
                                                          subscription_date=subsription_date)
        self.assertTrue(subscription.active)
        self.assertEqual(subscription.unused_daily_balance, 49.28)
        cost_url = reverse('saas_billing:plan-costs-subscribe_user_crypto', kwargs={'pk': basic_cost.pk})
        self.client.force_authenticate(self.user)
        r = self.client.post(cost_url, data={"crypto": "Bitcoin"})
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        activated_transaction = SubscriptionTransaction.objects.get(pk=r.data['transaction'])
        subscription.refresh_from_db()
        self.assertEqual(float(activated_transaction.amount), 50.72)
        self.assertFalse(subscription.active)

    def test_old_subscription_transaction_created(self):
        pass

    @patch('saas_billing.signals.save_profile')
    def test_leftover_previous_balance_recorded(self, signals):

        basic_cost = self.create_plan_cost("Basic Plan", cost=100)
        subsription_date = timezone.now() - timedelta(days=15)
        subscription = basic_cost.setup_user_subscription(user=self.user, active=True,
                                                          subscription_date=subsription_date)

        cost_url = reverse('saas_billing:plan-costs-subscribe_user_crypto', kwargs={'pk': self.cost.pk})
        self.client.force_authenticate(self.user)
        r = self.client.post(cost_url, data={"crypto": "Bitcoin"})
        activated_transaction = SubscriptionTransaction.objects.get(pk=r.data['transaction'])
        subscription.refresh_from_db()
        self.assertEqual(float(activated_transaction.amount), 0)
        sub = UserSubscription.objects.get(user=self.user, active=True)
        self.assertNotEqual(sub.pk, subscription.pk)
        transact = subscription.transactions.all()
        self.assertEqual(float(transact[0].amount), -39.28)

    def test_cannot_create_new_subscription_with_unpaid_transaction(self):
        basic_cost = self.create_plan_cost("Basic Plan", cost=50)
        cost_url = reverse('saas_billing:plan-costs-subscribe_user_crypto', kwargs={'pk': basic_cost.pk})
        r = self.client.post(cost_url, data={"crypto": "Bitcoin"})
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        r = self.client.post(cost_url, data={"crypto": "Bitcoin"})
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_subscription_amount_deducted_from_past_neg_transaction(self):
        cost = self.create_plan_cost("Basic Plan", cost=0)
        # Create a subscription cost with 0
        subscription = cost.setup_user_subscription(self.user)
        transaction = SubscriptionTransaction.objects.create(subscription=subscription, amount=-10,
                                                             user=self.user, date_transaction=timezone.now())
        basic_cost = self.create_plan_cost("Basic Plan", cost=6)
        cost_url = reverse('saas_billing:plan-costs-subscribe_user_crypto', kwargs={'pk': basic_cost.pk})

        r = self.client.post(cost_url, data={"crypto": "Bitcoin"})

        UserSubscription.objects.get(pk=r.data['subscription']).deactivate()
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        active_transaction = SubscriptionTransaction.objects.get(pk=r.data['transaction'])
        transaction.refresh_from_db()
        self.assertEqual(float(transaction.amount), -4)
        self.assertEqual(active_transaction.amount, 0)
        CryptoCurrencyPayment.objects.filter(user=self.user).update(status=CryptoCurrencyPayment.PAYMENT_PAID)
        cost_url = reverse('saas_billing:plan-costs-subscribe_user_crypto', kwargs={'pk': basic_cost.pk})
        self.client.force_authenticate(self.user)
        r = self.client.post(cost_url, data={"crypto": "Bitcoin"})

        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        active_transaction = SubscriptionTransaction.objects.get(pk=r.data['transaction'])
        transaction.refresh_from_db()
        self.assertEqual(float(transaction.amount), 0)
        self.assertEqual(active_transaction.amount, 2)

    @patch('saas_billing.signals.save_profile')
    def test_subcription_activated_when_all_payment_paid(self, signal):
        basic_cost = self.create_plan_cost("Basic Plan", cost=50)
        cost_url = reverse('saas_billing:plan-costs-subscribe_user_crypto', kwargs={'pk': basic_cost.pk})
        r = self.client.post(cost_url, data={"crypto": "Bitcoin"})
        active_transaction = SubscriptionTransaction.objects.get(pk=r.data['transaction'])
        sub = active_transaction.subscription
        self.assertFalse(sub.active)
        self.assertEqual(active_transaction.amount, 50)
        for pay in active_transaction.cryptocurrency_payments.all():
            pay.status = CryptoCurrencyPayment.PAYMENT_PAID
            pay.save()
        sub.refresh_from_db()
        self.assertTrue(sub.active)

    def test_create_subscription_without_payment(self):
        basic_cost = self.create_plan_cost("Basic Plan", cost=50)
        cost_url = reverse('saas_billing:plan-costs-subscribe_user_crypto', kwargs={'pk': basic_cost.pk})
        r = self.client.post(cost_url, data={})
        self.assertIsNone(r.data['payment'])
        transaction = SubscriptionTransaction.objects.get(pk=r.data['transaction'])
        self.assertEqual(transaction.cryptocurrency_payments.count(), 0)
        transact_url = reverse('saas_billing:transactions-create_crypto_payment', kwargs={'pk': transaction.pk})

        r = self.client.post(transact_url, data={'crypto': 'Bitcoin'})
        transaction.refresh_from_db()
        self.assertEqual(str(transaction.cryptocurrency_payments.all()[0].id), r.data['id'])

    @patch('saas_billing.signals.save_profile')
    def test_subscription_activated_with_future_transact_date(self, signal):
        basic_cost = self.create_plan_cost("Basic Plan", cost=50)
        cost_url = reverse('saas_billing:plan-costs-subscribe_user_crypto', kwargs={'pk': basic_cost.pk})
        r = self.client.post(cost_url, data={"crypto": "Bitcoin"})
        active_transaction = SubscriptionTransaction.objects.get(pk=r.data['transaction'])
        sub = active_transaction.subscription
        self.assertFalse(sub.active)
        self.assertEqual(active_transaction.amount, 50)
        future_date = timezone.now() + timedelta(days=15)
        active_transaction.date_transaction = future_date
        active_transaction.save()
        for pay in active_transaction.cryptocurrency_payments.all():
            pay.status = CryptoCurrencyPayment.PAYMENT_PAID
            pay.save()
        sub.refresh_from_db()
        self.assertEqual(sub.date_billing_start, future_date)
        self.assertTrue(sub.active)

    @patch('saas_billing.signals.save_profile')
    def test_subscription_payment_notification_generated(self, signal):
        basic_cost = self.create_plan_cost("Basic Plan", cost=50)
        cost_url = reverse('saas_billing:plan-costs-subscribe_user_crypto', kwargs={'pk': basic_cost.pk})
        r = self.client.post(cost_url, data={"crypto": "Bitcoin"})
        active_transaction = SubscriptionTransaction.objects.get(pk=r.data['transaction'])
        sub = active_transaction.subscription
        self.assertFalse(sub.active)
        self.assertEqual(active_transaction.amount, 50)
        for pay in active_transaction.cryptocurrency_payments.all():
            pay.status = CryptoCurrencyPayment.PAYMENT_CANCELLED
            pay.save()
            pay.status = CryptoCurrencyPayment.PAYMENT_PROCESSING
            pay.save()
        sub.refresh_from_db()
        self.assertFalse(sub.active)

    def test_get_transaction_payments(self):
        basic_cost = self.create_plan_cost("Basic Plan", cost=50)
        cost_url = reverse('saas_billing:plan-costs-subscribe_user_crypto', kwargs={'pk': basic_cost.pk})
        r = self.client.post(cost_url, data={"crypto": "Bitcoin"})
        transact_url = reverse('saas_billing:transactions-detail', kwargs={'pk': r.data['transaction']})
        r = self.client.get(transact_url)
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(len(r.data['cryptocurrency_payments']), 1)

    def test_expired_subscription_deactivated_get_activated(self):
        basic_cost = self.create_plan_cost("Basic Plan", cost=100)
        subscription = basic_cost.setup_user_subscription(user=self.user, active=True)
        sub_url = reverse('saas_billing:subscriptions-get_active_subscription')
        r = self.client.get(sub_url)
        self.assertEqual(r.data['id'], str(subscription.pk))
        sub_url = reverse('saas_billing:subscriptions-unsubscribe_user', kwargs={'pk': subscription.pk})
        r = self.client.post(sub_url)
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        subscription.refresh_from_db()
        self.assertFalse(subscription.active)
        sub_url = reverse('saas_billing:subscriptions-get_active_subscription')
        r = self.client.get(sub_url)
        self.assertIsNone(r.data)
        transaction = subscription.transactions.all()[0]
        self.assertEqual(float(transaction.amount), -98.56)

    def test_transaction_generated_for_expired_sub(self):
        basic_cost = self.create_plan_cost("Basic Plan", cost=100)
        subsription_date = timezone.now() - timedelta(days=31)
        subscription = basic_cost.setup_user_subscription(user=self.user, active=True,
                                                          subscription_date=subsription_date)
        self.assertTrue(subscription.active)
        manager = Manager()
        manager.process_expired_subscriptions(timezone.now())
        subscription.refresh_from_db()
        self.assertFalse(subscription.active)

    def test_transaction_generated_for_due_sub(self):
        basic_cost = self.create_plan_cost("Basic Plan", cost=100)
        subsription_date = timezone.now() - timedelta(days=24)
        subscription = basic_cost.setup_user_subscription(user=self.user, active=True,
                                                          subscription_date=subsription_date)
        self.assertTrue(subscription.active)
        manager = Manager()
        manager.process_one_week_due_subscriptions(timezone.now())

        subscription.refresh_from_db()
        self.assertTrue(subscription.active)
        self.assertTrue(subscription.due)
        transaction = subscription.transactions.all()[0]
        self.assertEqual(float(transaction.amount), 100)
        self.assertEqual(transaction.date_transaction, subscription.date_billing_next)

    def test_user_can_subscribe_to_plan_cost(self):
        pass
