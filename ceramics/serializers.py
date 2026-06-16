from rest_framework import serializers
from django.utils import timezone
from .models import (
    GlazeColor, BodyType, KilnBatch, TemperatureZone,
    ResponsiblePerson, FiringRecord, RectificationOrder,
    RectificationHistory,
)


class GlazeColorSerializer(serializers.ModelSerializer):
    class Meta:
        model = GlazeColor
        fields = '__all__'


class BodyTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = BodyType
        fields = '__all__'


class KilnBatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = KilnBatch
        fields = '__all__'


class TemperatureZoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = TemperatureZone
        fields = '__all__'


class ResponsiblePersonSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResponsiblePerson
        fields = '__all__'


class FiringRecordRectificationSummarySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    order_no = serializers.CharField()
    status = serializers.CharField()
    status_display = serializers.CharField()
    anomaly_type = serializers.CharField()
    anomaly_type_display = serializers.CharField()
    is_overdue = serializers.BooleanField()


class FiringRecordListSerializer(serializers.ModelSerializer):
    glaze_color_code = serializers.CharField(source='glaze_color.code', read_only=True)
    glaze_color_name = serializers.CharField(source='glaze_color.name', read_only=True)
    body_type_name = serializers.CharField(source='body_type.name', read_only=True)
    kiln_batch_code = serializers.CharField(source='kiln_batch.batch_code', read_only=True)
    temperature_zone_name = serializers.CharField(source='temperature_zone.name', read_only=True)
    responsible_person_name = serializers.CharField(source='responsible_person.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    color_difference_display = serializers.CharField(source='get_color_difference_display', read_only=True)
    pinhole_condition_display = serializers.CharField(source='get_pinhole_condition_display', read_only=True)
    has_rectification = serializers.SerializerMethodField()
    rectification_count = serializers.SerializerMethodField()
    rectification_orders = serializers.SerializerMethodField()

    class Meta:
        model = FiringRecord
        fields = [
            'id', 'glaze_color', 'glaze_color_code', 'glaze_color_name',
            'body_type', 'body_type_name', 'kiln_batch', 'kiln_batch_code',
            'trial_sequence', 'temperature_zone', 'temperature_zone_name',
            'responsible_person', 'responsible_person_name',
            'status', 'status_display',
            'kiln_in_time', 'kiln_out_time',
            'color_difference', 'color_difference_display',
            'pinhole_condition', 'pinhole_condition_display',
            'glaze_flow_desc', 'retest_conclusion', 'handling_suggestion',
            'has_rectification', 'rectification_count', 'rectification_orders',
            'created_at', 'updated_at',
        ]

    def get_has_rectification(self, obj):
        return hasattr(obj, 'rectification_orders') and obj.rectification_orders.exists()

    def get_rectification_count(self, obj):
        if hasattr(obj, 'rectification_orders'):
            return obj.rectification_orders.count()
        return 0

    def get_rectification_orders(self, obj):
        if not hasattr(obj, 'rectification_orders'):
            return []
        orders = obj.rectification_orders.select_related(
            'responsible_person'
        ).all()
        return FiringRecordRectificationSummarySerializer([
            {
                'id': o.id,
                'order_no': o.order_no,
                'status': o.status,
                'status_display': o.get_status_display(),
                'anomaly_type': o.anomaly_type,
                'anomaly_type_display': o.get_anomaly_type_display(),
                'is_overdue': o.is_overdue,
            } for o in orders
        ], many=True).data


class FiringRecordCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = FiringRecord
        fields = [
            'id', 'glaze_color', 'body_type', 'kiln_batch', 'trial_sequence',
            'temperature_zone', 'responsible_person', 'status',
            'kiln_in_time', 'kiln_out_time',
            'color_difference', 'pinhole_condition',
            'glaze_flow_desc', 'retest_conclusion', 'handling_suggestion',
        ]

    def validate(self, data):
        kiln_batch = data.get('kiln_batch')
        trial_sequence = data.get('trial_sequence')
        instance = self.instance

        qs = FiringRecord.objects.filter(
            kiln_batch=kiln_batch, trial_sequence=trial_sequence
        )
        if instance:
            qs = qs.exclude(pk=instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                {'trial_sequence': f'窑次 {kiln_batch.batch_code} 的试烧序号 {trial_sequence} 已存在，不可重复'}
            )

        status_val = data.get('status')
        if status_val == FiringRecord.STATUS_FIRING and not data.get('kiln_in_time'):
            raise serializers.ValidationError(
                {'kiln_in_time': '试烧中状态必须填写入窑时间'}
            )
        if status_val in (FiringRecord.STATUS_PENDING_RETEST, FiringRecord.STATUS_RETESTED, FiringRecord.STATUS_ADJUSTING,
                          FiringRecord.STATUS_APPROVED, FiringRecord.STATUS_SUSPENDED):
            if not data.get('kiln_out_time') and not (instance and instance.kiln_out_time):
                raise serializers.ValidationError(
                    {'kiln_out_time': '该状态必须填写出窑时间'}
                )

        return data


class FiringRecordUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = FiringRecord
        fields = [
            'id', 'glaze_color', 'body_type', 'kiln_batch', 'trial_sequence',
            'temperature_zone', 'responsible_person', 'status',
            'kiln_in_time', 'kiln_out_time',
            'color_difference', 'pinhole_condition',
            'glaze_flow_desc', 'retest_conclusion', 'handling_suggestion',
        ]

    def validate(self, data):
        kiln_batch = data.get('kiln_batch', self.instance.kiln_batch)
        trial_sequence = data.get('trial_sequence', self.instance.trial_sequence)

        qs = FiringRecord.objects.filter(
            kiln_batch=kiln_batch, trial_sequence=trial_sequence
        ).exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                {'trial_sequence': f'窑次 {kiln_batch.batch_code} 的试烧序号 {trial_sequence} 已存在，不可重复'}
            )

        status_val = data.get('status', self.instance.status)
        kiln_in_time = data.get('kiln_in_time', self.instance.kiln_in_time)
        kiln_out_time = data.get('kiln_out_time', self.instance.kiln_out_time)

        if status_val == FiringRecord.STATUS_FIRING and not kiln_in_time:
            raise serializers.ValidationError(
                {'kiln_in_time': '试烧中状态必须填写入窑时间'}
            )
        if status_val in (FiringRecord.STATUS_PENDING_RETEST, FiringRecord.STATUS_RETESTED, FiringRecord.STATUS_ADJUSTING,
                          FiringRecord.STATUS_APPROVED, FiringRecord.STATUS_SUSPENDED):
            if not kiln_out_time:
                raise serializers.ValidationError(
                    {'kiln_out_time': '该状态必须填写出窑时间'}
                )

        if status_val == FiringRecord.STATUS_ADJUSTING:
            if data.get('color_difference', self.instance.color_difference) not in (
                FiringRecord.COLOR_DIFF_HIGH, FiringRecord.COLOR_DIFF_SEVERE, ''
            ):
                pass

        if status_val == FiringRecord.STATUS_APPROVED:
            if not data.get('retest_conclusion', self.instance.retest_conclusion):
                raise serializers.ValidationError(
                    {'retest_conclusion': '必须先完成复测（填写复测结论）才能定样'}
                )

        return data


