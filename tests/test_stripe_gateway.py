import pytest
from unittest.mock import patch, PropertyMock
from rest_framework.test import APITestCase
from subscriptions_api.models import PlanCost, SubscriptionPlan, UserSubscription

from saas_billing.models import StripeSubscriptionPlan, StripeSubscriptionPlanCost

@pytest.mark.django_db
class GatewayTest(APITestCase):

    def setUp(self):
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
        self.stripe_plan.plan_ref = 'prod_FJLPlVXcbLq0Jt5'
        self.stripe_plan.save()
        res = self.stripe_plan.create_or_update()
        self.plan.refresh_from_db()
        self.assertEqual(res['name'], self.plan.plan_name)

    @patch('stripe.api_base', new_callable=PropertyMock(return_value="http://localhost:12111"))
    def test_stripe_subscription_cost(self, api_base):
        res = self.stripe_cost.create_or_update()
        print(res)
        self.cost.refresh_from_db()
        self.stripe_cost.refresh_from_db()
        self.assertEqual(res.id, self.stripe_cost.cost_ref)
        self.assertEqual('{:.2f}'.format(float(res.unit_amount_decimal)), str(self.stripe_cost.cost.cost * 100))

    @patch('saas_billing.signals.delete_stripe_plan_cost_hook')
    @patch('stripe.api_base', new_callable=PropertyMock(return_value="http://localhost:12111"))
    def test_delete_stripe_subscription_cost(self, api_base, signals):
        res = self.stripe_cost.create_or_update()
        self.cost.refresh_from_db()
        self.stripe_cost.refresh_from_db()
        self.assertEqual(res.id, self.stripe_cost.cost_ref)
        self.assertEqual('{:.2f}'.format(float(res.unit_amount_decimal)), str(self.stripe_cost.cost.cost * 100))
        self.cost.delete()
        self.assertRaises(StripeSubscriptionPlanCost.DoesNotExist, self.stripe_cost.refresh_from_db)
