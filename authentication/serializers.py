from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from .models import User, UserProfile, Address, Role, UserRole
from .utils import generate_verification_token, send_verification_email


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for user registration"""
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)
    
    class Meta:
        model = User
        fields = ('email', 'username', 'first_name', 'last_name', 'phone_number', 
                 'date_of_birth', 'password', 'password_confirm')
        extra_kwargs = {
            'email': {'required': True},
            'username': {'required': True},
            'first_name': {'required': True},
            'last_name': {'required': True},
        }
    
    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError("Passwords don't match")
        return attrs
    
    def create(self, validated_data):
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')
        
        user = User.objects.create_user(**validated_data)
        user.set_password(password)
        user.save()
        
        # Create user profile
        UserProfile.objects.create(user=user)
        
        # Send verification email
        send_verification_email(user)
        
        return user


class UserLoginSerializer(serializers.Serializer):
    """Serializer for user login"""
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    
    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')
        
        if email and password:
            user = authenticate(email=email, password=password)
            if not user:
                raise serializers.ValidationError('Invalid credentials')
            if not user.is_active:
                raise serializers.ValidationError('User account is disabled')
            if not user.is_verified:
                raise serializers.ValidationError('Email not verified')
            
            attrs['user'] = user
            return attrs
        else:
            raise serializers.ValidationError('Must include email and password')


class UserSerializer(serializers.ModelSerializer):
    """Serializer for user details"""
    full_name = serializers.SerializerMethodField()
    roles = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ('id', 'email', 'username', 'first_name', 'last_name', 'full_name',
                 'phone_number', 'date_of_birth', 'is_verified', 'avatar', 'bio',
                 'date_joined', 'last_login', 'roles')
        read_only_fields = ('id', 'is_verified', 'date_joined', 'last_login')
    
    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip()
    
    def get_roles(self, obj):
        return [role.role.name for role in obj.user_roles.filter(is_active=True)]


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for user profile"""
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = UserProfile
        fields = ('id', 'user', 'preferences', 'newsletter_subscribed', 
                 'marketing_consent', 'created_at', 'updated_at')
        read_only_fields = ('id', 'created_at', 'updated_at')


class AddressSerializer(serializers.ModelSerializer):
    """Serializer for user addresses"""
    full_address = serializers.SerializerMethodField()
    
    class Meta:
        model = Address
        fields = ('id', 'type', 'first_name', 'last_name', 'company', 
                 'address_line_1', 'address_line_2', 'city', 'state', 
                 'postal_code', 'country', 'is_default', 'full_address',
                 'created_at', 'updated_at')
        read_only_fields = ('id', 'created_at', 'updated_at')
    
    def get_full_address(self, obj):
        address_parts = [
            obj.address_line_1,
            obj.address_line_2,
            obj.city,
            obj.state,
            obj.postal_code,
            obj.country
        ]
        return ', '.join([part for part in address_parts if part])
    
    def create(self, validated_data):
        user = self.context['request'].user
        
        # If this is marked as default, unset other default addresses
        if validated_data.get('is_default', False):
            Address.objects.filter(user=user, type=validated_data['type']).update(is_default=False)
        
        address = Address.objects.create(user=user, **validated_data)
        return address


class RoleSerializer(serializers.ModelSerializer):
    """Serializer for roles"""
    permissions = serializers.StringRelatedField(many=True, read_only=True)
    
    class Meta:
        model = Role
        fields = ('id', 'name', 'description', 'permissions', 'is_active', 'created_at')
        read_only_fields = ('id', 'created_at')


class UserRoleSerializer(serializers.ModelSerializer):
    """Serializer for user-role assignments"""
    user = UserSerializer(read_only=True)
    role = RoleSerializer(read_only=True)
    assigned_by = UserSerializer(read_only=True)
    
    class Meta:
        model = UserRole
        fields = ('id', 'user', 'role', 'assigned_by', 'assigned_at', 
                 'expires_at', 'is_active')
        read_only_fields = ('id', 'assigned_at')


class PasswordChangeSerializer(serializers.Serializer):
    """Serializer for password change"""
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, validators=[validate_password])
    new_password_confirm = serializers.CharField(write_only=True)
    
    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('Current password is incorrect')
        return value
    
    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError("New passwords don't match")
        return attrs
    
    def save(self):
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save()
        return user


class PasswordResetRequestSerializer(serializers.Serializer):
    """Serializer for password reset request"""
    email = serializers.EmailField()
    
    def validate_email(self, value):
        try:
            user = User.objects.get(email=value)
            if not user.is_active:
                raise serializers.ValidationError('User account is disabled')
        except User.DoesNotExist:
            # Don't reveal if email exists or not for security
            pass
        return value


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Serializer for password reset confirmation"""
    token = serializers.CharField()
    new_password = serializers.CharField(validators=[validate_password])
    new_password_confirm = serializers.CharField()
    
    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError("Passwords don't match")
        return attrs


class EmailVerificationSerializer(serializers.Serializer):
    """Serializer for email verification"""
    token = serializers.CharField()
