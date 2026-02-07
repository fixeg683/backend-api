from rest_framework import viewsets, filters, permissions, generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.contrib.auth.models import User
from django.conf import settings
from .models import Product, Category, Order
from .serializers import ProductSerializer, CategorySerializer, UserSerializer, OrderSerializer

# Import M-Pesa Library
try:
    from django_mpesa.functions import LipaNaMpesa
except ImportError:
    # Fallback to prevent crash if library isn't installed yet
    LipaNaMpesa = None

class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow admins to edit objects.
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_staff

# --- Auth Views ---
class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = (permissions.AllowAny,)
    serializer_class = UserSerializer

# --- Store Views ---
class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAdminOrReadOnly] 

class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.select_related('category').all()
    serializer_class = ProductSerializer
    permission_classes = [IsAdminOrReadOnly]

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category']
    search_fields = ['name', 'description']
    ordering_fields = ['price', 'created_at']

# --- Order View ---
class OrderViewSet(viewsets.ModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

# --- M-Pesa Payment View (NEW) ---
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mpesa_stk_push(request):
    """
    Triggers the M-Pesa STK Push to the user's phone.
    Expects JSON: {'phone_number': '2547...', 'amount': 100}
    """
    if LipaNaMpesa is None:
        return Response({'error': 'M-Pesa library not installed'}, status=500)

    phone_number = request.data.get('phone_number')
    amount = request.data.get('amount')

    if not phone_number or not amount:
        return Response({'error': 'Phone number and amount are required'}, status=400)

    try:
        amount = int(float(amount))
    except ValueError:
        return Response({'error': 'Invalid amount'}, status=400)

    # Initialize M-Pesa
    mpesa = LipaNaMpesa(
        settings.MPESA_CONSUMER_KEY, 
        settings.MPESA_CONSUMER_SECRET, 
        settings.MPESA_SHORTCODE, 
        settings.MPESA_PASSKEY
    )

    # Callback URL (Must be publicly accessible, use Ngrok for localhost)
    callback_url = "https://mydomain.com/api/mpesa/callback/" 
    
    account_reference = "EcommerceShop"
    transaction_desc = "Payment for Order"

    try:
        # Send STK Push
        response = mpesa.stk_push(
            phone_number, 
            amount, 
            account_reference, 
            transaction_desc, 
            callback_url
        )
        return Response(response)
    except Exception as e:
        return Response({'error': str(e)}, status=500)