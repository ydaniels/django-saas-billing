from django.urls import path, include

app_name = 'saas_billing'

urlpatterns = [
    path('', include('saas_billing.urls')),
]
