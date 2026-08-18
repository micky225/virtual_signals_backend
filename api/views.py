import base64
import mimetypes
from django.conf import settings
from django.contrib.auth.models import User
from django.db.models import Count, F, Q
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from .ai import analyze_screenshot, proof_jpeg
from .models import Payment, Prediction, Profile
from .serializers import AdminPaymentSerializer, LoginSerializer, PaymentSerializer, PredictionSerializer, RegisterSerializer

AMOUNTS = {
    'ghana': 'GHC50.00',
    'nigeria': '₦10,000.00',
    'other': 'Telegram',
}

ALLOWED_IMAGE_TYPES = {'image/jpeg', 'image/jpg', 'image/png', 'image/webp'}


def _get_profile(user):
    try:
        return user.profile
    except Profile.DoesNotExist:
        return Profile.objects.create(user=user)


def _profile(user):
    profile = _get_profile(user)
    pending = list(
        Payment.objects.filter(user=user, status='pending').values('id', 'kind', 'status', 'created_at')[:8]
    )
    return {
        'name': user.first_name or user.username,
        'email': user.email,
        'phone': profile.phone,
        'registrationApproved': profile.registration_approved,
        'diamonds': profile.diamonds,
        'unlocked': {
            'football': profile.football_unlocked,
            'bottle': profile.bottle_unlocked,
        },
        'pendingPayments': pending,
        'isAdmin': bool(user.is_staff or user.is_superuser),
    }


def _auth_payload(user):
    token, _ = Token.objects.get_or_create(user=user)
    return {'token': token.key, 'user': _profile(user)}