class KilnInSerializer(serializers.Serializer):
    kiln_in_time = serializers.DateTimeField(required=False, default=None)

    def update(self, instance, validated_data):
        instance.kiln_in_time = validated_data.get('kiln_in_time') or timezone.now()
        instance.status = FiringRecord.STATUS_FIRING
        instance.save()
        return instance


class KilnOutSerializer(serializers.Serializer):
    kiln_out_time = serializers.DateTimeField(required=False, default=None)
    color_difference = serializers.ChoiceField(choices=FiringRecord.COLOR_DIFF_CHOICES, required=False, default='')
    pinhole_condition = serializers.ChoiceField(choices=FiringRecord.PINHOLE_CHOICES, required=False, default='')
    glaze_flow_desc = serializers.CharField(required=False, default='')

    def update(self, instance, validated_data):
        instance.kiln_out_time = validated_data.get('kiln_out_time') or timezone.now()
        instance.color_difference = validated_data.get('color_difference', instance.color_difference)
        instance.pinhole_condition = validated_data.get('pinhole_condition', instance.pinhole_condition)
        instance.glaze_flow_desc = validated_data.get('glaze_flow_desc', instance.glaze_flow_desc)
        instance.status = FiringRecord.STATUS_PENDING_RETEST
        instance.adjust_count = 0
        instance.save()
        return instance


