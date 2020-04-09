# Create your views here.
from rest_framework.permissions import IsAuthenticated

from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework.response import Response
from rest_framework.status import HTTP_201_CREATED
from rest_framework.decorators import action
from subscriptions_api.views import PlanCostViewSet, UserSubscriptionViewSet
from subscriptions_api.models import UserSubscription
from subscriptions_api.serializers import UserSubscriptionSerializer

from cryptocurrency_payment.models import CryptoCurrencyPayment

from .serializers import CryptoCurrencyPaymentSerializer, SubscriptionTransactionSerializerPayment

from .models import SubscriptionTransaction, UserSubscriptionProxy


class SubscriptionTransactionPaymentViewSet(ReadOnlyModelViewSet):
    serializer_class = SubscriptionTransactionSerializerPayment
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_staff:
            return SubscriptionTransaction.objects.all()
        return SubscriptionTransaction.objects.filter(user=self.request.user)


class UserSubscriptionCrypto(UserSubscriptionViewSet):
    @action(methods=['post'], url_name='unsubscribe_user_crypto', detail=True, permission_classes=[IsAuthenticated])
    def unsubscribe_user_crypto(self, request, pk=None):
        subscription = self.get_object()
        print(subscription.unused_daily_balance)
        if subscription.unused_daily_balance > 0:
            subscription.record_transaction(amount=-1 * subscription.unused_daily_balance)
        subscription.deactivate()
        return Response({'status': True})

    @action(methods=['get'], url_name='get_active_subscription', detail=False, permission_classes=[IsAuthenticated])
    def get_active_subscription(self, request):
        try:
            subscription = UserSubscription.objects.get(user=self.request.user, active=True)
        except UserSubscription.DoesNotExist:
            return Response({'subscription': None})
        return Response({'subscription': UserSubscriptionSerializer(subscription).data})


class PlanCostCryptoUserSubscriptionView(PlanCostViewSet):

    @action(methods=['post'], url_name='subscribe_user_crypto', detail=True, permission_classes=[IsAuthenticated])
    def subscribe_user_crypto(self, request, pk=None):
        plan_cost = self.get_object()
        # Get old subscription
        cost = plan_cost.cost
        crypto = self.request.data['crypto'].upper()
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
        plan_cost.UserSubscriptionClass = UserSubscriptionProxy
        subscription = plan_cost.setup_user_subscription(request.user, active=False, no_multipe_subscription=True, resuse=True)
        transaction = subscription.auto_activate_subscription(amount=cost)
        if transaction.amount <= 0:
            subscription.activate()
            data = {'subscription': str(subscription.pk), 'object_id': str(transaction.pk)}
        else:
            payment = transaction.create_payment(crypto)
            serialized_payment = CryptoCurrencyPaymentSerializer(payment)
            data = serialized_payment.data
            data['subscription'] = None
        return Response(data, status=HTTP_201_CREATED)


class CryptoCurrencyPaymentViewset(ReadOnlyModelViewSet):
    serializer_class = CryptoCurrencyPaymentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return CryptoCurrencyPayment.objects.filter(user=self.request.user)
