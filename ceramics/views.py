from django.db.models import Count, Q, F, ExpressionWrapper, IntegerField
from django.utils import timezone
from rest_framework import viewsets, status, generics
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.filters import SearchFilter, OrderingFilter
import django_filters

from .models import (
    GlazeColor, BodyType, KilnBatch, TemperatureZone,
    ResponsiblePerson, FiringRecord,
)
from .serializers import (
    GlazeColorSerializer, BodyTypeSerializer, KilnBatchSerializer,
    TemperatureZoneSerializer, ResponsiblePersonSerializer,
    FiringRecordListSerializer, FiringRecordCreateSerializer,
    FiringRecordUpdateSerializer, KilnInSerializer, KilnOutSerializer,
    RetestSerializer, AdjustSerializer, SuspendSerializer, ApproveSerializer,
    HighRiskGlazeSerializer, PendingRetestSerializer, ZoneAnomalySerializer,
)


class GlazeColorViewSet(viewsets.ModelViewSet):
    queryset = GlazeColor.objects.all()
    serializer_class = GlazeColorSerializer
    search_fields = ['code', 'name']


class BodyTypeViewSet(viewsets.ModelViewSet):
    queryset = BodyType.objects.all()
    serializer_class = BodyTypeSerializer
    search_fields = ['code', 'name']


class KilnBatchViewSet(viewsets.ModelViewSet):
    queryset = KilnBatch.objects.all()
    serializer_class = KilnBatchSerializer
    search_fields = ['batch_code']
    filterset_fields = ['firing_date']


class TemperatureZoneViewSet(viewsets.ModelViewSet):
    queryset = TemperatureZone.objects.all()
    serializer_class = TemperatureZoneSerializer
    search_fields = ['zone_code', 'name']


class ResponsiblePersonViewSet(viewsets.ModelViewSet):
    queryset = ResponsiblePerson.objects.all()
    serializer_class = ResponsiblePersonSerializer
    search_fields = ['name']


class FiringRecordFilter(django_filters.FilterSet):
    date_from = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    date_to = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')
    kiln_in_from = django_filters.DateTimeFilter(field_name='kiln_in_time', lookup_expr='gte')
    kiln_in_to = django_filters.DateTimeFilter(field_name='kiln_in_time', lookup_expr='lte')

    class Meta:
        model = FiringRecord
        fields = {
            'glaze_color': ['exact'],
            'kiln_batch': ['exact'],
            'temperature_zone': ['exact'],
            'responsible_person': ['exact'],
            'status': ['exact'],
            'color_difference': ['exact'],
            'body_type': ['exact'],
        }


