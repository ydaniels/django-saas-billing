# Create your views here.
import stripe
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.apps import apps
from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework.response import Response
from rest_framework.status import HTTP_201_CREATED, HTTP_400_BAD_REQUEST
from rest_framework.decorators import action
from subscriptions_api.views import PlanCostViewSet, UserSubscriptionViewSet
from saas_billing.models import UserSubscription
from subscriptions_api.serializers import UserSubscriptionSerializer

from cryptocurrency_payment.models import CryptoCurrencyPayment

from saas_billing.serializers import CryptoCurrencyPaymentSerializer, SubscriptionTransactionSerializerPayment
from saas_billing.provider import PayPalClient
from saas_billing.models import StripeCustomer, SubscriptionTransaction, auto_activate_subscription, PaypalSubscription
from saas_billing.app_settings import SETTINGS

auth = SETTINGS['billing_auths']
saas_models = SETTINGS['billing_models']


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
        if subscription.reference:
            # deactivate on gateway
            subscription_model = saas_models[subscription.reference]['subscription']
            Model = apps.get_model(subscription_model)
            obj = Model.objects.get(subscription=subscription)
            res = obj.deactivate()
            if res is True:
                subscription.deactivate()
        else:
            if subscription.unused_daily_balance > 0:
                subscription.record_transaction(amount=-1 * subscription.unused_daily_balance)
            subscription.deactivate()
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

    @action(methods=['post'], url_name='paypal_gateway', detail=False, permission_classes=[AllowAny])
    def paypal_gateway(self, request):
        event_type = request.data['event_type']
        payload = {
            'auth_algo': request.headers['PAYPAL-AUTH-ALGO'],
            'cert_url': request.headers['PAYPAL-CERT-URL'],
            'transmission_id': request.headers['PAYPAL-TRANSMISSION-ID'],
            'transmission_sig': request.headers['PAYPAL-TRANSMISSION-SIG'],
            'transmission_time': request.headers['PAYPAL-TRANSMISSION-TIME'],
            'webhook_id': auth['paypal']['WEB_HOOK_ID'],
            'webhook_event': event_type
        }

        paypal = PayPalClient(auth['paypal']['CLIENT_ID'], auth['paypal']['CLIENT_SECRET'],
                              token=auth['paypal']['TOKEN'],
                              env=auth['paypal']['ENV'])
        req = paypal.verify_webhook(payload)
        if req is True:
            data = request.data["resource"]
            subscription_id = data['id']
            subscription = PaypalSubscription.objects.get(subscription_ref=subscription_id).subscription
            if event_type == 'BILLING.SUBSCRIPTION.ACTIVATED':
                subscription.activate()
                subscription.notify_activate()
            elif event_type == 'BILLING.SUBSCRIPTION.SUSPENDED':
                subscription.deactivate()
                subscription.notify_deactivate()
            elif event_type == 'BILLING.SUBSCRIPTION.CANCELLED' or event_type == 'BILLING.SUBSCRIPTION.DELETED':
                subscription.notify_deactivate()
                subscription.deactivate()
            elif event_type == 'BILLING.SUBSCRIPTION.EXPIRED':
                subscription.deactivate()
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

    def get_local_customer(self, customer):
        stripe_customer = StripeCustomer.objects.get(customer_id=customer)
        return stripe_customer

    @action(methods=['post'], url_name='stripe_gateway', detail=False, permission_classes=[AllowAny])
    def stripe_gateway(self, request):
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
                subscription.activate()
                subscription.notify_new()
            elif subscription_status == 'incomplete':
                subscription.notify_payment_error()
            elif subscription_status == 'incomplete_expired':
                subscription.deactivate()
                subscription.notify_deactivate()
            elif subscription_status == 'past_due' or subscription_status == 'unpaid':
                subscription.notify_due()
            elif subscription_status == 'expired':
                subscription.deactivate()
                subscription.notify_expired()
            elif subscription_status == 'cancelled' or event.type == 'customer.subscription.deleted':
                subscription.deactivate()
                subscription.notify_expired()
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

    @action(methods=['post'], url_name='subscribe_user_crypto', detail=True, permission_classes=[IsAuthenticated])
    def subscribe_user_crypto(self, request, pk=None):
        plan_cost = self.get_object()
        # Get old subscription
        cost = plan_cost.cost
        crypto = self.request.data.get('crypto')
        unpaid_count = CryptoCurrencyPayment.objects.filter(user=self.request.user).exclude(
            status=CryptoCurrencyPayment.PAYMENT_PAID).count()
        if unpaid_count > 0:
            return Response({'detail': 'You cannot subscribe for a new plan if you have unpaid bitcoin transactions'},
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
            subscription.notify_deactivate(activate_new=True)
        subscription = plan_cost.setup_user_subscription(request.user, active=False, no_multipe_subscription=True,
                                                         resuse=True)
        subscription.reference = crypto
        subscription.save()
        transaction = auto_activate_subscription(subscription, amount=cost)
        data = {'subscription': str(subscription.pk), 'transaction': str(transaction.pk), 'payment': None}
        if transaction.amount <= 0:
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
        data = external_cost.setup_subscription(request.user)
        return Response(data)


class CryptoCurrencyPaymentViewset(ReadOnlyModelViewSet):
    serializer_class = CryptoCurrencyPaymentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return CryptoCurrencyPayment.objects.filter(user=self.request.user)
