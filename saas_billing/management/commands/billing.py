from django.core.management.base import BaseCommand, CommandError
from django.apps import AppConfig
from saas_billing.app_settings import SETTINGS
from subscriptions_api.models import SubscriptionPlan, PlanCost
from saas_billing.models import StripeSubscriptionPlan, StripeSubscriptionPlanCost, PaypalSubscriptionPlan, PaypalSubscriptionPlanCost

class Command(BaseCommand):
    help = 'Create and update subscription plans and cost on stripe and paypal'

    billing_models = SETTINGS['billing_models']
    gateways = ['all'] + billing_models.keys()
    model = ['plan', 'cost']
    action = ['activate', 'deactivate']

    def add_arguments(self, parser):
        parser.add_argument('gateway', choices=self.gateways)
        parser.add_argument('--model', choices=self.model)
        parser.add_argument('--action', choices=self.action)

    def create_external_obj(self, model_class, action=None, data=None):
        obj = model_class.objects.get_or_create(**data)
        if action == 'activate':
            obj.activate()
        elif action == 'deactivate':
            obj.deactivate()
        else:
             obj.create_or_update()
             obj.save()

        self.stdout.write(self.style.SUCCESS('Successfully created %s'%obj))

    def run_create(self, model_type_obj, external_model, action, data_type):
        for obj in model_type_obj.objects.all():
            self.create_external_obj(external_model, action=action, data={data_type: obj})

    def get_model_type_obj(self, model_type):
        if model_type == 'cost':
            return PlanCost
        elif model_type == 'plan':
            return SubscriptionPlan
        else:
            return

    def generate_gateway_model(self, gate_model_str, model_type, action):
        model_type_obj = self.get_model_type_obj(model_type)
        gateway_model_obj = AppConfig.get_model(gate_model_str)
        self.run_create(model_type_obj, gateway_model_obj, action, model_type)

    def get_model_type(self, model_type, gateway_model, action):
        if model_type:
            model_str = gateway_model[model_type.upper()]
            self.generate_gateway_model(model_type, model_str, action)
        for model_type, gateway_model in gateway_model.items():
            self.generate_gateway_model(gateway_model, model_type, action)


    def handle(self, *args, **options):
        gateway = options['gateway']
        model_type = options.get('model')
        action = options.get('action')
        if gateway == 'all':
            for billing_model, gateway_model in self.billing_models.items():
                self.get_model_type(model_type, gateway_model, action)
        else:
            gateway_model = self.billing_models[gateway]
            self.get_model_type(model_type, gateway_model, action)




