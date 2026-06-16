from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import BodyType, FiringRecord, GlazeColor, KilnBatch, ResponsiblePerson, TemperatureZone


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
