from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import (
    BodyType, FiringRecord, GlazeColor, KilnBatch,
    RectificationOrder, ResponsiblePerson, TemperatureZone,
)


class FiringRecordRetestFlowTests(APITestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(username='tester', password='Pass123456')
        token_response = self.client.post(
            reverse('token_obtain_pair'),
            {'username': 'tester', 'password': 'Pass123456'},
            format='json',
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token_response.data['access']}")

        self.glaze_color = GlazeColor.objects.create(code='GC-T1', name='Test Glaze', retest_cycle_days=7)
        self.body_type = BodyType.objects.create(code='BT-T1', name='Test Body')
        self.kiln_batch = KilnBatch.objects.create(batch_code='KB-T1', firing_date='2026-06-16')
        self.temperature_zone = TemperatureZone.objects.create(
            zone_code='TZ-T1',
            name='Test Zone',
            temperature_range='1200-1220',
        )
        self.responsible_person = ResponsiblePerson.objects.create(name='Tester')

    def test_retest_moves_record_out_of_pending_states(self):
        record = FiringRecord.objects.create(
            glaze_color=self.glaze_color,
            body_type=self.body_type,
            kiln_batch=self.kiln_batch,
            trial_sequence=1,
            temperature_zone=self.temperature_zone,
            responsible_person=self.responsible_person,
            status=FiringRecord.STATUS_ADJUSTING,
            kiln_out_time='2026-06-16T09:00:00+08:00',
        )

        retest_response = self.client.post(
            f'/api/firing-records/{record.id}/retest/',
            {'retest_conclusion': '复测通过'},
            format='json',
        )
        self.assertEqual(retest_response.status_code, status.HTTP_200_OK)
        self.assertEqual(retest_response.data['status'], FiringRecord.STATUS_RETESTED)

        pending_response = self.client.get('/api/stats/pending-retest/')
        self.assertEqual(pending_response.status_code, status.HTTP_200_OK)
        self.assertFalse(any(item['id'] == record.id for item in pending_response.data))

    def test_retested_record_can_be_approved(self):
        record = FiringRecord.objects.create(
            glaze_color=self.glaze_color,
            body_type=self.body_type,
            kiln_batch=self.kiln_batch,
            trial_sequence=2,
            temperature_zone=self.temperature_zone,
            responsible_person=self.responsible_person,
            status=FiringRecord.STATUS_RETESTED,
            kiln_out_time='2026-06-16T09:00:00+08:00',
            retest_conclusion='复测通过',
        )

        approve_response = self.client.post(f'/api/firing-records/{record.id}/approve/', {}, format='json')
        self.assertEqual(approve_response.status_code, status.HTTP_200_OK)
        self.assertEqual(approve_response.data['status'], FiringRecord.STATUS_APPROVED)


class RectificationOrderTests(APITestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(username='rectifier', password='Pass123456')
        token_response = self.client.post(
            reverse('token_obtain_pair'),
            {'username': 'rectifier', 'password': 'Pass123456'},
            format='json',
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token_response.data['access']}")

        self.glaze_color = GlazeColor.objects.create(code='GC-R1', name='Rectify Glaze', retest_cycle_days=7)
        self.body_type = BodyType.objects.create(code='BT-R1', name='Rectify Body')
        self.kiln_batch = KilnBatch.objects.create(batch_code='KB-R1', firing_date='2026-06-16')
        self.temperature_zone = TemperatureZone.objects.create(
            zone_code='TZ-R1',
            name='Rectify Zone',
            temperature_range='1200-1220',
        )
        self.responsible_person = ResponsiblePerson.objects.create(name='Rectifier')

    def test_duplicate_active_rectification_order_is_rejected(self):
        record = FiringRecord.objects.create(
            glaze_color=self.glaze_color,
            body_type=self.body_type,
            kiln_batch=self.kiln_batch,
            trial_sequence=11,
            temperature_zone=self.temperature_zone,
            responsible_person=self.responsible_person,
            status=FiringRecord.STATUS_PENDING_RETEST,
            kiln_out_time='2026-06-16T09:00:00+08:00',
            color_difference=FiringRecord.COLOR_DIFF_HIGH,
        )

        payload = {
            'firing_record': record.id,
            'anomaly_type': RectificationOrder.ANOMALY_COLOR_DIFF_HIGH,
            'anomaly_description': '色差偏高，需复盘整改',
            'cause_category': RectificationOrder.CAUSE_PROCESS,
            'cause_detail': '工艺波动',
            'responsible_person': self.responsible_person.id,
            'rectification_measures': '调整工艺参数',
            'planned_completion_date': '2026-06-20',
        }

        first_response = self.client.post('/api/rectification-orders/', payload, format='json')
        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)

        second_response = self.client.post('/api/rectification-orders/', payload, format='json')
        self.assertEqual(second_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('anomaly_type', second_response.data)

    def test_firing_record_detail_returns_all_rectification_orders(self):
        record = FiringRecord.objects.create(
            glaze_color=self.glaze_color,
            body_type=self.body_type,
            kiln_batch=self.kiln_batch,
            trial_sequence=12,
            temperature_zone=self.temperature_zone,
            responsible_person=self.responsible_person,
            status=FiringRecord.STATUS_SUSPENDED,
            kiln_out_time='2026-06-16T09:00:00+08:00',
            suspend_time='2026-06-17T09:00:00+08:00',
        )

        for index in range(6):
            RectificationOrder.objects.create(
                order_no=f'ZG20260616{index + 1:04d}',
                firing_record=record,
                anomaly_type=RectificationOrder.ANOMALY_SUSPENDED,
                anomaly_description=f'暂停整改 {index + 1}',
                responsible_person=self.responsible_person,
                planned_completion_date='2026-06-20',
                status=RectificationOrder.STATUS_CLOSED if index == 5 else RectificationOrder.STATUS_PENDING_ANALYSIS,
            )

        response = self.client.get(f'/api/firing-records/{record.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['rectification_count'], 6)
        self.assertEqual(len(response.data['rectification_orders']), 6)

    def test_dashboard_returns_pending_total_count(self):
        record = FiringRecord.objects.create(
            glaze_color=self.glaze_color,
            body_type=self.body_type,
            kiln_batch=self.kiln_batch,
            trial_sequence=13,
            temperature_zone=self.temperature_zone,
            responsible_person=self.responsible_person,
            status=FiringRecord.STATUS_PENDING_RETEST,
            kiln_out_time='2026-06-16T09:00:00+08:00',
            color_difference=FiringRecord.COLOR_DIFF_SEVERE,
        )

        RectificationOrder.objects.create(
            order_no='ZG202606160101',
            firing_record=record,
            anomaly_type=RectificationOrder.ANOMALY_COLOR_DIFF_SEVERE,
            anomaly_description='严重色差整改',
            responsible_person=self.responsible_person,
            planned_completion_date='2026-06-20',
            status=RectificationOrder.STATUS_PENDING_ANALYSIS,
        )
        RectificationOrder.objects.create(
            order_no='ZG202606160102',
            firing_record=record,
            anomaly_type=RectificationOrder.ANOMALY_COLOR_DIFF_HIGH,
            anomaly_description='色差偏高整改',
            responsible_person=self.responsible_person,
            planned_completion_date='2026-06-20',
            status=RectificationOrder.STATUS_RECTIFYING,
        )
        RectificationOrder.objects.create(
            order_no='ZG202606160103',
            firing_record=record,
            anomaly_type=RectificationOrder.ANOMALY_SUSPENDED,
            anomaly_description='暂停后关闭',
            responsible_person=self.responsible_person,
            planned_completion_date='2026-06-20',
            status=RectificationOrder.STATUS_CLOSED,
            close_time='2026-06-18T09:00:00+08:00',
        )

        response = self.client.get('/api/stats/rectification-dashboard/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['pending_total_count'], 2)
        self.assertEqual(response.data['closed_count'], 1)
