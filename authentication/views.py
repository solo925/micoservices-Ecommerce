from rest_framework import generics, status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import transaction

from .serializers import (
    UserRegistrationSerializer, UserLoginSerializer, UserSerializer,
    UserProfileSerializer, AddressSerializer, PasswordChangeSerializer,
    PasswordResetRequestSerializer, PasswordResetConfirmSerializer,
    EmailVerificationSerializer, RoleSerializer
)
from .models import UserProfile, Address, Role, LoginAttempt
from .utils import (
    generate_jwt_tokens, log_login_attempt, check_rate_limit,
    get_client_ip, get_user_agent, send_password_reset_email,
    verify_email_token, reset_password_with_token, RoleManager
)

User = get_user_model()


class UserRegistrationView(generics.CreateAPIView):
    """User registration endpoint"""
    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny]
    
    def create(self, request, *args, **kwargs):
        ip_address = get_client_ip(request)
        if check_rate_limit('', ip_address, window_minutes=60, max_attempts=3):
            return Response(
                {'error': 'Too many registration attempts. Please try again later.'},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        with transaction.atomic():
            user = serializer.save()
            RoleManager.assign_role(user, 'customer')
            tokens = generate_jwt_tokens(user)
            
            return Response({
                'message': 'Registration successful. Please check your email for verification.',
                'user': UserSerializer(user).data,
                'tokens': tokens
            }, status=status.HTTP_201_CREATED)


class UserLoginView(APIView):
    """User login endpoint with rate limiting and security logging"""
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        serializer = UserLoginSerializer(data=request.data)
        email = request.data.get('email', '')
        ip_address = get_client_ip(request)
        user_agent = get_user_agent(request)
        
        if check_rate_limit(email, ip_address):
            log_login_attempt(email, ip_address, user_agent, False, 'Rate limited')
            return Response(
                {'error': 'Too many failed attempts. Please try again later.'},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )
        
        if serializer.is_valid():
            user = serializer.validated_data['user']
            user.last_login_ip = ip_address
            user.save(update_fields=['last_login_ip'])
            
            tokens = generate_jwt_tokens(user)
            log_login_attempt(email, ip_address, user_agent, True)
            
            return Response({
                'message': 'Login successful',
                'user': UserSerializer(user).data,
                'tokens': tokens
            }, status=status.HTTP_200_OK)
        else:
            log_login_attempt(email, ip_address, user_agent, False, 'Invalid credentials')
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserLogoutView(APIView):
    """User logout endpoint"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        try:
            refresh_token = request.data.get('refresh_token')
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
            return Response({'message': 'Logout successful'}, status=status.HTTP_200_OK)
        except Exception:
            return Response({'error': 'Invalid token'}, status=status.HTTP_400_BAD_REQUEST)


class UserProfileView(generics.RetrieveUpdateAPIView):
    """User profile management"""
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        return self.request.user


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def health_check(request):
    """Health check endpoint"""
    return Response({
        'status': 'healthy',
        'service': 'authentication',
        'timestamp': timezone.now().isoformat()
    }, status=status.HTTP_200_OK)