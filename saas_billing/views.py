# Create your views here.
import stripe
import logging
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.apps import apps
from rest_framework.views import APIView
from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework.response import Response
from rest_framework.status import HTTP_201_CREATED, HTTP_400_BAD_REQUEST
from rest_framework.decorators import action
from subscriptions_api.views import PlanCostViewSet, UserSubscriptionViewSet
from subscriptions_api.models import SubscriptionPromo
from saas_billing.models import UserSubscription, PlanCost
from subscriptions_api.serializers import UserSubscriptionSerializer
from cryptocurrency_payment.models import CryptoCurrencyPayment

from saas_billing.serializers import CryptoCurrencyPaymentSerializer, SubscriptionTransactionSerializerPayment
from saas_billing.provider import PayPalClient
from saas_billing.models import StripeCustomer, SubscriptionTransaction, auto_activate_subscription, PaypalSubscription
from saas_billing.app_settings import SETTINGS

auth = SETTINGS['billing_auths']
saas_models = SETTINGS['billing_models']
saas_billing_settings = SETTINGS['saas_billing_settings']

_logger = logging.getLogger(__name__)

class SubscriptionTransactionPaymentViewSet(ReadOnlyModelViewSet):
    serializer_class = SubscriptionTransactionSerializerPayment
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_staff:
            return SubscriptionTransaction.objects.all()
        return SubscriptionTransaction.objects.filter(user=self.request.user)

    @action(methods=['post'], url_name='create_crypto_payment', detail=True, permission_classes=[IsAuthenticated])
    def create_crypto_payment(self, request, pk=None):
        crypto = self.request.data.get('crypto') or 'BITCOIN'
        transaction = self.get_object()
        payment = transaction.create_payment(crypto.upper())
        serialized_payment = CryptoCurrencyPaymentSerializer(payment)
        data = serialized_payment.data
        return Response(data, status=HTTP_201_CREATED)


class UserSubscriptionCrypto(UserSubscriptionViewSet):
    @action(methods=['post'], url_name='unsubscribe_user', detail=True, permission_classes=[IsAuthenticated])
    def unsubscribe_user(self, request, pk=None):
        subscription = self.get_object()
        if subscription.reference and subscription.reference in saas_models:
            # deactivate on gateway
            subscription_model = saas_models[subscription.reference]['subscription']
            Model = apps.get_model(subscription_model)
            obj = Model.objects.get(subscription=subscription)
            res = obj.deactivate()
            if res is True:
                subscription.deactivate(activate_default=True)
        else:
            subscription.deactivate(activate_default=True)
            subscription.notify_deactivate()
        return Response({'status': True})

    @action(methods=['get'], url_name='get_active_subscription', detail=False, permission_classes=[IsAuthenticated])
    def get_active_subscription(self, request):
        try:
            subscription = UserSubscription.objects.get(active=True, user=request.user)
            data = UserSubscriptionSerializer(subscription).data
        except UserSubscription.DoesNotExist:
            data = None
        return Response(data)

    @action(methods=['get'], url_name='get_active_subscriptions', detail=False, permission_classes=[IsAuthenticated])
    def get_active_subscriptions(self, request):
        return Response(UserSubscriptionSerializer(self.request.user.subscriptions.all(), many=True).data)


