import pytest
from unittest.mock import patch, PropertyMock
from django.urls import reverse
from django.contrib.auth.models import User
from rest_framework.test import APITestCase
from subscriptions_api.models import PlanCost, SubscriptionPlan, UserSubscription

from saas_billing.models import PaypalSubscriptionPlan, PaypalSubscriptionPlanCost, PaypalSubscription

@pytest.mark.django_db
class GatewayTest(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user('demo_user', email='test@gmail.com')
        self.client.force_authenticate(self.user)
        self.cost = self.create_plan_cost("Paypal Basic Plan", cost=10)
        self.paypal_plan = PaypalSubscriptionPlan(plan=self.plan)
        self.paypal_cost = PaypalSubscriptionPlanCost(cost=self.cost)

    def create_plan_cost(self, name, cost=9.99):
        self.plan = SubscriptionPlan(plan_name=name)
        self.plan.save()
        cost = PlanCost(cost=cost, plan=self.plan)
        cost.save()
        return cost

    def test_paypal_subscription_plan(self):
        res = self.paypal_plan.create_or_update()
        self.plan.refresh_from_db()
        self.paypal_plan.refresh_from_db()
        self.assertEqual(res['id'], self.paypal_plan.plan_ref)

    def test_paypal_subscription_plan_cost(self):
        self.paypal_plan.create_or_update()
        self.plan.trial_period = 7
        self.plan.save()
        res = self.paypal_cost.create_or_update()
        self.cost.refresh_from_db()
        self.assertEqual(res['id'], self.paypal_cost.cost_ref)
        self.cost.cost = 9.99
        self.cost.save()
        self.paypal_cost.create_or_update()

    def test_plan_cost_deactivate_activate(self):
        self.paypal_plan.create_or_update()
        self.paypal_cost.create_or_update()
        res = self.paypal_cost.deactivate()
        res = self.paypal_cost.activate()

    def test_delete_plan_cost(self):
        self.paypal_plan.create_or_update()
        res = self.paypal_cost.create_or_update()
        self.cost.refresh_from_db()
        self.assertEqual(res['id'], self.paypal_cost.cost_ref)
        self.cost.delete()
        self.assertRaises(PaypalSubscriptionPlanCost.DoesNotExist, self.paypal_cost.refresh_from_db)

    def test_get_paypal_subscription_link(self):
        self.paypal_plan.create_or_update()
        res = self.paypal_cost.create_or_update()
        cost_url = reverse('saas_billing:plan-costs-init_gateway_subscription', kwargs={'pk': self.cost.pk})
        rsp = self.client.post(cost_url, data={'gateway': 'paypal'})
        self.assertEqual(rsp.data['cost_id'], self.paypal_cost.cost_ref)
        self.assertIn('payment_link', rsp.data)

    # @patch('stripe.api_base', new_callable=PropertyMock(return_value="http://localhost:12111"))
    # def test_cancel_stripe_subscription(self, api_base):
    #     self.paypal_plan.create_or_update()
    #     res = self.paypal_cost.create_or_update()
    #     res = self.paypal_cost.setup_subscription(self.user)
    #     print(res)
    #     print('000000000000000000000')
    #     subscription = UserSubscription.objects.get(pk=str(res['id']))
    #     self.assertEqual(subscription.reference, 'paypal')
    #     subscription.activate()
    #     subscription.refresh_from_db()
    #     self.assertTrue(subscription.active)
    #     subscription.paypal_subscription.deactivate()
    #
    #     cost_url = reverse('saas_billing:subscriptions-unsubscribe_user', kwargs={'pk': subscription.pk})
    #     r = self.client.post(cost_url)
    #     self.assertEqual(r.status_code, 200)
    #     subscription.refresh_from_db()
    #     self.assertFalse(subscription.active)
    #     self.assertTrue(subscription.cancelled)