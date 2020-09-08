import pytest
from unittest.mock import patch, PropertyMock
from rest_framework.test import APITestCase
from subscriptions_api.models import PlanCost, SubscriptionPlan, UserSubscription

from saas_billing.models import PaypalSubscriptionPlan, PaypalSubscriptionPlanCost

@pytest.mark.django_db
class GatewayTest(APITestCase):

    def setUp(self):
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

