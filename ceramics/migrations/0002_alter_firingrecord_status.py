from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ceramics', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='firingrecord',
            name='status',
            field=models.CharField(choices=[('pending', '待试烧'), ('firing', '试烧中'), ('pending_retest', '待复测'), ('retested', '已复测'), ('adjusting', '调整中'), ('approved', '可定样'), ('suspended', '暂停使用')], default='pending', max_length=20),
        ),
    ]