class PaypalWebHook(APIView):
    
    def paypal_gateway(self, request):
        event_type = request.data['event_type']
        payload = {
            'auth_algo': request.headers['PAYPAL-AUTH-ALGO'],
            'cert_url': request.headers['PAYPAL-CERT-URL'],
            'transmission_id': request.headers['PAYPAL-TRANSMISSION-ID'],
            'transmission_sig': request.headers['PAYPAL-TRANSMISSION-SIG'],
            'transmission_time': request.headers['PAYPAL-TRANSMISSION-TIME'],
            'webhook_id': auth['paypal']['WEB_HOOK_ID'],
            'webhook_event': request.data
        }

        paypal = PayPalClient(auth['paypal']['CLIENT_ID'], auth['paypal']['CLIENT_SECRET'],
                              token=auth['paypal']['TOKEN'],
                              env=auth['paypal']['ENV'])
        req = paypal.verify_webhook(payload)
        if req is True:
            data = request.data["resource"]
            subscription_id = data['id']
            try:
                subscription = PaypalSubscription.objects.get(subscription_ref=subscription_id).subscription
            except PaypalSubscription.DoesNotExist:
                _logger.error("Got webhook payload for subscription but cannot find obj ")
                _logger.error(data)
                return Response({})
            if event_type == 'BILLING.SUBSCRIPTION.ACTIVATED':
                subscription.activate(no_multiple_subscription=saas_billing_settings['NO_MULTIPLE_SUBSCRIPTION'])
                subscription.record_transaction(paid=True)
                subscription.notify_activate()
            elif event_type == 'BILLING.SUBSCRIPTION.SUSPENDED':
                subscription.deactivate(activate_default=True)
                subscription.notify_deactivate()
            elif event_type == 'BILLING.SUBSCRIPTION.CANCELLED':
                #subscription.notify_deactivate()#Dont deactivate subscription if subscription is cancelled
                pass
            elif event_type == 'BILLING.SUBSCRIPTION.DELETED':
                subscription.notify_deactivate()
                subscription.deactivate(activate_default=True)
            elif event_type == 'BILLING.SUBSCRIPTION.EXPIRED':
                subscription.deactivate(activate_default=True)
                subscription.notify_expired()
            elif event_type == 'BILLING.SUBSCRIPTION.PAYMENT.FAILED':
                subscription.notify_payment_error()
            elif event_type == 'BILLING.SUBSCRIPTION.RE-ACTIVATED':
                pass
            elif event_type == 'BILLING.SUBSCRIPTION.RENEWED':
                pass
            elif event_type == 'BILLING.SUBSCRIPTION.UPDATED':
                pass
            else:
                pass
            return Response({})

        
        
class StripeWebHook(APIView):

    def get_local_customer(self, customer):
        stripe_customer = StripeCustomer.objects.get(customer_id=customer)
        return stripe_customer


    def post(self, request):
        payload = request.data
        try:
            event = stripe.Event.construct_from(
                payload, auth['stripe']['LIVE_KEY']
            )
        except ValueError:
            # Invalid payload
            return Response(status=HTTP_400_BAD_REQUEST)

            # Handle the event
        data = event.data.object
        if 'customer.subscription' in event.type:
            customer = data.customer
            stripe_costomer = self.get_local_customer(customer=customer)
            subscription = stripe_costomer.get_or_create_subscription(data)
            subscription_status = data['status']

            if subscription_status == 'active' or subscription_status == 'trialing':
                subscription.record_transaction(paid=True)
                subscription.activate(no_multiple_subscription=saas_billing_settings['NO_MULTIPLE_SUBSCRIPTION'])
            elif subscription_status == 'incomplete':
                subscription.notify_payment_error()
            elif subscription_status == 'trial_will_end':
                subscription.notify_due()
            elif subscription_status == 'incomplete_expired':
                subscription.deactivate(activate_default=True)
                subscription.notify_deactivate()
            elif subscription_status == 'past_due' or subscription_status == 'unpaid':
                subscription.notify_due()
            elif subscription_status == 'expired':
                subscription.deactivate(activate_default=True)
                subscription.notify_expired()
            elif subscription_status == 'canceled':
                #subscription.notify_deactivate()
                pass
            elif event.type == 'customer.subscription.deleted':
                subscription.deactivate(activate_default=True)
                subscription.notify_deactivate()
        # elif 'invoice' in event.type:
        #     invoice = event.data.object  # contains a stripe.PaymentMethod
        #     stripe_costomer = self.get_local_customer(customer=invoice.customer)
        #     subscription = stripe_costomer.get_or_create_subscription(request.user, invoice)
        #     if event.type == 'invoice.paid':
        #         subscription.notify_payment_success()
        #     elif event.type == 'invoice.created':
        #         subscription.notify_new()
        #     elif event.type == 'invoice.upcoming':
        #         subscription.notify_due()
        #     elif event.type == 'invoice.payment_failed':
        #         subscription.notify_payment_error()
        else:
            return Response(status=HTTP_400_BAD_REQUEST)

        return Response({})


