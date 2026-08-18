from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone = models.CharField(max_length=40, blank=True)
    referral = models.CharField(max_length=40, blank=True)
    registration_approved = models.BooleanField(default=False)
    diamonds = models.PositiveIntegerField(default=0)
    football_unlocked = models.BooleanField(default=False)
    bottle_unlocked = models.BooleanField(default=False)

    def __str__(self):
        return self.user.email or self.user.username


class Payment(models.Model):
    KIND_CHOICES = [
        ('registration', 'Registration'),
        ('football', 'Instant Football'),
        ('bottle', 'Spin the Bottle'),
        ('diamonds', 'Diamond top-up'),
    ]
    COUNTRY_CHOICES = [
        ('ghana', 'Ghana'),
        ('nigeria', 'Nigeria'),
        ('other', 'Other'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending admin confirmation'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payments')
    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    country = models.CharField(max_length=20, choices=COUNTRY_CHOICES, default='ghana')
    amount = models.CharField(max_length=40, blank=True)
    transaction_id = models.CharField(max_length=80, blank=True)
    sender_name = models.CharField(max_length=120)
    paid_from = models.CharField(max_length=80)
    screenshot = models.ImageField(upload_to='payments/%Y/%m/')
    proof = models.BinaryField(null=True, blank=True, editable=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    admin_note = models.CharField(max_length=240, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='reviewed_payments')

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status'], name='api_pay_user_status_idx'),
        ]

    def __str__(self):
        return f'{self.user.email} · {self.kind} · {self.status}'

    def approve(self, admin_user=None):
        if self.status == 'approved':
            return
        profile, _ = Profile.objects.get_or_create(user=self.user)
        if self.kind == 'registration':
            profile.registration_approved = True
        elif self.kind == 'football':
            profile.football_unlocked = True
            profile.diamonds += settings.PACKAGE_DIAMONDS
        elif self.kind == 'bottle':
            profile.bottle_unlocked = True
            profile.diamonds += settings.PACKAGE_DIAMONDS
        elif self.kind == 'diamonds':
            profile.diamonds += settings.PACKAGE_DIAMONDS
        profile.save()
        self.status = 'approved'
        self.reviewed_at = timezone.now()
        self.reviewed_by = admin_user
        self.save(update_fields=['status', 'reviewed_at', 'reviewed_by'])

    def reject(self, admin_user=None, note=''):
        self.status = 'rejected'
        self.admin_note = note or self.admin_note
        self.reviewed_at = timezone.now()
        self.reviewed_by = admin_user
        self.save(update_fields=['status', 'admin_note', 'reviewed_at', 'reviewed_by'])


class Prediction(models.Model):
    GAME_CHOICES = [
        ('football', 'Instant Football'),
        ('bottle', 'Spin the Bottle'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='predictions')
    game = models.CharField(max_length=20, choices=GAME_CHOICES)
    cost = models.PositiveIntegerField(default=50)
    payload = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'game'], name='api_pred_user_game_idx'),
        ]

    def __str__(self):
        return f'{self.user.email} · {self.game} · {self.created_at:%Y-%m-%d %H:%M}'
