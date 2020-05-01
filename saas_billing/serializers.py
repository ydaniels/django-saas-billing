from rest_framework import serializers

from cryptocurrency_payment.models import CryptoCurrencyPayment
from saas_billing.models import SubscriptionTransaction


class CryptoCurrencyPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = CryptoCurrencyPayment
        fields = '__all__'


class SubscriptionTransactionSerializerPayment(serializers.ModelSerializer):
    """SubscriptionTransaction serializer"""

    cryptocurrency_payments = CryptoCurrencyPaymentSerializer(many=True, read_only=True)
    subscription_name = serializers.SerializerMethodField()

    def get_subscription_name(self, obj):
        if obj.subscription:
            return '{} {}'.format(obj.subscription.plan_cost.plan.plan_name,
                                  obj.subscription.plan_cost.display_billing_frequency_text)
        return ''

    class Meta:
        model = SubscriptionTransaction
        fields = '__all__'