class PlanCostCryptoUserSubscriptionView(PlanCostViewSet):

    def calculate_discount(self, amount):
        code = self.request.data.get('promo_code')
        if not code:
            return amount
        promo_obj = SubscriptionPromo.objects.filter(code=code, customer=self.request.user, active=True).first()
        if not promo_obj:
            promo_obj = SubscriptionPromo.objects.exclude(customer__isnull=False).filter(code=code, active=True).first()
        if not promo_obj:
            return amount
        if promo_obj.expires_at and promo_obj.expires_at < timezone.now():
            return amount #promo as expire
        bal =  amount - promo_obj.calculate_discount(amount)
        if bal < 0:
            bal = 0
        return bal

    def get_extra_costs(self):
        extra_cost_ids = self.request.data.get('extra_costs', [])
        costs = PlanCost.objects.filter(id__in=extra_cost_ids).all()
        return costs

    def get_extra_costs_sum(self):
        extra_costs = self.get_extra_costs()
        total_extra_costs = sum([cost.cost for cost in extra_costs if cost != self.get_object()])
        return total_extra_costs

    @action(methods=['post'], url_name='subscribe_user_crypto', detail=True, permission_classes=[IsAuthenticated])
    def subscribe_user_crypto(self, request, pk=None):
        plan_cost = self.get_object()
        # Get old subscription
        qty = request.data.get('quantity', 1)
        if qty < plan_cost.min_subscription_quantity:
            return Response({'detail': 'Quantity must not be less than {} to subscribe to this plan'.format(plan_cost.min_subscription_quantity)},
                            status=HTTP_400_BAD_REQUEST)

        cost = (plan_cost.cost + self.get_extra_costs_sum()) * qty
        cost = self.calculate_discount(cost)
        crypto = self.request.data.get('crypto')
        unpaid_count = CryptoCurrencyPayment.objects.filter(user=self.request.user).exclude(
            status=CryptoCurrencyPayment.PAYMENT_PAID).count()
        if unpaid_count > 0:
            return Response({'detail': 'You cannot subscribe for a new plan if you have unpaid bitcoin transactions.'},
                            status=HTTP_400_BAD_REQUEST)
        active_subscriptions = UserSubscription.objects.filter(user=request.user, active=True).all()
        for subscription in active_subscriptions:
            unused_balance = subscription.unused_daily_balance
            if unused_balance > 0:
                cost = float(cost) - unused_balance
                if cost == 0 or cost > 0:
                    subscription.deactivate()
                else:
                    subscription.deactivate()

                    subscription.record_transaction(amount=cost)
                    cost = 0

            else:
                subscription.deactivate()
            subscription.notify_deactivate()
        subscription = plan_cost.setup_user_subscription(request.user, active=False,
                                                         no_multiple_subscription=saas_billing_settings['NO_MULTIPLE_SUBSCRIPTION'],
                                                         resuse=True, extra_costs=self.get_extra_costs())
        subscription.quantity = qty
        subscription.reference = crypto
        subscription.save()
        transaction = auto_activate_subscription(subscription, amount=cost)
        data = {'subscription': str(subscription.pk), 'transaction': str(transaction.pk), 'payment': None}
        if transaction.amount <= 0 or cost == 0:
            subscription.activate()
            subscription.notify_activate()
        if crypto:
            payment = transaction.create_payment(crypto.upper())
            serialized_payment = CryptoCurrencyPaymentSerializer(payment)
            data['payment'] = serialized_payment.data['id']
        return Response(data, status=HTTP_201_CREATED)

    @action(methods=['post'], url_name='init_gateway_subscription', detail=True, permission_classes=[IsAuthenticated])
    def init_gateway_subscription(self, request, pk=None):
        cost = self.get_object()
        gateway = self.request.data['gateway']
        cost_model_str = SETTINGS['billing_models'][gateway]['cost']
        Model = apps.get_model(cost_model_str)
        external_cost = Model.objects.get(cost=cost)
        qty = request.data.get('quantity', 1)

        if qty <  cost.min_subscription_quantity:
            return Response({'detail': 'Quantity must not be less than {} to subscribe to this plan'.format(cost.min_subscription_quantity)},
                            status=HTTP_400_BAD_REQUEST)
        data = external_cost.setup_subscription(request.user, qty, extra_costs=self.get_extra_costs())
        return Response(data)


class CryptoCurrencyPaymentViewset(ReadOnlyModelViewSet):
    serializer_class = CryptoCurrencyPaymentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return CryptoCurrencyPayment.objects.filter(user=self.request.user)
