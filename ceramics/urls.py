from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .views import (
    GlazeColorViewSet, BodyTypeViewSet, KilnBatchViewSet,
    TemperatureZoneViewSet, ResponsiblePersonViewSet,
    FiringRecordViewSet,
    high_risk_glaze_ranking, pending_retest_tasks, zone_anomaly_distribution,
)

router = DefaultRouter()
router.register(r'glaze-colors', GlazeColorViewSet)
router.register(r'body-types', BodyTypeViewSet)
router.register(r'kiln-batches', KilnBatchViewSet)
router.register(r'temperature-zones', TemperatureZoneViewSet)
router.register(r'responsible-persons', ResponsiblePersonViewSet)
router.register(r'firing-records', FiringRecordViewSet)

urlpatterns = [
    path('api/', include(router.urls)),
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/stats/high-risk-glaze/', high_risk_glaze_ranking, name='high_risk_glaze'),
    path('api/stats/pending-retest/', pending_retest_tasks, name='pending_retest'),
    path('api/stats/zone-anomaly/', zone_anomaly_distribution, name='zone_anomaly'),
]
