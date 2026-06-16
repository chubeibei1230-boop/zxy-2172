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
    STATUS_RETESTED = 'retested'
    STATUS_ADJUSTING = 'adjusting'
    STATUS_APPROVED = 'approved'
    STATUS_SUSPENDED = 'suspended'

    STATUS_CHOICES = [
        (STATUS_PENDING, '待试烧'),
        (STATUS_FIRING, '试烧中'),
        (STATUS_PENDING_RETEST, '待复测'),
        (STATUS_RETESTED, '已复测'),
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
    retest_time = models.DateTimeField(null=True, blank=True)
    adjust_time = models.DateTimeField(null=True, blank=True)
    approve_time = models.DateTimeField(null=True, blank=True)
    suspend_time = models.DateTimeField(null=True, blank=True)
    color_difference = models.CharField(max_length=20, choices=COLOR_DIFF_CHOICES, blank=True, default='')
    pinhole_condition = models.CharField(max_length=20, choices=PINHOLE_CHOICES, blank=True, default='')
    glaze_flow_desc = models.TextField(blank=True, default='')
    retest_conclusion = models.TextField(blank=True, default='')
    handling_suggestion = models.TextField(blank=True, default='')
    adjust_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = [('kiln_batch', 'trial_sequence')]

    def __str__(self):
        return f"{self.kiln_batch.batch_code}-{self.trial_sequence} ({self.glaze_color.code})"


class RectificationOrder(models.Model):
    STATUS_PENDING_ANALYSIS = 'pending_analysis'
    STATUS_RECTIFYING = 'rectifying'
    STATUS_PENDING_CONFIRM = 'pending_confirm'
    STATUS_CLOSED = 'closed'

    STATUS_CHOICES = [
        (STATUS_PENDING_ANALYSIS, '待分析'),
        (STATUS_RECTIFYING, '整改中'),
        (STATUS_PENDING_CONFIRM, '待确认'),
        (STATUS_CLOSED, '已关闭'),
    ]

    ANOMALY_COLOR_DIFF_HIGH = 'color_diff_high'
    ANOMALY_COLOR_DIFF_SEVERE = 'color_diff_severe'
    ANOMALY_PINHOLE_MODERATE = 'pinhole_moderate'
    ANOMALY_PINHOLE_SEVERE = 'pinhole_severe'
    ANOMALY_SUSPENDED = 'suspended'
    ANOMALY_RETEST_OVERDUE = 'retest_overdue'

    ANOMALY_TYPE_CHOICES = [
        (ANOMALY_COLOR_DIFF_HIGH, '色差偏高'),
        (ANOMALY_COLOR_DIFF_SEVERE, '色差严重'),
        (ANOMALY_PINHOLE_MODERATE, '针孔中等'),
        (ANOMALY_PINHOLE_SEVERE, '针孔严重'),
        (ANOMALY_SUSPENDED, '暂停使用'),
        (ANOMALY_RETEST_OVERDUE, '复测超期'),
    ]

    CAUSE_FORMULA = 'formula'
    CAUSE_PROCESS = 'process'
    CAUSE_KILN = 'kiln'
    CAUSE_MATERIAL = 'material'
    CAUSE_OPERATION = 'operation'
    CAUSE_OTHER = 'other'

    CAUSE_CATEGORY_CHOICES = [
        (CAUSE_FORMULA, '配方问题'),
        (CAUSE_PROCESS, '工艺问题'),
        (CAUSE_KILN, '窑炉问题'),
        (CAUSE_MATERIAL, '原料问题'),
        (CAUSE_OPERATION, '操作问题'),
        (CAUSE_OTHER, '其他'),
    ]

    order_no = models.CharField(max_length=50, unique=True)
    firing_record = models.ForeignKey(
        FiringRecord,
        on_delete=models.PROTECT,
        related_name='rectification_orders'
    )
    anomaly_type = models.CharField(max_length=30, choices=ANOMALY_TYPE_CHOICES)
    anomaly_description = models.TextField()
    cause_category = models.CharField(max_length=30, choices=CAUSE_CATEGORY_CHOICES, blank=True, default='')
    cause_detail = models.TextField(blank=True, default='')
    responsible_person = models.ForeignKey(
        ResponsiblePerson,
        on_delete=models.PROTECT,
        related_name='rectification_orders'
    )
    rectification_measures = models.TextField(blank=True, default='')
    planned_completion_date = models.DateField()
    rectification_result = models.TextField(blank=True, default='')
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default=STATUS_PENDING_ANALYSIS)
    analysis_time = models.DateTimeField(null=True, blank=True)
    rectification_time = models.DateTimeField(null=True, blank=True)
    confirm_time = models.DateTimeField(null=True, blank=True)
    close_time = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.order_no} ({self.get_status_display()})"

    @property
    def is_overdue(self):
        from django.utils import timezone
        if self.status == self.STATUS_CLOSED:
            return False
        if not self.planned_completion_date:
            return False
        today = timezone.now().date()
        return today > self.planned_completion_date

    @property
    def remaining_days(self):
        from django.utils import timezone
        if self.status == self.STATUS_CLOSED:
            return None
        if not self.planned_completion_date:
            return None
        today = timezone.now().date()
        delta = (self.planned_completion_date - today).days
        return delta if delta >= 0 else None

    @property
    def overdue_days(self):
        from django.utils import timezone
        if self.status == self.STATUS_CLOSED:
            return None
        if not self.planned_completion_date:
            return None
        today = timezone.now().date()
        delta = (today - self.planned_completion_date).days
        return delta if delta > 0 else None


class RectificationHistory(models.Model):
    ACTION_CREATE = 'create'
    ACTION_ANALYZE = 'analyze'
    ACTION_SUBMIT = 'submit'
    ACTION_CONFIRM = 'confirm'
    ACTION_REOPEN = 'reopen'
    ACTION_UPDATE = 'update'
    ACTION_COMMENT = 'comment'

    ACTION_CHOICES = [
        (ACTION_CREATE, '创建整改单'),
        (ACTION_ANALYZE, '原因分析'),
        (ACTION_SUBMIT, '提交整改'),
        (ACTION_CONFIRM, '确认关闭'),
        (ACTION_REOPEN, '退回整改'),
        (ACTION_UPDATE, '信息更新'),
        (ACTION_COMMENT, '备注'),
    ]

    rectification_order = models.ForeignKey(
        RectificationOrder,
        on_delete=models.CASCADE,
        related_name='history_records'
    )
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    action_display = models.CharField(max_length=50, blank=True, default='')
    operator_name = models.CharField(max_length=100, blank=True, default='')
    description = models.TextField(blank=True, default='')
    previous_status = models.CharField(max_length=30, blank=True, default='')
    current_status = models.CharField(max_length=30, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.rectification_order.order_no} - {self.get_action_display()}"

    def save(self, *args, **kwargs):
        if not self.action_display:
            self.action_display = self.get_action_display()
        super().save(*args, **kwargs)
