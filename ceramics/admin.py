from django.contrib import admin
from .models import (
    GlazeColor, BodyType, KilnBatch, TemperatureZone,
    ResponsiblePerson, FiringRecord, RectificationOrder,
    RectificationHistory,
)


class RectificationHistoryInline(admin.TabularInline):
    model = RectificationHistory
    extra = 0
    readonly_fields = ['action', 'action_display', 'operator_name', 'description',
                       'previous_status', 'current_status', 'created_at']
    can_delete = False


@admin.register(GlazeColor)
class GlazeColorAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'retest_cycle_days']
    search_fields = ['code', 'name']
    list_filter = ['retest_cycle_days']


@admin.register(BodyType)
class BodyTypeAdmin(admin.ModelAdmin):
    list_display = ['code', 'name']
    search_fields = ['code', 'name']


@admin.register(KilnBatch)
class KilnBatchAdmin(admin.ModelAdmin):
    list_display = ['batch_code', 'firing_date']
    search_fields = ['batch_code']
    list_filter = ['firing_date']
    date_hierarchy = 'firing_date'


@admin.register(TemperatureZone)
class TemperatureZoneAdmin(admin.ModelAdmin):
    list_display = ['zone_code', 'name', 'temperature_range']
    search_fields = ['zone_code', 'name']


@admin.register(ResponsiblePerson)
class ResponsiblePersonAdmin(admin.ModelAdmin):
    list_display = ['name', 'contact']
    search_fields = ['name', 'contact']


@admin.register(FiringRecord)
class FiringRecordAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'glaze_color', 'body_type', 'kiln_batch',
                    'trial_sequence', 'temperature_zone', 'responsible_person',
                    'status', 'color_difference', 'pinhole_condition', 'created_at']
    search_fields = ['glaze_color__code', 'glaze_color__name', 'kiln_batch__batch_code']
    list_filter = ['status', 'color_difference', 'pinhole_condition',
                   'glaze_color', 'body_type', 'kiln_batch', 'temperature_zone',
                   'responsible_person', 'created_at']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'created_at'


@admin.register(RectificationOrder)
class RectificationOrderAdmin(admin.ModelAdmin):
    list_display = ['order_no', 'firing_record', 'anomaly_type', 'status',
                    'responsible_person', 'planned_completion_date',
                    'is_overdue', 'created_at', 'close_time']
    search_fields = ['order_no', 'anomaly_description', 'rectification_measures']
    list_filter = ['status', 'anomaly_type', 'cause_category',
                   'responsible_person', 'planned_completion_date',
                   'created_at', 'close_time']
    readonly_fields = ['order_no', 'created_at', 'updated_at', 'is_overdue']
    inlines = [RectificationHistoryInline]
    date_hierarchy = 'created_at'

    def is_overdue(self, obj):
        return obj.is_overdue
    is_overdue.boolean = True
    is_overdue.short_description = '是否超期'


@admin.register(RectificationHistory)
class RectificationHistoryAdmin(admin.ModelAdmin):
    list_display = ['rectification_order', 'action', 'action_display',
                    'operator_name', 'previous_status', 'current_status', 'created_at']
    search_fields = ['rectification_order__order_no', 'operator_name', 'description']
    list_filter = ['action', 'created_at']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
