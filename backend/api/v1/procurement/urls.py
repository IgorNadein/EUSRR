"""
URL конфигурация для API модуля закупок.
"""

from rest_framework.routers import DefaultRouter

from .views import (
    BudgetViewSet,
    EquipmentCategoryViewSet,
    EquipmentViewSet,
    MaintenanceRecordViewSet,
    ProcurementItemViewSet,
    ProcurementRequestViewSet,
    ProcurementStatsViewSet,
    SupplierViewSet,
)

app_name = 'procurement'

router = DefaultRouter()
router.register(
    r'requests',
    ProcurementRequestViewSet,
    basename='procurementrequest'
)
router.register(
    r'items',
    ProcurementItemViewSet,
    basename='procurementitem'
)
router.register(
    r'equipment-categories',
    EquipmentCategoryViewSet,
    basename='equipmentcategory'
)
router.register(
    r'equipment',
    EquipmentViewSet,
    basename='equipment'
)
router.register(
    r'maintenance',
    MaintenanceRecordViewSet,
    basename='maintenancerecord'
)
router.register(
    r'budgets',
    BudgetViewSet,
    basename='budget'
)
router.register(
    r'suppliers',
    SupplierViewSet,
    basename='supplier'
)
router.register(
    r'stats',
    ProcurementStatsViewSet,
    basename='stats'
)

urlpatterns = router.urls
