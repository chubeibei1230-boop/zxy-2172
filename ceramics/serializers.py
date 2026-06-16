from rest_framework import serializers
from django.utils import timezone
from .models import (
    GlazeColor, BodyType, KilnBatch, TemperatureZone,
    ResponsiblePerson, FiringRecord,
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
            'created_at', 'updated_at',
        ]


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
        if status_val in (FiringRecord.STATUS_PENDING_RETEST, FiringRecord.STATUS_ADJUSTING,
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
        if status_val in (FiringRecord.STATUS_PENDING_RETEST, FiringRecord.STATUS_ADJUSTING,
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
        instance.save()
        return instance


class RetestSerializer(serializers.Serializer):
    retest_conclusion = serializers.CharField(required=True)
    handling_suggestion = serializers.CharField(required=False, default='')

    def update(self, instance, validated_data):
        instance.retest_conclusion = validated_data['retest_conclusion']
        instance.handling_suggestion = validated_data.get('handling_suggestion', instance.handling_suggestion)
        instance.save()
        return instance


class AdjustSerializer(serializers.Serializer):
    handling_suggestion = serializers.CharField(required=False, default='')

    def update(self, instance, validated_data):
        instance.status = FiringRecord.STATUS_ADJUSTING
        instance.handling_suggestion = validated_data.get('handling_suggestion', instance.handling_suggestion)
        instance.save()
        return instance


class SuspendSerializer(serializers.Serializer):
    handling_suggestion = serializers.CharField(required=False, default='')

    def update(self, instance, validated_data):
        instance.status = FiringRecord.STATUS_SUSPENDED
        instance.handling_suggestion = validated_data.get('handling_suggestion', instance.handling_suggestion)
        instance.save()
        return instance


class ApproveSerializer(serializers.Serializer):
    def update(self, instance, validated_data):
        instance.status = FiringRecord.STATUS_APPROVED
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
