from rest_framework import serializers
from .models import User
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth import authenticate
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


# --- Registration ---
# Validates signup data and creates a new user.
# Django's validate_password checks strength (min 8 chars, not too common, etc.)
class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only = True , required=True , validators=[validate_password])
    password2 = serializers.CharField(write_only = True , required=True)

    class Meta:
        model = User
        fields = ['username' , 'email' , 'password' , 'password2']

    def validate(self , attrs):
        # Make sure both password fields match
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password2": "Passwords do not match."})
        return attrs
       
    def create(self , validated_data):
        validated_data.pop("password2")   # don't store the confirmation field
        user = User.objects.create_user(**validated_data)  # hashes password automatically
        return user


# --- Login ---
# Takes username + password, checks them against the database.
class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self , data):
        # authenticate() returns the User if credentials are correct, None otherwise
        user = authenticate(username=data['username'] , password=data['password'])

        if user is None:
            raise serializers.ValidationError("Invalid username or password.")
        
        return user
    

# --- Profile (read-only view) ---
# Used when fetching a user's profile — some fields can't be edited here.
class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id' , 'username' , 'email' , 'role' , 'bio' , 'avatar' , 'date_joined']    
        read_only_fields = ['id' , 'username' , 'email' , 'role' , 'date_joined']


# --- Profile Update ---
# Only bio and avatar can be updated by the user.
# Bio is sanitized to strip any HTML / script tags (XSS prevention).
import bleach

class ProfileUpdateSerializer(serializers.ModelSerializer):
    bio = serializers.CharField(required=False , allow_blank=True , allow_null=True)
    avatar = serializers.CharField(required=False , allow_blank=True , allow_null=True)

    class Meta:
        model = User
        fields = ['bio' , 'avatar']

    def validate_bio(self, value):
        if value:
            value = bleach.clean(value, tags=[], strip=True).strip()
        return value or None

    def validate_avatar(self, value):
        if value == '':
            return None   # treat empty string as "no avatar"
        return value


# --- Forgot Password ---
# Just needs the email to send a reset link.
class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)


# --- Reset Password ---
# Uses a uid + token (from the reset link) plus the new password.
class ResetPasswordSerializer(serializers.Serializer):
    uid = serializers.CharField(required=True)
    token = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, validators=[validate_password])
    new_password2 = serializers.CharField(required=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password2']:
            raise serializers.ValidationError({"new_password2": "Passwords do not match."})
        return attrs


# --- Lightweight user info ---
# Used by forum-service to display username + avatar next to posts/comments.
# Only exposes the bare minimum — no email, no bio.
class UserBasicSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id' , 'username' , 'avatar' , 'role']


# --- Custom JWT ---
# Puts the user's role inside the JWT token so other services can read it
# without calling auth-service again.
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['role'] = user.role   # add role claim to the JWT payload
        return token