class FiringRecordViewSet(viewsets.ModelViewSet):
    queryset = FiringRecord.objects.select_related(
        'glaze_color', 'body_type', 'kiln_batch',
        'temperature_zone', 'responsible_person',
    ).all()
    filterset_class = FiringRecordFilter
    search_fields = ['glaze_color__code', 'glaze_color__name', 'kiln_batch__batch_code']
    ordering_fields = [
        'created_at', 'kiln_in_time', 'kiln_out_time',
        'trial_sequence', 'status', 'color_difference',
    ]

    def get_serializer_class(self):
        if self.action == 'list' or self.action == 'retrieve':
            return FiringRecordListSerializer
        if self.action == 'create':
            return FiringRecordCreateSerializer
        if self.action in ('update', 'partial_update'):
            return FiringRecordUpdateSerializer
        return FiringRecordListSerializer

    @action(detail=True, methods=['post'], url_path='kiln-in')
    def kiln_in(self, request, pk=None):
        record = self.get_object()
        if record.status != FiringRecord.STATUS_PENDING:
            return Response(
                {'detail': f'当前状态为"{record.get_status_display()}"，只有"待试烧"状态可执行入窑操作'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = KilnInSerializer(instance=record, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(FiringRecordListSerializer(record).data)

    @action(detail=True, methods=['post'], url_path='kiln-out')
    def kiln_out(self, request, pk=None):
        record = self.get_object()
        if record.status != FiringRecord.STATUS_FIRING:
            return Response(
                {'detail': f'当前状态为"{record.get_status_display()}"，只有"试烧中"状态可执行出窑操作'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = KilnOutSerializer(instance=record, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(FiringRecordListSerializer(record).data)

    @action(detail=True, methods=['post'], url_path='retest')
    def retest(self, request, pk=None):
        record = self.get_object()
        if record.status not in (FiringRecord.STATUS_PENDING_RETEST, FiringRecord.STATUS_ADJUSTING):
            return Response(
                {'detail': f'当前状态为"{record.get_status_display()}"，只有"待复测"或"调整中"状态可执行复测操作'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = RetestSerializer(instance=record, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(FiringRecordListSerializer(record).data)

    @action(detail=True, methods=['post'], url_path='adjust')
    def adjust(self, request, pk=None):
        record = self.get_object()
        if not record.kiln_out_time:
            return Response(
                {'detail': '未出窑的记录不能进入调整中状态，请先执行出窑操作'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if record.status not in (FiringRecord.STATUS_PENDING_RETEST, FiringRecord.STATUS_ADJUSTING):
            return Response(
                {'detail': f'当前状态为"{record.get_status_display()}"，只有"待复测"状态可执行调整操作'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = AdjustSerializer(instance=record, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(FiringRecordListSerializer(record).data)

    @action(detail=True, methods=['post'], url_path='suspend')
    def suspend(self, request, pk=None):
        record = self.get_object()
        if record.status == FiringRecord.STATUS_SUSPENDED:
            return Response(
                {'detail': '该记录已处于暂停使用状态'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = SuspendSerializer(instance=record, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(FiringRecordListSerializer(record).data)

    @action(detail=True, methods=['post'], url_path='approve')
    def approve(self, request, pk=None):
        record = self.get_object()
        if record.status in (FiringRecord.STATUS_PENDING, FiringRecord.STATUS_FIRING, FiringRecord.STATUS_SUSPENDED):
            return Response(
                {'detail': f'当前状态为"{record.get_status_display()}"，不可直接定样'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not record.retest_conclusion:
            return Response(
                {'detail': '必须先完成复测（填写复测结论）才能定样'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = ApproveSerializer(instance=record, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(FiringRecordListSerializer(record).data)

    @action(detail=False, methods=['get'], url_path='alerts')
    def alerts(self, request):
        alerts = []

        consecutive_high = self._detect_consecutive_high_color_diff()
        for item in consecutive_high:
            alerts.append({
                'type': 'consecutive_high_color_diff',
                'level': 'warning',
                'message': f'釉色 {item["glaze_color_code"]} 连续 {item["count"]} 次色差偏高/严重',
                'data': item,
            })

        overdue_retests = self._detect_overdue_retests()
        for item in overdue_retests:
            alerts.append({
                'type': 'overdue_retest',
                'level': 'danger',
                'message': f'窑次 {item["kiln_batch_code"]}-{item["trial_sequence"]} 复测已超期 {item["overdue_days"]} 天',
                'data': item,
            })

        zone_anomalies = self._detect_zone_anomalies()
        for item in zone_anomalies:
            alerts.append({
                'type': 'zone_anomaly',
                'level': 'warning',
                'message': f'温区 {item["zone_name"]} 异常集中，异常率 {item["anomaly_rate"]:.1%}',
                'data': item,
            })

        adjust_no_retest = self._detect_adjust_without_retest()
        for item in adjust_no_retest:
            alerts.append({
                'type': 'adjust_without_retest',
                'level': 'info',
                'message': f'窑次 {item["kiln_batch_code"]}-{item["trial_sequence"]} 调整后尚未复测',
                'data': item,
            })

        return Response({'count': len(alerts), 'results': alerts})

    def _detect_consecutive_high_color_diff(self):
        results = []
        glaze_colors = GlazeColor.objects.all()
        for gc in glaze_colors:
            records = FiringRecord.objects.filter(
                glaze_color=gc
            ).select_related('kiln_batch').order_by(
                'kiln_batch__firing_date', 'trial_sequence'
            )
            max_consecutive = 0
            current_consecutive = 0
            for r in records:
                if r.color_difference in (FiringRecord.COLOR_DIFF_HIGH, FiringRecord.COLOR_DIFF_SEVERE):
                    current_consecutive += 1
                    max_consecutive = max(max_consecutive, current_consecutive)
                else:
                    current_consecutive = 0
            if max_consecutive >= 2:
                results.append({
                    'glaze_color_id': gc.id,
                    'glaze_color_code': gc.code,
                    'glaze_color_name': gc.name,
                    'count': max_consecutive,
                })
        return results

    def _detect_overdue_retests(self):
        now = timezone.now()
        results = []
        records = FiringRecord.objects.filter(
            status=FiringRecord.STATUS_PENDING_RETEST,
            kiln_out_time__isnull=False,
            retest_conclusion='',
        ).select_related('glaze_color', 'kiln_batch', 'responsible_person')
        for r in records:
            cycle = r.glaze_color.retest_cycle_days
            days_since = (now - r.kiln_out_time).days
            if days_since > cycle:
                results.append({
                    'id': r.id,
                    'glaze_color_code': r.glaze_color.code,
                    'kiln_batch_code': r.kiln_batch.batch_code,
                    'trial_sequence': r.trial_sequence,
                    'responsible_person_name': r.responsible_person.name,
                    'kiln_out_time': r.kiln_out_time,
                    'days_since_kiln_out': days_since,
                    'retest_cycle_days': cycle,
                    'overdue_days': days_since - cycle,
                })
        return results

    def _detect_zone_anomalies(self):
        results = []
        zones = TemperatureZone.objects.all()
        for zone in zones:
            total = FiringRecord.objects.filter(temperature_zone=zone).count()
            if total == 0:
                continue
            high_cd_count = FiringRecord.objects.filter(
                temperature_zone=zone,
                color_difference__in=(FiringRecord.COLOR_DIFF_HIGH, FiringRecord.COLOR_DIFF_SEVERE),
            ).count()
            severe_ph_count = FiringRecord.objects.filter(
                temperature_zone=zone,
                pinhole_condition__in=(FiringRecord.PINHOLE_MODERATE, FiringRecord.PINHOLE_SEVERE),
            ).count()
            anomaly_records = FiringRecord.objects.filter(
                temperature_zone=zone,
            ).filter(
                Q(color_difference__in=(FiringRecord.COLOR_DIFF_HIGH, FiringRecord.COLOR_DIFF_SEVERE)) |
                Q(pinhole_condition__in=(FiringRecord.PINHOLE_MODERATE, FiringRecord.PINHOLE_SEVERE))
            ).count()
            anomaly_rate = anomaly_records / total if total > 0 else 0
            if anomaly_rate > 0.3:
                results.append({
                    'temperature_zone_id': zone.id,
                    'zone_code': zone.zone_code,
                    'zone_name': zone.name,
                    'total_records': total,
                    'high_color_diff_count': high_cd_count,
                    'severe_pinhole_count': severe_ph_count,
                    'anomaly_rate': anomaly_rate,
                })
        return results

    def _detect_adjust_without_retest(self):
        results = []
        records = FiringRecord.objects.filter(
            status=FiringRecord.STATUS_ADJUSTING,
            retest_conclusion='',
        ).select_related('glaze_color', 'kiln_batch', 'responsible_person')
        for r in records:
            results.append({
                'id': r.id,
                'glaze_color_code': r.glaze_color.code,
                'kiln_batch_code': r.kiln_batch.batch_code,
                'trial_sequence': r.trial_sequence,
                'responsible_person_name': r.responsible_person.name,
                'status': r.status,
                'status_display': r.get_status_display(),
            })
        return results


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def high_risk_glaze_ranking(request):
    records = FiringRecord.objects.all()
    glaze_data = {}
    for r in records:
        gc_id = r.glaze_color_id
        if gc_id not in glaze_data:
            gc = r.glaze_color
            glaze_data[gc_id] = {
                'glaze_color_id': gc.id,
                'glaze_color_code': gc.code,
                'glaze_color_name': gc.name,
                'total_records': 0,
                'high_color_diff_count': 0,
                'severe_pinhole_count': 0,
                'suspended_count': 0,
            }
        glaze_data[gc_id]['total_records'] += 1
        if r.color_difference in (FiringRecord.COLOR_DIFF_HIGH, FiringRecord.COLOR_DIFF_SEVERE):
            glaze_data[gc_id]['high_color_diff_count'] += 1
        if r.pinhole_condition in (FiringRecord.PINHOLE_MODERATE, FiringRecord.PINHOLE_SEVERE):
            glaze_data[gc_id]['severe_pinhole_count'] += 1
        if r.status == FiringRecord.STATUS_SUSPENDED:
            glaze_data[gc_id]['suspended_count'] += 1

    for item in glaze_data.values():
        total = item['total_records'] or 1
        item['risk_score'] = round(
            item['high_color_diff_count'] * 3 +
            item['severe_pinhole_count'] * 2 +
            item['suspended_count'] * 5
            , 2)

    ranking = sorted(glaze_data.values(), key=lambda x: x['risk_score'], reverse=True)
    serializer = HighRiskGlazeSerializer(ranking, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def pending_retest_tasks(request):
    now = timezone.now()
    records = FiringRecord.objects.filter(
        status__in=(FiringRecord.STATUS_PENDING_RETEST, FiringRecord.STATUS_ADJUSTING),
        retest_conclusion='',
    ).select_related(
        'glaze_color', 'kiln_batch', 'responsible_person'
    ).order_by('kiln_out_time')

    results = []
    for r in records:
        days_since = (now - r.kiln_out_time).days if r.kiln_out_time else None
        overdue = False
        if days_since is not None and days_since > r.glaze_color.retest_cycle_days:
            overdue = True
        results.append({
            'id': r.id,
            'glaze_color_code': r.glaze_color.code,
            'kiln_batch_code': r.kiln_batch.batch_code,
            'trial_sequence': r.trial_sequence,
            'responsible_person_name': r.responsible_person.name,
            'status': r.status,
            'status_display': r.get_status_display(),
            'color_difference': r.color_difference,
            'color_difference_display': r.get_color_difference_display(),
            'days_since_kiln_out': days_since,
            'retest_cycle_days': r.glaze_color.retest_cycle_days,
            'overdue': overdue,
        })

    serializer = PendingRetestSerializer(results, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def zone_anomaly_distribution(request):
    zones = TemperatureZone.objects.all()
    results = []
    for zone in zones:
        total = FiringRecord.objects.filter(temperature_zone=zone).count()
        high_cd = FiringRecord.objects.filter(
            temperature_zone=zone,
            color_difference__in=(FiringRecord.COLOR_DIFF_HIGH, FiringRecord.COLOR_DIFF_SEVERE),
        ).count()
        severe_ph = FiringRecord.objects.filter(
            temperature_zone=zone,
            pinhole_condition__in=(FiringRecord.PINHOLE_MODERATE, FiringRecord.PINHOLE_SEVERE),
        ).count()
        anomaly_records = FiringRecord.objects.filter(
            temperature_zone=zone,
        ).filter(
            Q(color_difference__in=(FiringRecord.COLOR_DIFF_HIGH, FiringRecord.COLOR_DIFF_SEVERE)) |
            Q(pinhole_condition__in=(FiringRecord.PINHOLE_MODERATE, FiringRecord.PINHOLE_SEVERE))
        ).count()
        anomaly_rate = anomaly_records / total if total > 0 else 0
        results.append({
            'temperature_zone_id': zone.id,
            'zone_code': zone.zone_code,
            'zone_name': zone.name,
            'total_records': total,
            'high_color_diff_count': high_cd,
            'severe_pinhole_count': severe_ph,
            'anomaly_rate': round(anomaly_rate, 4),
        })

    serializer = ZoneAnomalySerializer(results, many=True)
    return Response(serializer.data)
