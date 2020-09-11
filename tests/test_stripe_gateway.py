import pytest
from unittest.mock import patch, PropertyMock
from django.urls import reverse
from django.contrib.auth.models import User
from rest_framework.test import APITestCase
from subscriptions_api.models import PlanCost, SubscriptionPlan

from saas_billing.models import StripeSubscriptionPlan, StripeSubscriptionPlanCost, StripeCustomer, StripeSubscription

@pytest.mark.django_db
class GatewayTest(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user('demo_user', email='test@gmail.com')
        self.client.force_authenticate(self.user)
        self.cost = self.create_plan_cost("Basic Plan", cost=10)
        self.stripe_plan = StripeSubscriptionPlan(plan=self.plan)
        self.stripe_cost = StripeSubscriptionPlanCost(cost=self.cost)

    def create_plan_cost(self, name, cost=9.99):
        self.plan = SubscriptionPlan(plan_name=name)
        self.plan.save()
        cost = PlanCost(cost=cost, plan=self.plan)
        cost.save()
        return cost

    @patch('stripe.api_base', new_callable=PropertyMock(return_value="http://localhost:12111"))
    def test_stripe_subscription_plan(self, api_base):
        res = self.stripe_plan.create_or_update()
        self.plan.refresh_from_db()
        self.stripe_plan.refresh_from_db()
        self.assertEqual(res.id, self.stripe_plan.plan_ref)

    @patch('saas_billing.signals.delete_stripe_subscription_plan_hook')
    @patch('stripe.api_base', new_callable=PropertyMock(return_value="http://localhost:12111"))
    def test_delete_stripe_subscription_plan(self, api_base, signals):
        res = self.stripe_plan.create_or_update()
        self.plan.refresh_from_db()
        self.stripe_plan.refresh_from_db()
        self.assertEqual(res.id, self.stripe_plan.plan_ref)
        self.plan.delete()
        self.assertRaises(StripeSubscriptionPlan.DoesNotExist, self.stripe_plan.refresh_from_db)


    @patch('stripe.api_base', new_callable=PropertyMock(return_value="http://localhost:12111"))
    def test_update_stripe_subscription_plan(self, api_base):
        self.plan.plan_name = 'New Plan Name'
        self.plan.save()
        res = self.stripe_plan.create_or_update()
        self.stripe_plan.save()
        self.plan.refresh_from_db()
        self.assertEqual(res['name'], self.plan.plan_name)

    @patch('stripe.api_base', new_callable=PropertyMock(return_value="http://localhost:12111"))
    def test_stripe_subscription_cost(self, api_base):
        res = self.stripe_cost.create_or_update()
        self.cost.refresh_from_db()
        self.stripe_cost.refresh_from_db()
        self.assertEqual(res.id, self.stripe_cost.cost_ref)
        self.assertEqual('{:.2f}'.format(float(res.unit_amount_decimal)), str(self.stripe_cost.cost.cost * 100))

    @patch('saas_billing.signals.delete_stripe_plan_cost_hook')
    @patch('stripe.api_base', new_callable=PropertyMock(return_value="http://localhost:12111"))
    def test_delete_stripe_subscription_cost(self, api_base, signals):
        self.stripe_plan.create_or_update()
        res = self.stripe_cost.create_or_update()
        self.cost.refresh_from_db()
        self.stripe_cost.refresh_from_db()
        self.assertEqual(res.id, self.stripe_cost.cost_ref)
        self.assertEqual('{:.2f}'.format(float(res.unit_amount_decimal)), str(self.stripe_cost.cost.cost * 100))
        self.cost.delete()
        self.assertRaises(StripeSubscriptionPlanCost.DoesNotExist, self.stripe_cost.refresh_from_db)

    @patch('stripe.api_base', new_callable=PropertyMock(return_value="http://localhost:12111"))
    def test_get_stripe_subscription_link(self, api_base):
        res = self.stripe_cost.create_or_update()
        cost_url = reverse('saas_billing:plan-costs-init_gateway_subscription', kwargs={'pk': self.cost.pk})
        rsp = self.client.post(cost_url, data={'gateway': 'stripe'})
        self.assertEqual(rsp.data['cost_id'], self.stripe_cost.cost_ref)
        self.assertIn('session_id', rsp.data)

    @patch('stripe.api_base', new_callable=PropertyMock(return_value="http://localhost:12111"))
    def test_get_create_stripe_customer(self, api_base):
        self.assertRaises(StripeCustomer.DoesNotExist, StripeCustomer.objects.get, user=self.user)
        customer_id = self.stripe_cost.get_or_creeate_stripe_customer_id(self.user)
        self.assertEqual(self.user.stripe_customer.customer_id,customer_id)

    # @patch('stripe.api_base', new_callable=PropertyMock(return_value="http://localhost:12111"))
    # def test_cancel_stripe_subscription(self, api_base):
    #     subscription = self.cost.setup_user_subscription(self.user)
    #     subscription.reference = 'stripe'
    #     subscription.activate()
    #     subscription.save()
    #     StripeSubscription(subscription_ref='random_sub', subscription=subscription).save()
    #     self.assertTrue(subscription.active)
    #     cost_url = reverse('saas_billing:subscriptions-unsubscribe_user', kwargs={'pk': subscription.pk})
    #     r = self.client.post(cost_url)
    #     self.assertEqual(r.status_code, 200)
    #     subscription.refresh_from_db()
    #     self.assertFalse(subscription.active)
    #     self.assertTrue(subscription.cancelled)