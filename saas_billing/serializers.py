from rest_framework import serializers

from cryptocurrency_payment.models import CryptoCurrencyPayment
from saas_billing.models import SubscriptionTransaction


class CryptoCurrencyPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = CryptoCurrencyPayment
        fields = '__all__'


class SubscriptionTransactionSerializerPayment(serializers.ModelSerializer):
    """SubscriptionTransaction serializer"""

    cryptocurrency_payments = CryptoCurrencyPaymentSerializer(many=True)

    class Meta:
        model = SubscriptionTransaction
        fields = '__all__'
