from rest_framework import serializers

from cryptocurrency_payment.models import CryptoCurrencyPayment
from saas_billing.models import SubscriptionTransaction, PaypalSubscription, StripeSubscription


class CryptoCurrencyPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = CryptoCurrencyPayment
        fields = '__all__'


class PaypalSubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaypalSubscription
        fields = '__all__'


class StripeSubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = StripeSubscription
        fields = '__all__'


class SubscriptionTransactionSerializerPayment(serializers.ModelSerializer):
    """SubscriptionTransaction serializer"""

    cryptocurrency_payments = CryptoCurrencyPaymentSerializer(many=True, read_only=True)
    subscription_name = serializers.SerializerMethodField()
    subscription_reference = serializers.SerializerMethodField()
    subscription_reference_obj = serializers.SerializerMethodField()

    def get_subscription_name(self, obj):
        if obj.subscription:
            return '{} {}'.format(obj.subscription.plan_cost.plan.plan_name,
                                  obj.subscription.plan_cost.display_billing_frequency_text)
        return ''

    def get_subscription_reference(self, obj):
        return obj.subscription.reference

    def get_subscription_reference_obj(self, obj):
        if obj.subscription.reference == 'paypal':
            return PaypalSubscriptionSerializer(obj.subscription.paypal_subscription).data
        elif obj.subscription.reference == 'stripe':
            return StripeSubscriptionSerializer(obj.subscription.stripe_subscription).data
        else:
            return {}

    class Meta:
        model = SubscriptionTransaction
        fields = '__all__'
