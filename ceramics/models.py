from django.db import models


class GlazeColor(models.Model):
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, default='')
    retest_cycle_days = models.IntegerField(default=30)

    class Meta:
        ordering = ['code']

    def __str__(self):
        return f"{self.code} - {self.name}"


class BodyType(models.Model):
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['code']

    def __str__(self):
        return f"{self.code} - {self.name}"


class KilnBatch(models.Model):
    batch_code = models.CharField(max_length=50, unique=True)
    firing_date = models.DateField()
    notes = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-firing_date', 'batch_code']

    def __str__(self):
        return self.batch_code


class TemperatureZone(models.Model):
    zone_code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    temperature_range = models.CharField(max_length=100)

    class Meta:
        ordering = ['zone_code']

    def __str__(self):
        return f"{self.zone_code} - {self.name}"


class ResponsiblePerson(models.Model):
    name = models.CharField(max_length=100)
    contact = models.CharField(max_length=100, blank=True, default='')

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class FiringRecord(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_FIRING = 'firing'
    STATUS_PENDING_RETEST = 'pending_retest'
    STATUS_ADJUSTING = 'adjusting'
    STATUS_APPROVED = 'approved'
    STATUS_SUSPENDED = 'suspended'

    STATUS_CHOICES = [
        (STATUS_PENDING, '待试烧'),
        (STATUS_FIRING, '试烧中'),
        (STATUS_PENDING_RETEST, '待复测'),
        (STATUS_ADJUSTING, '调整中'),
        (STATUS_APPROVED, '可定样'),
        (STATUS_SUSPENDED, '暂停使用'),
    ]

    COLOR_DIFF_NONE = 'none'
    COLOR_DIFF_SLIGHT = 'slight'
    COLOR_DIFF_HIGH = 'high'
    COLOR_DIFF_SEVERE = 'severe'

    COLOR_DIFF_CHOICES = [
        (COLOR_DIFF_NONE, '无'),
        (COLOR_DIFF_SLIGHT, '轻微'),
        (COLOR_DIFF_HIGH, '偏高'),
        (COLOR_DIFF_SEVERE, '严重'),
    ]

    PINHOLE_NONE = 'none'
    PINHOLE_MINOR = 'minor'
    PINHOLE_MODERATE = 'moderate'
    PINHOLE_SEVERE = 'severe'

    PINHOLE_CHOICES = [
        (PINHOLE_NONE, '无'),
        (PINHOLE_MINOR, '少量'),
        (PINHOLE_MODERATE, '中等'),
        (PINHOLE_SEVERE, '严重'),
    ]

    glaze_color = models.ForeignKey(GlazeColor, on_delete=models.PROTECT, related_name='firing_records')
    body_type = models.ForeignKey(BodyType, on_delete=models.PROTECT, related_name='firing_records')
    kiln_batch = models.ForeignKey(KilnBatch, on_delete=models.PROTECT, related_name='firing_records')
    trial_sequence = models.IntegerField()
    temperature_zone = models.ForeignKey(TemperatureZone, on_delete=models.PROTECT, related_name='firing_records')
    responsible_person = models.ForeignKey(ResponsiblePerson, on_delete=models.PROTECT, related_name='firing_records')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    kiln_in_time = models.DateTimeField(null=True, blank=True)
    kiln_out_time = models.DateTimeField(null=True, blank=True)
    color_difference = models.CharField(max_length=20, choices=COLOR_DIFF_CHOICES, blank=True, default='')
    pinhole_condition = models.CharField(max_length=20, choices=PINHOLE_CHOICES, blank=True, default='')
    glaze_flow_desc = models.TextField(blank=True, default='')
    retest_conclusion = models.TextField(blank=True, default='')
    handling_suggestion = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = [('kiln_batch', 'trial_sequence')]

    def __str__(self):
        return f"{self.kiln_batch.batch_code}-{self.trial_sequence} ({self.glaze_color.code})"