class RetestSerializer(serializers.Serializer):
    retest_conclusion = serializers.CharField(required=True)
    handling_suggestion = serializers.CharField(required=False, default='')
    retest_time = serializers.DateTimeField(required=False, default=None)

    def update(self, instance, validated_data):
        instance.retest_conclusion = validated_data['retest_conclusion']
        instance.handling_suggestion = validated_data.get('handling_suggestion', instance.handling_suggestion)
        instance.retest_time = validated_data.get('retest_time') or timezone.now()
        instance.status = FiringRecord.STATUS_RETESTED
        instance.save()
        return instance


class AdjustSerializer(serializers.Serializer):
    handling_suggestion = serializers.CharField(required=False, default='')
    adjust_time = serializers.DateTimeField(required=False, default=None)

    def update(self, instance, validated_data):
        instance.status = FiringRecord.STATUS_ADJUSTING
        instance.handling_suggestion = validated_data.get('handling_suggestion', instance.handling_suggestion)
        instance.adjust_time = validated_data.get('adjust_time') or timezone.now()
        instance.adjust_count = instance.adjust_count + 1
        instance.save()
        return instance


class SuspendSerializer(serializers.Serializer):
    handling_suggestion = serializers.CharField(required=False, default='')
    suspend_time = serializers.DateTimeField(required=False, default=None)

    def update(self, instance, validated_data):
        instance.status = FiringRecord.STATUS_SUSPENDED
        instance.handling_suggestion = validated_data.get('handling_suggestion', instance.handling_suggestion)
        instance.suspend_time = validated_data.get('suspend_time') or timezone.now()
        instance.save()
        return instance


class ApproveSerializer(serializers.Serializer):
    approve_time = serializers.DateTimeField(required=False, default=None)

    def update(self, instance, validated_data):
        instance.status = FiringRecord.STATUS_APPROVED
        instance.approve_time = validated_data.get('approve_time') or timezone.now()
        instance.save()
        return instance


class HighRiskGlazeSerializer(serializers.Serializer):
    glaze_color_id = serializers.IntegerField()
    glaze_color_code = serializers.CharField()
    glaze_color_name = serializers.CharField()
    total_records = serializers.IntegerField()
    high_color_diff_count = serializers.IntegerField()
    severe_pinhole_count = serializers.IntegerField()
    suspended_count = serializers.IntegerField()
    risk_score = serializers.FloatField()


class PendingRetestSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    glaze_color_code = serializers.CharField()
    kiln_batch_code = serializers.CharField()
    trial_sequence = serializers.IntegerField()
    responsible_person_name = serializers.CharField()
    status = serializers.CharField()
    status_display = serializers.CharField()
    color_difference = serializers.CharField()
    color_difference_display = serializers.CharField()
    days_since_kiln_out = serializers.IntegerField(allow_null=True)
    retest_cycle_days = serializers.IntegerField()
    overdue = serializers.BooleanField()


class ZoneAnomalySerializer(serializers.Serializer):
    temperature_zone_id = serializers.IntegerField()
    zone_code = serializers.CharField()
    zone_name = serializers.CharField()
    total_records = serializers.IntegerField()
    high_color_diff_count = serializers.IntegerField()
    severe_pinhole_count = serializers.IntegerField()
    anomaly_rate = serializers.FloatField()


class ClosedLoopTaskSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    glaze_color_id = serializers.IntegerField()
    glaze_color_code = serializers.CharField()
    glaze_color_name = serializers.CharField()
    body_type_id = serializers.IntegerField()
    body_type_name = serializers.CharField()
    kiln_batch_id = serializers.IntegerField()
    kiln_batch_code = serializers.CharField()
    kiln_batch_date = serializers.DateField()
    trial_sequence = serializers.IntegerField()
    temperature_zone_id = serializers.IntegerField()
    temperature_zone_name = serializers.CharField()
    responsible_person_id = serializers.IntegerField()
    responsible_person_name = serializers.CharField()
    status = serializers.CharField()
    status_display = serializers.CharField()
    current_node = serializers.CharField()
    remaining_days = serializers.IntegerField(allow_null=True)
    overdue_days = serializers.IntegerField(allow_null=True)
    is_overdue = serializers.BooleanField()
    anomaly_summary = serializers.CharField()
    suggested_action = serializers.CharField()
    adjust_count = serializers.IntegerField()
    kiln_out_time = serializers.DateTimeField(allow_null=True)
    retest_cycle_days = serializers.IntegerField()


class TimeNodeSerializer(serializers.Serializer):
    node_key = serializers.CharField()
    node_name = serializers.CharField()
    time = serializers.DateTimeField(allow_null=True)
    completed = serializers.BooleanField()


class NextActionSerializer(serializers.Serializer):
    action_key = serializers.CharField()
    action_name = serializers.CharField()
    enabled = serializers.BooleanField()
    reason = serializers.CharField(required=False, default='')


class ClosedLoopDetailSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    basic_info = serializers.DictField()
    quality_anomaly = serializers.DictField()
    retest_conclusion = serializers.CharField()
    handling_suggestion = serializers.CharField()
    time_nodes = TimeNodeSerializer(many=True)
    next_actions = NextActionSerializer(many=True)
    adjust_count = serializers.IntegerField()
    current_node = serializers.CharField()
    is_overdue = serializers.BooleanField()
    remaining_days = serializers.IntegerField(allow_null=True)
    overdue_days = serializers.IntegerField(allow_null=True)


