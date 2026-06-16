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
    ResponsiblePerson, FiringRecord, RectificationOrder,
    RectificationHistory,
)
from .serializers import (
    GlazeColorSerializer, BodyTypeSerializer, KilnBatchSerializer,
    TemperatureZoneSerializer, ResponsiblePersonSerializer,
    FiringRecordListSerializer, FiringRecordCreateSerializer,
    FiringRecordUpdateSerializer, KilnInSerializer, KilnOutSerializer,
    RetestSerializer, AdjustSerializer, SuspendSerializer, ApproveSerializer,
    HighRiskGlazeSerializer, PendingRetestSerializer, ZoneAnomalySerializer,
    ClosedLoopTaskSerializer, ClosedLoopDetailSerializer,
    RectificationOrderListSerializer, RectificationOrderDetailSerializer,
    RectificationOrderCreateSerializer, RectificationOrderUpdateSerializer,
    RectificationAnalyzeSerializer, RectificationSubmitSerializer,
    RectificationConfirmSerializer, RectificationReopenSerializer,
    RectificationRejectSerializer,
    RectificationDashboardSerializer, RectificationHistorySerializer,
    RectificationHistoryCreateSerializer, PendingAbnormalItemSerializer,
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
    ).prefetch_related(
        'rectification_orders',
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
        if record.status not in (FiringRecord.STATUS_PENDING_RETEST, FiringRecord.STATUS_RETESTED, FiringRecord.STATUS_ADJUSTING):
            return Response(
                {'detail': f'当前状态为"{record.get_status_display()}"，只有"待复测"或"已复测"状态可执行调整操作'},
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
        if record.status in (FiringRecord.STATUS_PENDING, FiringRecord.STATUS_FIRING, FiringRecord.STATUS_PENDING_RETEST, FiringRecord.STATUS_SUSPENDED):
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


NODE_MAP = {
    FiringRecord.STATUS_PENDING: 'pending',
    FiringRecord.STATUS_FIRING: 'kiln_in',
    FiringRecord.STATUS_PENDING_RETEST: 'kiln_out',
    FiringRecord.STATUS_RETESTED: 'retest',
    FiringRecord.STATUS_ADJUSTING: 'adjust',
    FiringRecord.STATUS_APPROVED: 'approve',
    FiringRecord.STATUS_SUSPENDED: 'suspend',
}

NODE_NAME_MAP = {
    'pending': '待试烧',
    'kiln_in': '入窑',
    'kiln_out': '出窑',
    'retest': '复测',
    'adjust': '调整',
    'approve': '定样',
    'suspend': '暂停',
}


def _get_anomaly_summary(record):
    anomalies = []
    if record.color_difference == FiringRecord.COLOR_DIFF_SEVERE:
        anomalies.append('色差严重')
    elif record.color_difference == FiringRecord.COLOR_DIFF_HIGH:
        anomalies.append('色差偏高')
    if record.pinhole_condition == FiringRecord.PINHOLE_SEVERE:
        anomalies.append('针孔严重')
    elif record.pinhole_condition == FiringRecord.PINHOLE_MODERATE:
        anomalies.append('针孔中等')
    if record.glaze_flow_desc:
        anomalies.append('釉面流动异常')
    if not anomalies:
        return '无明显异常'
    return '、'.join(anomalies)


def _get_suggested_action(record):
    if record.status == FiringRecord.STATUS_PENDING:
        return '请安排入窑试烧'
    if record.status == FiringRecord.STATUS_FIRING:
        return '等待出窑后进行质量检验'
    if record.status == FiringRecord.STATUS_PENDING_RETEST:
        return '请尽快完成复测并填写结论'
    if record.status == FiringRecord.STATUS_RETESTED:
        if record.color_difference in (FiringRecord.COLOR_DIFF_HIGH, FiringRecord.COLOR_DIFF_SEVERE):
            return '建议进行配方或工艺调整后复测'
        return '可进行定样审批'
    if record.status == FiringRecord.STATUS_ADJUSTING:
        return '请在调整后安排复测验证'
    if record.status == FiringRecord.STATUS_APPROVED:
        return '已定样，可投入批量生产'
    if record.status == FiringRecord.STATUS_SUSPENDED:
        return '已暂停，待评估后决定'
    return ''


def _get_overdue_info(record, now):
    cycle = record.glaze_color.retest_cycle_days
    record_status = record.status

    if record_status in (FiringRecord.STATUS_PENDING, FiringRecord.STATUS_FIRING):
        return None, None, False

    if not record.kiln_out_time:
        return None, None, False

    deadline = record.kiln_out_time + timezone.timedelta(days=cycle)
    days_diff = (deadline - now).days

    if record_status in (FiringRecord.STATUS_APPROVED, FiringRecord.STATUS_SUSPENDED):
        return None, None, False

    if days_diff >= 0:
        return days_diff, None, False
    else:
        return None, abs(days_diff), True


def _get_time_nodes(record):
    nodes = [
        {'node_key': 'pending', 'node_name': '创建', 'time': record.created_at, 'completed': True},
        {'node_key': 'kiln_in', 'node_name': '入窑', 'time': record.kiln_in_time, 'completed': record.kiln_in_time is not None},
        {'node_key': 'kiln_out', 'node_name': '出窑', 'time': record.kiln_out_time, 'completed': record.kiln_out_time is not None},
        {'node_key': 'retest', 'node_name': '复测', 'time': record.retest_time, 'completed': record.retest_time is not None},
        {'node_key': 'adjust', 'node_name': '调整', 'time': record.adjust_time, 'completed': record.adjust_time is not None},
    ]
    if record.status == FiringRecord.STATUS_APPROVED:
        nodes.append({'node_key': 'approve', 'node_name': '定样', 'time': record.approve_time, 'completed': True})
    if record.status == FiringRecord.STATUS_SUSPENDED:
        nodes.append({'node_key': 'suspend', 'node_name': '暂停', 'time': record.suspend_time, 'completed': True})
    return nodes


def _get_next_actions(record):
    actions = []
    status = record.status

    actions.append({
        'action_key': 'kiln_in',
        'action_name': '入窑',
        'enabled': status == FiringRecord.STATUS_PENDING,
        'reason': '' if status == FiringRecord.STATUS_PENDING else '仅待试烧状态可入窑',
    })
    actions.append({
        'action_key': 'kiln_out',
        'action_name': '出窑',
        'enabled': status == FiringRecord.STATUS_FIRING,
        'reason': '' if status == FiringRecord.STATUS_FIRING else '仅试烧中状态可出窑',
    })
    actions.append({
        'action_key': 'retest',
        'action_name': '复测',
        'enabled': status in (FiringRecord.STATUS_PENDING_RETEST, FiringRecord.STATUS_ADJUSTING),
        'reason': '' if status in (FiringRecord.STATUS_PENDING_RETEST, FiringRecord.STATUS_ADJUSTING) else '仅待复测或调整中状态可复测',
    })
    actions.append({
        'action_key': 'adjust',
        'action_name': '调整',
        'enabled': status in (FiringRecord.STATUS_PENDING_RETEST, FiringRecord.STATUS_RETESTED, FiringRecord.STATUS_ADJUSTING),
        'reason': '' if status in (FiringRecord.STATUS_PENDING_RETEST, FiringRecord.STATUS_RETESTED, FiringRecord.STATUS_ADJUSTING) else '仅待复测、已复测或调整中状态可调整',
    })
    actions.append({
        'action_key': 'approve',
        'action_name': '定样',
        'enabled': status in (FiringRecord.STATUS_RETESTED, FiringRecord.STATUS_ADJUSTING) and bool(record.retest_conclusion),
        'reason': '' if (status in (FiringRecord.STATUS_RETESTED, FiringRecord.STATUS_ADJUSTING) and bool(record.retest_conclusion)) else '需已复测且有复测结论才可定样',
    })
    actions.append({
        'action_key': 'suspend',
        'action_name': '暂停',
        'enabled': status != FiringRecord.STATUS_SUSPENDED,
        'reason': '' if status != FiringRecord.STATUS_SUSPENDED else '已处于暂停状态',
    })

    return actions


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def closed_loop_tasks(request):
    now = timezone.now()
    queryset = FiringRecord.objects.select_related(
        'glaze_color', 'body_type', 'kiln_batch',
        'temperature_zone', 'responsible_person',
    ).all()

    include_terminal = request.query_params.get('include_terminal', 'false')
    if include_terminal.lower() not in ('true', '1', 'yes'):
        queryset = queryset.exclude(
            status__in=(FiringRecord.STATUS_APPROVED, FiringRecord.STATUS_SUSPENDED)
        )

    responsible_person_id = request.query_params.get('responsible_person')
    if responsible_person_id:
        queryset = queryset.filter(responsible_person_id=responsible_person_id)

    glaze_color_id = request.query_params.get('glaze_color')
    if glaze_color_id:
        queryset = queryset.filter(glaze_color_id=glaze_color_id)

    status_val = request.query_params.get('status')
    if status_val:
        queryset = queryset.filter(status=status_val)

    is_overdue = request.query_params.get('is_overdue')
    if is_overdue is not None and is_overdue != '':
        is_overdue_bool = is_overdue.lower() in ('true', '1', 'yes')
        overdue_ids = []
        for r in queryset:
            _, _, overdue = _get_overdue_info(r, now)
            if overdue == is_overdue_bool:
                overdue_ids.append(r.id)
        queryset = queryset.filter(id__in=overdue_ids)

    date_from = request.query_params.get('kiln_date_from')
    if date_from:
        queryset = queryset.filter(kiln_batch__firing_date__gte=date_from)

    date_to = request.query_params.get('kiln_date_to')
    if date_to:
        queryset = queryset.filter(kiln_batch__firing_date__lte=date_to)

    ordering = request.query_params.get('ordering', '-kiln_out_time')
    if ordering == 'overdue_days':
        records_with_days = []
        for r in queryset:
            remaining, overdue_days, overdue = _get_overdue_info(r, now)
            records_with_days.append((r, overdue_days or 0))
        records_with_days.sort(key=lambda x: x[1], reverse=True)
        records = [r for r, _ in records_with_days]
    elif ordering == '-overdue_days':
        records_with_days = []
        for r in queryset:
            remaining, overdue_days, overdue = _get_overdue_info(r, now)
            records_with_days.append((r, overdue_days or 0))
        records_with_days.sort(key=lambda x: x[1])
        records = [r for r, _ in records_with_days]
    else:
        queryset = queryset.order_by(ordering)
        records = list(queryset)

    results = []
    for r in records:
        remaining_days, overdue_days, is_overdue_flag = _get_overdue_info(r, now)
        current_node_key = NODE_MAP.get(r.status, r.status)
        results.append({
            'id': r.id,
            'glaze_color_id': r.glaze_color_id,
            'glaze_color_code': r.glaze_color.code,
            'glaze_color_name': r.glaze_color.name,
            'body_type_id': r.body_type_id,
            'body_type_name': r.body_type.name,
            'kiln_batch_id': r.kiln_batch_id,
            'kiln_batch_code': r.kiln_batch.batch_code,
            'kiln_batch_date': r.kiln_batch.firing_date,
            'trial_sequence': r.trial_sequence,
            'temperature_zone_id': r.temperature_zone_id,
            'temperature_zone_name': r.temperature_zone.name,
            'responsible_person_id': r.responsible_person_id,
            'responsible_person_name': r.responsible_person.name,
            'status': r.status,
            'status_display': r.get_status_display(),
            'current_node': current_node_key,
            'remaining_days': remaining_days,
            'overdue_days': overdue_days,
            'is_overdue': is_overdue_flag,
            'anomaly_summary': _get_anomaly_summary(r),
            'suggested_action': _get_suggested_action(r),
            'adjust_count': r.adjust_count,
            'kiln_out_time': r.kiln_out_time,
            'retest_cycle_days': r.glaze_color.retest_cycle_days,
        })

    serializer = ClosedLoopTaskSerializer(results, many=True)
    return Response({
        'count': len(results),
        'results': serializer.data,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def closed_loop_detail(request, pk):
    try:
        record = FiringRecord.objects.select_related(
            'glaze_color', 'body_type', 'kiln_batch',
            'temperature_zone', 'responsible_person',
        ).get(pk=pk)
    except FiringRecord.DoesNotExist:
        return Response(
            {'detail': '记录不存在'},
            status=status.HTTP_404_NOT_FOUND,
        )

    now = timezone.now()
    remaining_days, overdue_days, is_overdue_flag = _get_overdue_info(record, now)
    current_node_key = NODE_MAP.get(record.status, record.status)

    basic_info = {
        'id': record.id,
        'glaze_color': {
            'id': record.glaze_color_id,
            'code': record.glaze_color.code,
            'name': record.glaze_color.name,
        },
        'body_type': {
            'id': record.body_type_id,
            'name': record.body_type.name,
        },
        'kiln_batch': {
            'id': record.kiln_batch_id,
            'batch_code': record.kiln_batch.batch_code,
            'firing_date': record.kiln_batch.firing_date,
        },
        'trial_sequence': record.trial_sequence,
        'temperature_zone': {
            'id': record.temperature_zone_id,
            'name': record.temperature_zone.name,
        },
        'responsible_person': {
            'id': record.responsible_person_id,
            'name': record.responsible_person.name,
            'contact': record.responsible_person.contact,
        },
        'status': record.status,
        'status_display': record.get_status_display(),
    }

    quality_anomaly = {
        'color_difference': record.color_difference,
        'color_difference_display': record.get_color_difference_display(),
        'pinhole_condition': record.pinhole_condition,
        'pinhole_condition_display': record.get_pinhole_condition_display(),
        'glaze_flow_desc': record.glaze_flow_desc,
        'anomaly_summary': _get_anomaly_summary(record),
    }

    time_nodes = _get_time_nodes(record)
    next_actions = _get_next_actions(record)

    data = {
        'id': record.id,
        'basic_info': basic_info,
        'quality_anomaly': quality_anomaly,
        'retest_conclusion': record.retest_conclusion,
        'handling_suggestion': record.handling_suggestion,
        'time_nodes': time_nodes,
        'next_actions': next_actions,
        'adjust_count': record.adjust_count,
        'current_node': current_node_key,
        'is_overdue': is_overdue_flag,
        'remaining_days': remaining_days,
        'overdue_days': overdue_days,
    }

    serializer = ClosedLoopDetailSerializer(data)
    return Response(serializer.data)


def _create_rectification_history(order, action, operator_name='', description=''):
    previous_status = order.status
    history = RectificationHistory.objects.create(
        rectification_order=order,
        action=action,
        operator_name=operator_name,
        description=description,
        previous_status=previous_status,
        current_status=order.status,
    )
    return history


class RectificationOrderFilter(django_filters.FilterSet):
    date_from = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    date_to = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')
    planned_from = django_filters.DateFilter(field_name='planned_completion_date', lookup_expr='gte')
    planned_to = django_filters.DateFilter(field_name='planned_completion_date', lookup_expr='lte')
    is_overdue = django_filters.BooleanFilter(method='filter_is_overdue')
    body_type = django_filters.ModelChoiceFilter(
        field_name='firing_record__body_type',
        queryset=BodyType.objects.all()
    )
    temperature_zone = django_filters.ModelChoiceFilter(
        field_name='firing_record__temperature_zone',
        queryset=TemperatureZone.objects.all()
    )

    class Meta:
        model = RectificationOrder
        fields = {
            'firing_record': ['exact'],
            'firing_record__glaze_color': ['exact'],
            'firing_record__body_type': ['exact'],
            'firing_record__kiln_batch': ['exact'],
            'firing_record__temperature_zone': ['exact'],
            'responsible_person': ['exact'],
            'status': ['exact'],
            'anomaly_type': ['exact'],
            'cause_category': ['exact'],
        }

    def filter_is_overdue(self, queryset, name, value):
        from django.utils import timezone
        today = timezone.now().date()
        if value:
            return queryset.filter(
                status__in=[
                    RectificationOrder.STATUS_PENDING_ANALYSIS,
                    RectificationOrder.STATUS_RECTIFYING,
                    RectificationOrder.STATUS_PENDING_CONFIRM,
                ],
                planned_completion_date__lt=today,
            )
        else:
            return queryset.exclude(
                status__in=[
                    RectificationOrder.STATUS_PENDING_ANALYSIS,
                    RectificationOrder.STATUS_RECTIFYING,
                    RectificationOrder.STATUS_PENDING_CONFIRM,
                ],
                planned_completion_date__lt=today,
            )


class RectificationOrderViewSet(viewsets.ModelViewSet):
    queryset = RectificationOrder.objects.select_related(
        'firing_record', 'firing_record__glaze_color', 'firing_record__body_type',
        'firing_record__kiln_batch', 'firing_record__temperature_zone',
        'firing_record__responsible_person', 'responsible_person',
    ).prefetch_related(
        'history_records',
    ).all()
    filterset_class = RectificationOrderFilter
    search_fields = ['order_no', 'anomaly_description', 'rectification_measures']
    ordering_fields = [
        'created_at', 'planned_completion_date', 'status',
        'close_time', 'updated_at',
    ]

    def get_serializer_class(self):
        if self.action == 'list':
            return RectificationOrderListSerializer
        if self.action == 'retrieve':
            return RectificationOrderDetailSerializer
        if self.action == 'create':
            return RectificationOrderCreateSerializer
        if self.action in ('update', 'partial_update'):
            return RectificationOrderUpdateSerializer
        if self.action == 'history':
            return RectificationHistorySerializer
        if self.action == 'reject':
            return RectificationRejectSerializer
        return RectificationOrderDetailSerializer

    def get_operator_name(self, request):
        if request.user and request.user.is_authenticated:
            return request.user.get_full_name() or request.user.username
        return ''

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        instance = serializer.instance
        operator_name = self.get_operator_name(request)
        _create_rectification_history(
            instance,
            RectificationHistory.ACTION_CREATE,
            operator_name,
            f'创建整改单，异常类型：{instance.get_anomaly_type_display()}'
        )
        detail_serializer = RectificationOrderDetailSerializer(instance)
        return Response(detail_serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        operator_name = self.get_operator_name(request)
        _create_rectification_history(
            instance,
            RectificationHistory.ACTION_UPDATE,
            operator_name,
            '更新整改单信息'
        )
        detail_serializer = RectificationOrderDetailSerializer(instance)
        return Response(detail_serializer.data)

    @action(detail=True, methods=['get'], url_path='history')
    def history(self, request, pk=None):
        order = self.get_object()
        history_records = order.history_records.all()
        serializer = RectificationHistorySerializer(history_records, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='add-history')
    def add_history(self, request, pk=None):
        order = self.get_object()
        data = request.data.copy()
        data['rectification_order'] = order.id
        operator_name = self.get_operator_name(request)
        if 'operator_name' not in data or not data['operator_name']:
            data['operator_name'] = operator_name
        serializer = RectificationHistoryCreateSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save(
            previous_status=order.status,
            current_status=order.status,
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='analyze')
    def analyze(self, request, pk=None):
        order = self.get_object()
        if order.status != RectificationOrder.STATUS_PENDING_ANALYSIS:
            return Response(
                {'detail': f'当前状态为"{order.get_status_display()}"，只有"待分析"状态可执行分析操作'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = RectificationAnalyzeSerializer(instance=order, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        operator_name = self.get_operator_name(request)
        _create_rectification_history(
            order,
            RectificationHistory.ACTION_ANALYZE,
            operator_name,
            f'完成原因分析，原因分类：{order.get_cause_category_display()}'
        )
        return Response(RectificationOrderDetailSerializer(order).data)

    @action(detail=True, methods=['post'], url_path='submit')
    def submit(self, request, pk=None):
        order = self.get_object()
        if order.status != RectificationOrder.STATUS_RECTIFYING:
            return Response(
                {'detail': f'当前状态为"{order.get_status_display()}"，只有"整改中"状态可提交整改结果'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = RectificationSubmitSerializer(instance=order, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        operator_name = self.get_operator_name(request)
        _create_rectification_history(
            order,
            RectificationHistory.ACTION_SUBMIT,
            operator_name,
            '提交整改结果，等待确认'
        )
        return Response(RectificationOrderDetailSerializer(order).data)

    @action(detail=True, methods=['post'], url_path='confirm')
    def confirm(self, request, pk=None):
        order = self.get_object()
        if order.status != RectificationOrder.STATUS_PENDING_CONFIRM:
            return Response(
                {'detail': f'当前状态为"{order.get_status_display()}"，只有"待确认"状态可执行确认关闭操作'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = RectificationConfirmSerializer(instance=order, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        operator_name = self.get_operator_name(request)
        _create_rectification_history(
            order,
            RectificationHistory.ACTION_CONFIRM,
            operator_name,
            '确认整改完成，关闭整改单'
        )
        return Response(RectificationOrderDetailSerializer(order).data)

    @action(detail=True, methods=['post'], url_path='reopen')
    def reopen(self, request, pk=None):
        order = self.get_object()
        if order.status != RectificationOrder.STATUS_CLOSED:
            return Response(
                {'detail': f'当前状态为"{order.get_status_display()}"，只有"已关闭"状态可重新打开'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = RectificationReopenSerializer(instance=order, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        operator_name = self.get_operator_name(request)
        reason = request.data.get('reason', '')
        _create_rectification_history(
            order,
            RectificationHistory.ACTION_REOPEN,
            operator_name,
            f'退回继续整改，原因：{reason}'
        )
        return Response(RectificationOrderDetailSerializer(order).data)

    @action(detail=True, methods=['post'], url_path='reject')
    def reject(self, request, pk=None):
        order = self.get_object()
        if order.status != RectificationOrder.STATUS_PENDING_CONFIRM:
            return Response(
                {'detail': f'当前状态为"{order.get_status_display()}"，只有"待确认"状态可执行退回操作'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = RectificationRejectSerializer(instance=order, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        operator_name = self.get_operator_name(request)
        reason = request.data.get('reason', '')
        _create_rectification_history(
            order,
            RectificationHistory.ACTION_REOPEN,
            operator_name,
            f'验收不通过，先确认关闭后重新打开整改。退回原因：{reason}'
        )
        _create_rectification_history(
            order,
            RectificationHistory.ACTION_CREATE,
            operator_name,
            f'重新发起整改，原因：{reason}'
        )
        return Response(RectificationOrderDetailSerializer(order).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def rectification_dashboard(request):
    from django.utils import timezone
    now = timezone.now()
    today = now.date()

    pending_total_count = RectificationOrder.objects.filter(
        status__in=[
            RectificationOrder.STATUS_PENDING_ANALYSIS,
            RectificationOrder.STATUS_RECTIFYING,
            RectificationOrder.STATUS_PENDING_CONFIRM,
        ]
    ).count()

    pending_count = RectificationOrder.objects.filter(
        status=RectificationOrder.STATUS_PENDING_ANALYSIS
    ).count()

    rectifying_count = RectificationOrder.objects.filter(
        status=RectificationOrder.STATUS_RECTIFYING
    ).count()

    pending_confirm_count = RectificationOrder.objects.filter(
        status=RectificationOrder.STATUS_PENDING_CONFIRM
    ).count()

    closed_count = RectificationOrder.objects.filter(
        status=RectificationOrder.STATUS_CLOSED
    ).count()

    active_orders = RectificationOrder.objects.filter(
        status__in=[
            RectificationOrder.STATUS_PENDING_ANALYSIS,
            RectificationOrder.STATUS_RECTIFYING,
            RectificationOrder.STATUS_PENDING_CONFIRM,
        ],
        planned_completion_date__lt=today,
    )

    total_overdue_count = active_orders.count()
    pending_overdue_count = active_orders.filter(
        status=RectificationOrder.STATUS_PENDING_ANALYSIS
    ).count()
    rectifying_overdue_count = active_orders.filter(
        status=RectificationOrder.STATUS_RECTIFYING
    ).count()

    recently_closed = RectificationOrder.objects.select_related(
        'firing_record', 'firing_record__glaze_color', 'firing_record__kiln_batch',
        'responsible_person',
    ).filter(
        status=RectificationOrder.STATUS_CLOSED
    ).order_by('-close_time')[:10]

    data = {
        'pending_total_count': pending_total_count,
        'pending_count': pending_count,
        'rectifying_count': rectifying_count,
        'pending_confirm_count': pending_confirm_count,
        'closed_count': closed_count,
        'total_overdue_count': total_overdue_count,
        'pending_overdue_count': pending_overdue_count,
        'rectifying_overdue_count': rectifying_overdue_count,
        'recently_closed': recently_closed,
    }

    serializer = RectificationDashboardSerializer(data)
    return Response(serializer.data)


ANOMALY_TYPE_MAP = {
    RectificationOrder.ANOMALY_COLOR_DIFF_HIGH: '色差偏高',
    RectificationOrder.ANOMALY_COLOR_DIFF_SEVERE: '色差严重',
    RectificationOrder.ANOMALY_PINHOLE_MODERATE: '针孔中等',
    RectificationOrder.ANOMALY_PINHOLE_SEVERE: '针孔严重',
    RectificationOrder.ANOMALY_SUSPENDED: '暂停使用',
    RectificationOrder.ANOMALY_RETEST_OVERDUE: '复测超期',
}


def _get_active_rectification(firing_record_id, anomaly_type):
    active = RectificationOrder.objects.filter(
        firing_record_id=firing_record_id,
        anomaly_type=anomaly_type,
        status__in=[
            RectificationOrder.STATUS_PENDING_ANALYSIS,
            RectificationOrder.STATUS_RECTIFYING,
            RectificationOrder.STATUS_PENDING_CONFIRM,
        ],
    ).first()
    if active:
        return {
            'id': active.id,
            'status': active.status,
            'status_display': active.get_status_display(),
        }
    return None


def _get_latest_rectification(firing_record_id, anomaly_type):
    latest = RectificationOrder.objects.filter(
        firing_record_id=firing_record_id,
        anomaly_type=anomaly_type,
    ).order_by('-created_at').first()
    if latest:
        return {
            'id': latest.id,
            'status': latest.status,
            'status_display': latest.get_status_display(),
        }
    return None


def _has_closed_rectification(firing_record_id, anomaly_type):
    return RectificationOrder.objects.filter(
        firing_record_id=firing_record_id,
        anomaly_type=anomaly_type,
        status=RectificationOrder.STATUS_CLOSED,
    ).exists()


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def pending_abnormal_list(request):
    from django.utils import timezone
    now = timezone.now()

    anomaly_type = request.query_params.get('anomaly_type', '')
    glaze_color_id = request.query_params.get('glaze_color')
    body_type_id = request.query_params.get('body_type')
    kiln_batch_id = request.query_params.get('kiln_batch')
    temperature_zone_id = request.query_params.get('temperature_zone')
    responsible_person_id = request.query_params.get('responsible_person')
    has_rectification = request.query_params.get('has_rectification', '')
    rectification_status = request.query_params.get('rectification_status', '')
    exclude_closed = request.query_params.get('exclude_closed', 'true')

    results = []

    firing_records_qs = FiringRecord.objects.select_related(
        'glaze_color', 'body_type', 'kiln_batch',
        'temperature_zone', 'responsible_person',
    ).all()

    if glaze_color_id:
        firing_records_qs = firing_records_qs.filter(glaze_color_id=glaze_color_id)
    if body_type_id:
        firing_records_qs = firing_records_qs.filter(body_type_id=body_type_id)
    if kiln_batch_id:
        firing_records_qs = firing_records_qs.filter(kiln_batch_id=kiln_batch_id)
    if temperature_zone_id:
        firing_records_qs = firing_records_qs.filter(temperature_zone_id=temperature_zone_id)
    if responsible_person_id:
        firing_records_qs = firing_records_qs.filter(responsible_person_id=responsible_person_id)

    for record in firing_records_qs:
        anomalies = []

        if not anomaly_type or anomaly_type == RectificationOrder.ANOMALY_COLOR_DIFF_HIGH:
            if record.color_difference == FiringRecord.COLOR_DIFF_HIGH:
                anomalies.append((
                    RectificationOrder.ANOMALY_COLOR_DIFF_HIGH,
                    '色差偏高，需调整配方或工艺',
                ))

        if not anomaly_type or anomaly_type == RectificationOrder.ANOMALY_COLOR_DIFF_SEVERE:
            if record.color_difference == FiringRecord.COLOR_DIFF_SEVERE:
                anomalies.append((
                    RectificationOrder.ANOMALY_COLOR_DIFF_SEVERE,
                    '色差严重，需紧急整改',
                ))

        if not anomaly_type or anomaly_type == RectificationOrder.ANOMALY_PINHOLE_MODERATE:
            if record.pinhole_condition == FiringRecord.PINHOLE_MODERATE:
                anomalies.append((
                    RectificationOrder.ANOMALY_PINHOLE_MODERATE,
                    '针孔中等，需排查原因',
                ))

        if not anomaly_type or anomaly_type == RectificationOrder.ANOMALY_PINHOLE_SEVERE:
            if record.pinhole_condition == FiringRecord.PINHOLE_SEVERE:
                anomalies.append((
                    RectificationOrder.ANOMALY_PINHOLE_SEVERE,
                    '针孔严重，需紧急整改',
                ))

        if not anomaly_type or anomaly_type == RectificationOrder.ANOMALY_SUSPENDED:
            if record.status == FiringRecord.STATUS_SUSPENDED:
                anomalies.append((
                    RectificationOrder.ANOMALY_SUSPENDED,
                    '已暂停使用，需评估整改',
                ))

        if not anomaly_type or anomaly_type == RectificationOrder.ANOMALY_RETEST_OVERDUE:
            if record.status in (FiringRecord.STATUS_PENDING_RETEST, FiringRecord.STATUS_ADJUSTING):
                if record.kiln_out_time and not record.retest_conclusion:
                    cycle = record.glaze_color.retest_cycle_days
                    days_since = (now - record.kiln_out_time).days
                    if days_since > cycle:
                        anomalies.append((
                            RectificationOrder.ANOMALY_RETEST_OVERDUE,
                            f'复测已超期{days_since - cycle}天，需尽快复测',
                        ))

        for atype, adesc in anomalies:
            if exclude_closed.lower() in ('true', '1', 'yes'):
                if _has_closed_rectification(record.id, atype):
                    continue

            active_rect = _get_active_rectification(record.id, atype)
            latest_rect = _get_latest_rectification(record.id, atype)
            has_active = active_rect is not None
            rect_status = latest_rect['status'] if latest_rect else None

            if has_rectification == 'true' and not has_active:
                continue
            if has_rectification == 'false' and has_active:
                continue

            if rectification_status:
                status_list = rectification_status.split(',')
                if rect_status and rect_status not in status_list:
                    continue
                if not rect_status and 'none' not in status_list:
                    continue

            results.append({
                'firing_record_id': record.id,
                'glaze_color_id': record.glaze_color_id,
                'glaze_color_code': record.glaze_color.code,
                'glaze_color_name': record.glaze_color.name,
                'body_type_id': record.body_type_id,
                'body_type_name': record.body_type.name,
                'kiln_batch_id': record.kiln_batch_id,
                'kiln_batch_code': record.kiln_batch.batch_code,
                'kiln_batch_date': record.kiln_batch.firing_date,
                'trial_sequence': record.trial_sequence,
                'temperature_zone_id': record.temperature_zone_id,
                'temperature_zone_name': record.temperature_zone.name,
                'responsible_person_id': record.responsible_person_id,
                'responsible_person_name': record.responsible_person.name,
                'anomaly_type': atype,
                'anomaly_type_display': ANOMALY_TYPE_MAP.get(atype, atype),
                'anomaly_description': adesc,
                'has_active_rectification': has_active,
                'active_rectification_id': active_rect['id'] if active_rect else None,
                'active_rectification_status': active_rect['status'] if active_rect else None,
                'active_rectification_status_display': active_rect['status_display'] if active_rect else None,
                'latest_rectification_id': latest_rect['id'] if latest_rect else None,
                'latest_rectification_status': latest_rect['status'] if latest_rect else None,
                'latest_rectification_status_display': latest_rect['status_display'] if latest_rect else None,
                'created_at': record.created_at,
            })

    ordering = request.query_params.get('ordering', '-created_at')
    if ordering == 'anomaly_type':
        results.sort(key=lambda x: x['anomaly_type'])
    elif ordering == '-anomaly_type':
        results.sort(key=lambda x: x['anomaly_type'], reverse=True)
    elif ordering == 'glaze_color_code':
        results.sort(key=lambda x: x['glaze_color_code'])
    elif ordering == '-glaze_color_code':
        results.sort(key=lambda x: x['glaze_color_code'], reverse=True)
    elif ordering == 'has_active_rectification':
        results.sort(key=lambda x: x['has_active_rectification'])
    elif ordering == '-has_active_rectification':
        results.sort(key=lambda x: x['has_active_rectification'], reverse=True)
    elif ordering == 'created_at':
        results.sort(key=lambda x: x['created_at'])
    else:
        results.sort(key=lambda x: x['created_at'], reverse=True)

    serializer = PendingAbnormalItemSerializer(results, many=True)
    return Response({
        'count': len(results),
        'results': serializer.data,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def abnormal_summary(request):
    from django.utils import timezone
    now = timezone.now()

    color_diff_high = FiringRecord.objects.filter(
        color_difference=FiringRecord.COLOR_DIFF_HIGH
    ).count()
    color_diff_severe = FiringRecord.objects.filter(
        color_difference=FiringRecord.COLOR_DIFF_SEVERE
    ).count()
    pinhole_moderate = FiringRecord.objects.filter(
        pinhole_condition=FiringRecord.PINHOLE_MODERATE
    ).count()
    pinhole_severe = FiringRecord.objects.filter(
        pinhole_condition=FiringRecord.PINHOLE_SEVERE
    ).count()
    suspended = FiringRecord.objects.filter(
        status=FiringRecord.STATUS_SUSPENDED
    ).count()

    retest_overdue = 0
    overdue_records = FiringRecord.objects.filter(
        status__in=(FiringRecord.STATUS_PENDING_RETEST, FiringRecord.STATUS_ADJUSTING),
        kiln_out_time__isnull=False,
        retest_conclusion='',
    ).select_related('glaze_color')
    for r in overdue_records:
        cycle = r.glaze_color.retest_cycle_days
        days_since = (now - r.kiln_out_time).days
        if days_since > cycle:
            retest_overdue += 1

    pending_total = RectificationOrder.objects.filter(
        status__in=[
            RectificationOrder.STATUS_PENDING_ANALYSIS,
            RectificationOrder.STATUS_RECTIFYING,
            RectificationOrder.STATUS_PENDING_CONFIRM,
        ]
    ).count()

    today = now.date()
    overdue = RectificationOrder.objects.filter(
        status__in=[
            RectificationOrder.STATUS_PENDING_ANALYSIS,
            RectificationOrder.STATUS_RECTIFYING,
            RectificationOrder.STATUS_PENDING_CONFIRM,
        ],
        planned_completion_date__lt=today,
    ).count()

    processing = RectificationOrder.objects.filter(
        status=RectificationOrder.STATUS_RECTIFYING
    ).count()

    closed = RectificationOrder.objects.filter(
        status=RectificationOrder.STATUS_CLOSED
    ).count()

    return Response({
        'anomaly_counts': {
            'color_diff_high': color_diff_high,
            'color_diff_severe': color_diff_severe,
            'pinhole_moderate': pinhole_moderate,
            'pinhole_severe': pinhole_severe,
            'suspended': suspended,
            'retest_overdue': retest_overdue,
        },
        'rectification_counts': {
            'pending_total': pending_total,
            'overdue': overdue,
            'processing': processing,
            'closed': closed,
        },
    })
