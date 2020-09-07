# Create your views here.
from rest_framework.permissions import IsAuthenticated
from django.apps import AppConfig
from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework.response import Response
from rest_framework.status import HTTP_201_CREATED, HTTP_400_BAD_REQUEST
from rest_framework.decorators import action
from subscriptions_api.views import PlanCostViewSet, UserSubscriptionViewSet
from subscriptions_api.models import UserSubscription
from subscriptions_api.serializers import UserSubscriptionSerializer

from cryptocurrency_payment.models import CryptoCurrencyPayment

from saas_billing.serializers import CryptoCurrencyPaymentSerializer, SubscriptionTransactionSerializerPayment
from saas_billing.app_settings import SETTINGS
from saas_billing.models import SubscriptionTransaction, auto_activate_subscription


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


class PlanCostCryptoUserSubscriptionView(PlanCostViewSet):

    @action(methods=['post'], url_name='subscribe_user_crypto', detail=True, permission_classes=[IsAuthenticated])
    def subscribe_user_crypto(self, request, pk=None):
        plan_cost = self.get_object()
        # Get old subscription
        cost = plan_cost.cost
        crypto = self.request.data.get('crypto')
        unpaid_count = CryptoCurrencyPayment.objects.filter(user=self.request.user).exclude(status=CryptoCurrencyPayment.PAYMENT_PAID).count()
        if unpaid_count > 0:
            return Response({'detail': 'You cannot subscribe for a new plan if you have unpaid bitcoin transactions'}, status=HTTP_400_BAD_REQUEST)
        active_subscriptions = UserSubscription.objects.filter(user=request.user, active=True).all()
        for subscription in active_subscriptions:
            unused_balance = subscription.unused_daily_balance
            if unused_balance > 0:
                cost = float(cost) - unused_balance
                print(cost, '0p')
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

    @action(methods=['get'], url_name='get_gateway_cost', detail=True, permission_classes=[IsAuthenticated])
    def get_gateway_cost(self):
        cost = self.get_object()
        gateway = self.request.data.get('gateway')
        cost_model_str = SETTINGS['billing_models'][gateway]['COST']
        Model = AppConfig.get_model(cost_model_str)
        external_cost = Model.objects.get(cost=cost)
        return Response({'id': external_cost.cost_ref})

class CryptoCurrencyPaymentViewset(ReadOnlyModelViewSet):
    serializer_class = CryptoCurrencyPaymentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return CryptoCurrencyPayment.objects.filter(user=self.request.user)