class RectificationOrderListSerializer(serializers.ModelSerializer):
    firing_record_id = serializers.IntegerField(source='firing_record.id', read_only=True)
    firing_record_display = serializers.CharField(source='firing_record.__str__', read_only=True)
    glaze_color_code = serializers.CharField(source='firing_record.glaze_color.code', read_only=True)
    glaze_color_name = serializers.CharField(source='firing_record.glaze_color.name', read_only=True)
    kiln_batch_code = serializers.CharField(source='firing_record.kiln_batch.batch_code', read_only=True)
    trial_sequence = serializers.IntegerField(source='firing_record.trial_sequence', read_only=True)
    responsible_person_name = serializers.CharField(source='responsible_person.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    anomaly_type_display = serializers.CharField(source='get_anomaly_type_display', read_only=True)
    cause_category_display = serializers.CharField(source='get_cause_category_display', read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)

    class Meta:
        model = RectificationOrder
        fields = [
            'id', 'order_no', 'firing_record_id', 'firing_record_display',
            'glaze_color_code', 'glaze_color_name',
            'kiln_batch_code', 'trial_sequence',
            'anomaly_type', 'anomaly_type_display',
            'anomaly_description',
            'cause_category', 'cause_category_display',
            'responsible_person', 'responsible_person_name',
            'planned_completion_date',
            'status', 'status_display',
            'is_overdue',
            'close_time',
            'created_at', 'updated_at',
        ]


class RectificationOrderCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = RectificationOrder
        fields = [
            'id', 'firing_record', 'anomaly_type', 'anomaly_description',
            'cause_category', 'cause_detail', 'responsible_person',
            'rectification_measures', 'planned_completion_date',
        ]

    def validate(self, data):
        firing_record = data.get('firing_record')
        anomaly_type = data.get('anomaly_type')

        active_duplicate_exists = RectificationOrder.objects.filter(
            firing_record=firing_record,
            anomaly_type=anomaly_type,
            status__in=(
                RectificationOrder.STATUS_PENDING_ANALYSIS,
                RectificationOrder.STATUS_RECTIFYING,
                RectificationOrder.STATUS_PENDING_CONFIRM,
            ),
        ).exists()
        if active_duplicate_exists:
            raise serializers.ValidationError(
                {'anomaly_type': '该试烧记录已存在同类处理中整改单，请勿重复发起'}
            )

        if anomaly_type == RectificationOrder.ANOMALY_COLOR_DIFF_HIGH:
            if firing_record.color_difference not in (FiringRecord.COLOR_DIFF_HIGH, FiringRecord.COLOR_DIFF_SEVERE):
                raise serializers.ValidationError(
                    {'anomaly_type': '该试烧记录色差不满足偏高/严重条件，无法发起此类整改单'}
                )
        elif anomaly_type == RectificationOrder.ANOMALY_COLOR_DIFF_SEVERE:
            if firing_record.color_difference != FiringRecord.COLOR_DIFF_SEVERE:
                raise serializers.ValidationError(
                    {'anomaly_type': '该试烧记录色差不满足严重条件，无法发起此类整改单'}
                )
        elif anomaly_type == RectificationOrder.ANOMALY_PINHOLE_MODERATE:
            if firing_record.pinhole_condition not in (FiringRecord.PINHOLE_MODERATE, FiringRecord.PINHOLE_SEVERE):
                raise serializers.ValidationError(
                    {'anomaly_type': '该试烧记录针孔情况不满足中等/严重条件，无法发起此类整改单'}
                )
        elif anomaly_type == RectificationOrder.ANOMALY_PINHOLE_SEVERE:
            if firing_record.pinhole_condition != FiringRecord.PINHOLE_SEVERE:
                raise serializers.ValidationError(
                    {'anomaly_type': '该试烧记录针孔情况不满足严重条件，无法发起此类整改单'}
                )
        elif anomaly_type == RectificationOrder.ANOMALY_SUSPENDED:
            if firing_record.status != FiringRecord.STATUS_SUSPENDED:
                raise serializers.ValidationError(
                    {'anomaly_type': '该试烧记录未处于暂停状态，无法发起此类整改单'}
                )
        elif anomaly_type == RectificationOrder.ANOMALY_RETEST_OVERDUE:
            if firing_record.status not in (FiringRecord.STATUS_PENDING_RETEST, FiringRecord.STATUS_ADJUSTING):
                raise serializers.ValidationError(
                    {'anomaly_type': '该试烧记录不处于待复测或调整中状态，无法发起此类整改单'}
                )
            if not firing_record.kiln_out_time or firing_record.retest_conclusion:
                raise serializers.ValidationError(
                    {'anomaly_type': '该试烧记录已完成复测或未出窑，无法发起复测超期整改单'}
                )
            from django.utils import timezone
            now = timezone.now()
            cycle = firing_record.glaze_color.retest_cycle_days
            days_since = (now - firing_record.kiln_out_time).days
            if days_since <= cycle:
                raise serializers.ValidationError(
                    {'anomaly_type': f'该试烧记录出窑仅{days_since}天，未超过复测周期{cycle}天，不满足超期条件'}
                )

        return data

    def create(self, validated_data):
        from django.utils import timezone
        from .models import RectificationOrder

        today_str = timezone.now().strftime('%Y%m%d')
        count = RectificationOrder.objects.filter(order_no__startswith=f'ZG{today_str}').count()
        order_no = f'ZG{today_str}{count + 1:04d}'

        validated_data['order_no'] = order_no
        return super().create(validated_data)


class RectificationOrderUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = RectificationOrder
        fields = [
            'anomaly_description', 'cause_category', 'cause_detail',
            'responsible_person', 'rectification_measures',
            'planned_completion_date', 'rectification_result',
        ]


class RectificationAnalyzeSerializer(serializers.Serializer):
    cause_category = serializers.ChoiceField(choices=RectificationOrder.CAUSE_CATEGORY_CHOICES, required=True)
    cause_detail = serializers.CharField(required=False, default='')
    rectification_measures = serializers.CharField(required=False, default='')
    planned_completion_date = serializers.DateField(required=True)
    analysis_time = serializers.DateTimeField(required=False, default=None)

    def update(self, instance, validated_data):
        from django.utils import timezone
        instance.cause_category = validated_data['cause_category']
        instance.cause_detail = validated_data.get('cause_detail', instance.cause_detail)
        instance.rectification_measures = validated_data.get('rectification_measures', instance.rectification_measures)
        instance.planned_completion_date = validated_data['planned_completion_date']
        instance.analysis_time = validated_data.get('analysis_time') or timezone.now()
        instance.status = RectificationOrder.STATUS_RECTIFYING
        instance.save()
        return instance


class RectificationSubmitSerializer(serializers.Serializer):
    rectification_result = serializers.CharField(required=True)
    rectification_time = serializers.DateTimeField(required=False, default=None)

    def update(self, instance, validated_data):
        from django.utils import timezone
        instance.rectification_result = validated_data['rectification_result']
        instance.rectification_time = validated_data.get('rectification_time') or timezone.now()
        instance.status = RectificationOrder.STATUS_PENDING_CONFIRM
        instance.save()
        return instance


class RectificationConfirmSerializer(serializers.Serializer):
    confirm_time = serializers.DateTimeField(required=False, default=None)
    close_time = serializers.DateTimeField(required=False, default=None)

    def update(self, instance, validated_data):
        from django.utils import timezone
        now = validated_data.get('confirm_time') or timezone.now()
        instance.confirm_time = now
        instance.close_time = validated_data.get('close_time') or now
        instance.status = RectificationOrder.STATUS_CLOSED
        instance.save()
        return instance


class RectificationReopenSerializer(serializers.Serializer):
    reason = serializers.CharField(required=True)

    def update(self, instance, validated_data):
        instance.status = RectificationOrder.STATUS_RECTIFYING
        instance.rectification_result = ''
        instance.confirm_time = None
        instance.close_time = None
        instance.save()
        return instance


class RectificationRejectSerializer(serializers.Serializer):
    reason = serializers.CharField(required=True)
    operator_name = serializers.CharField(required=False, default='')

    def update(self, instance, validated_data):
        from django.utils import timezone
        now = timezone.now()
        instance.confirm_time = now
        instance.close_time = now
        instance.status = RectificationOrder.STATUS_CLOSED
        instance.save()

        instance.status = RectificationOrder.STATUS_RECTIFYING
        instance.rectification_result = ''
        instance.confirm_time = None
        instance.close_time = None
        instance.analysis_time = None
        instance.rectification_time = None
        instance.cause_category = ''
        instance.cause_detail = ''
        instance.rectification_measures = ''
        instance.save()

        return instance


class RectificationHistorySerializer(serializers.ModelSerializer):
    action_display = serializers.CharField(source='get_action_display', read_only=True)

    class Meta:
        model = RectificationHistory
        fields = [
            'id', 'action', 'action_display',
            'operator_name', 'description',
            'previous_status', 'current_status',
            'created_at',
        ]


class RectificationHistoryCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = RectificationHistory
        fields = [
            'id', 'rectification_order', 'action',
            'operator_name', 'description',
        ]


class RectificationOrderDetailSerializer(serializers.ModelSerializer):
    firing_record_id = serializers.IntegerField(source='firing_record.id', read_only=True)
    firing_record_display = serializers.CharField(source='firing_record.__str__', read_only=True)
    glaze_color_code = serializers.CharField(source='firing_record.glaze_color.code', read_only=True)
    glaze_color_name = serializers.CharField(source='firing_record.glaze_color.name', read_only=True)
    body_type_name = serializers.CharField(source='firing_record.body_type.name', read_only=True)
    kiln_batch_code = serializers.CharField(source='firing_record.kiln_batch.batch_code', read_only=True)
    kiln_batch_date = serializers.DateField(source='firing_record.kiln_batch.firing_date', read_only=True)
    trial_sequence = serializers.IntegerField(source='firing_record.trial_sequence', read_only=True)
    temperature_zone_name = serializers.CharField(source='firing_record.temperature_zone.name', read_only=True)
    responsible_person_name = serializers.CharField(source='responsible_person.name', read_only=True)
    responsible_person_contact = serializers.CharField(source='responsible_person.contact', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    anomaly_type_display = serializers.CharField(source='get_anomaly_type_display', read_only=True)
    cause_category_display = serializers.CharField(source='get_cause_category_display', read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    remaining_days = serializers.IntegerField(read_only=True)
    overdue_days = serializers.IntegerField(read_only=True)
    history_records = RectificationHistorySerializer(many=True, read_only=True)

    class Meta:
        model = RectificationOrder
        fields = [
            'id', 'order_no',
            'firing_record_id', 'firing_record_display',
            'glaze_color_code', 'glaze_color_name',
            'body_type_name',
            'kiln_batch_code', 'kiln_batch_date',
            'trial_sequence',
            'temperature_zone_name',
            'anomaly_type', 'anomaly_type_display',
            'anomaly_description',
            'cause_category', 'cause_category_display',
            'cause_detail',
            'responsible_person', 'responsible_person_name', 'responsible_person_contact',
            'rectification_measures',
            'planned_completion_date',
            'rectification_result',
            'status', 'status_display',
            'is_overdue', 'remaining_days', 'overdue_days',
            'analysis_time', 'rectification_time', 'confirm_time', 'close_time',
            'created_at', 'updated_at',
            'history_records',
        ]


class PendingAbnormalItemSerializer(serializers.Serializer):
    firing_record_id = serializers.IntegerField()
    glaze_color_id = serializers.IntegerField()
    glaze_color_code = serializers.CharField()
    glaze_color_name = serializers.CharField()
    body_type_id = serializers.IntegerField()
    body_type_name = serializers.CharField()
    kiln_batch_id = serializers.IntegerField()
    kiln_batch_code = serializers.CharField()
    kiln_batch_date = serializers.DateField()
    trial_sequence = serializers.IntegerField()
    temperature_zone_id = serializers.IntegerField()
    temperature_zone_name = serializers.CharField()
    responsible_person_id = serializers.IntegerField()
    responsible_person_name = serializers.CharField()
    anomaly_type = serializers.CharField()
    anomaly_type_display = serializers.CharField()
    anomaly_description = serializers.CharField()
    has_active_rectification = serializers.BooleanField()
    active_rectification_id = serializers.IntegerField(allow_null=True)
    active_rectification_status = serializers.CharField(allow_null=True)
    active_rectification_status_display = serializers.CharField(allow_null=True)
    latest_rectification_id = serializers.IntegerField(allow_null=True)
    latest_rectification_status = serializers.CharField(allow_null=True)
    latest_rectification_status_display = serializers.CharField(allow_null=True)
    created_at = serializers.DateTimeField()


class RectificationDashboardSerializer(serializers.Serializer):
    pending_total_count = serializers.IntegerField()
    pending_count = serializers.IntegerField()
    rectifying_count = serializers.IntegerField()
    pending_confirm_count = serializers.IntegerField()
    closed_count = serializers.IntegerField()
    total_overdue_count = serializers.IntegerField()
    pending_overdue_count = serializers.IntegerField()
    rectifying_overdue_count = serializers.IntegerField()
    recently_closed = RectificationOrderListSerializer(many=True)