@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    serializer = RegisterSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = serializer.save()
    return Response(_auth_payload(user), status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    email = serializer.validated_data['email'].lower().strip()
    password = serializer.validated_data['password']
    try:
        user = User.objects.select_related('profile').get(email__iexact=email)
    except User.DoesNotExist:
        return Response({'error': 'Invalid email or password.'}, status=400)
    if not user.check_password(password):
        return Response({'error': 'Invalid email or password.'}, status=400)
    return Response(_auth_payload(user))


@api_view(['GET'])
@permission_classes([AllowAny])
def guest(request):
    return Response({'error': 'Guest access is off. Sign up and wait for admin confirmation.'}, status=403)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me(request):
    return Response(_profile(request.user))


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def payments(request):
    user = request.user
    profile = _get_profile(user)
    if request.method == 'GET':
        kind = request.query_params.get('kind')
        queryset = Payment.objects.filter(user=user).only(
            'id', 'kind', 'country', 'amount', 'transaction_id', 'sender_name',
            'paid_from', 'screenshot', 'status', 'admin_note', 'created_at',
        )
        if kind:
            queryset = queryset.filter(kind=kind)
        return Response(PaymentSerializer(queryset[:50], many=True).data)

    data = request.data.copy()
    kind = data.get('kind')
    country = data.get('country') or 'ghana'
    if kind not in dict(Payment.KIND_CHOICES):
        return Response({'error': 'Unknown payment type.'}, status=400)
    if kind != 'registration' and not profile.registration_approved:
        return Response({'error': 'Your registration payment is still waiting for admin confirmation.'}, status=403)
    screenshot = request.FILES.get('screenshot')
    if not screenshot:
        return Response({'error': 'Upload a payment screenshot.'}, status=400)
    if screenshot.size > 8 * 1024 * 1024:
        return Response({'error': 'Screenshot must be 8MB or smaller.'}, status=400)
    raw = screenshot.read()
    screenshot.seek(0)
    try:
        proof = proof_jpeg(raw)
    except Exception:
        proof = raw if len(raw) <= 400_000 else None
    payment = Payment.objects.create(
        user=user,
        kind=kind,
        country=country,
        amount=AMOUNTS.get(country, 'GHC50.00'),
        transaction_id=data.get('transaction_id') or '',
        sender_name=data.get('sender_name') or '',
        paid_from=data.get('paid_from') or '',
        screenshot=screenshot,
        proof=proof,
        status='pending',
    )
    return Response(PaymentSerializer(payment).data, status=201)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def predictions(request):
    user = request.user
    profile = _get_profile(user)
    if request.method == 'GET':
        game = request.query_params.get('game')
        try:
            limit = min(40, max(1, int(request.query_params.get('limit') or 20)))
        except (TypeError, ValueError):
            limit = 20
        queryset = Prediction.objects.filter(user=user).only('id', 'game', 'cost', 'payload', 'created_at')
        if game:
            queryset = queryset.filter(game=game)
        return Response(PredictionSerializer(queryset[:limit], many=True).data)

    if not profile.registration_approved:
        return Response({'error': 'Your registration payment is still waiting for admin confirmation.'}, status=403)

    game = request.data.get('game')
    if game not in ('football', 'bottle'):
        return Response({'error': 'Unknown game.'}, status=400)
    unlocked = profile.football_unlocked if game == 'football' else profile.bottle_unlocked
    if not unlocked:
        return Response({'error': 'This package is still waiting for admin confirmation.'}, status=403)
    if profile.diamonds < settings.PREDICTION_COST:
        return Response({'error': 'Not enough diamonds. Buy a package to continue.'}, status=400)

    image = request.FILES.get('image')
    if not image:
        return Response({'error': 'Upload a screenshot first.'}, status=400)
    if image.size > 8 * 1024 * 1024:
        return Response({'error': 'Screenshot must be 8MB or smaller.'}, status=400)
    mime = 'image/jpeg' if image.content_type == 'image/jpg' else (image.content_type or 'image/jpeg')
    if mime not in ALLOWED_IMAGE_TYPES:
        return Response({'error': 'Use a PNG, JPG, or JPEG screenshot.'}, status=400)
    try:
        payload = analyze_screenshot(image.read(), mime, game)
    except Exception as error:
        message = str(error) or 'Prediction failed.'
        return Response({'error': message}, status=502)

    updated = Profile.objects.filter(pk=profile.pk, diamonds__gte=settings.PREDICTION_COST).update(
        diamonds=F('diamonds') - settings.PREDICTION_COST
    )
    if not updated:
        return Response({'error': 'Not enough diamonds. Buy a package to continue.'}, status=400)
    profile.refresh_from_db(fields=['diamonds'])
    record = Prediction.objects.create(
        user=user,
        game=game,
        cost=settings.PREDICTION_COST,
        payload=payload['predictions'],
    )
    return Response({
        'game': game,
        'predictions': payload['predictions'],
        'diamonds': profile.diamonds,
        'id': record.id,
        'created_at': record.created_at,
    })


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def clear_predictions(request, game):
    if game not in ('football', 'bottle'):
        return Response({'error': 'Unknown game.'}, status=400)
    Prediction.objects.filter(user=request.user, game=game).delete()
    return Response({'ok': True})


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def admin_payments(request):
    status_filter = (request.query_params.get('status') or 'pending').strip().lower()
    search = (request.query_params.get('q') or '').strip()
    queryset = Payment.objects.select_related('user', 'user__profile')
    if status_filter in ('pending', 'approved', 'rejected'):
        queryset = queryset.filter(status=status_filter)
    if search:
        queryset = queryset.filter(
            Q(user__email__icontains=search)
            | Q(user__first_name__icontains=search)
            | Q(sender_name__icontains=search)
            | Q(transaction_id__icontains=search)
            | Q(paid_from__icontains=search)
        )
    counts = Payment.objects.aggregate(
        pending=Count('id', filter=Q(status='pending')),
        approved=Count('id', filter=Q(status='approved')),
        rejected=Count('id', filter=Q(status='rejected')),
    )
    return Response({
        'counts': {
            **counts,
            'users': User.objects.filter(is_staff=False).count(),
        },
        'payments': AdminPaymentSerializer(queryset[:80], many=True).data,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def admin_review_payment(request, pk):
    try:
        payment = Payment.objects.select_related('user', 'user__profile').get(pk=pk)
    except Payment.DoesNotExist:
        return Response({'error': 'Payment not found.'}, status=404)
    action = (request.data.get('action') or '').strip().lower()
    note = (request.data.get('note') or '').strip()
    if action == 'approve':
        payment.approve(request.user)
    elif action == 'reject':
        if payment.status != 'pending':
            return Response({'error': 'Only pending payments can be rejected.'}, status=400)
        payment.reject(request.user, note=note or 'Rejected by admin')
    else:
        return Response({'error': 'Use action approve or reject.'}, status=400)
    payment.refresh_from_db()
    return Response(AdminPaymentSerializer(payment).data)


def _payment_proof(payment):
    if payment.proof:
        return bytes(payment.proof), 'image/jpeg'
    if not payment.screenshot:
        return None, None
    try:
        with payment.screenshot.open('rb') as handle:
            raw = handle.read()
    except OSError:
        return None, None
    if not raw:
        return None, None
    mime = mimetypes.guess_type(payment.screenshot.name)[0] or 'image/jpeg'
    try:
        jpeg = proof_jpeg(raw)
        payment.proof = jpeg
        payment.save(update_fields=['proof'])
        return jpeg, 'image/jpeg'
    except Exception:
        return raw, mime


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def admin_payment_screenshot(request, pk):
    try:
        payment = Payment.objects.get(pk=pk)
    except Payment.DoesNotExist:
        return Response({'error': 'Payment not found.'}, status=404)
    raw, mime = _payment_proof(payment)
    if not raw:
        return Response({'error': 'Screenshot file is missing on the server.'}, status=404)
    return Response({
        'mime': mime,
        'image': base64.b64encode(raw).decode(),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def admin_users(request):
    search = (request.query_params.get('q') or '').strip()
    queryset = User.objects.select_related('profile').annotate(
        pending_count=Count('payments', filter=Q(payments__status='pending')),
    ).order_by('-date_joined')
    if search:
        queryset = queryset.filter(
            Q(email__icontains=search) | Q(first_name__icontains=search) | Q(profile__phone__icontains=search)
        )
    rows = []
    for user in queryset[:80]:
        try:
            profile = user.profile
        except Profile.DoesNotExist:
            profile = None
        rows.append({
            'id': user.id,
            'name': user.first_name or user.username,
            'email': user.email,
            'phone': profile.phone if profile else '',
            'diamonds': profile.diamonds if profile else 0,
            'registrationApproved': bool(profile and profile.registration_approved),
            'footballUnlocked': bool(profile and profile.football_unlocked),
            'bottleUnlocked': bool(profile and profile.bottle_unlocked),
            'pendingPayments': user.pending_count,
            'joined': user.date_joined,
        })
    return Response(rows)
