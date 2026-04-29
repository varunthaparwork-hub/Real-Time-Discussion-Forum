from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import (
    LoginSerializer, RegisterSerializer, ProfileSerializer,
    ProfileUpdateSerializer, UserBasicSerializer,
    ForgotPasswordSerializer, ResetPasswordSerializer,
    CustomTokenObtainPairSerializer,
)
from rest_framework.permissions import IsAuthenticated , IsAdminUser
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken
from .models import User
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str


# ── Sign Up ──────────────────────────────────────────────────────────
# Creates a new user account.
# If anything is wrong (username taken, weak password, etc.)
# it returns the exact field-level errors so the frontend can show them.
class RegisterView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'register'

    def post(self , request):
        serializer = RegisterSerializer(data=request.data)

        if serializer.is_valid():
            user = serializer.save()
            return Response({"message" : "User created Successfully"} , status=status.HTTP_201_CREATED)
        
        # Return field-specific errors like {"username": ["already exists"]}
        return Response(serializer.errors , status=status.HTTP_400_BAD_REQUEST)


# ── Login ────────────────────────────────────────────────────────────
# Checks username + password and returns JWT tokens (access + refresh).
# The access token is what the frontend sends with every request.
# The refresh token is used to get a new access token when it expires.
class LoginView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'login'

    def post(self , request):
        serializer = LoginSerializer(data=request.data)

        if serializer.is_valid():
            user = serializer.validated_data
            # Generate JWT with the user's role baked into the token
            refresh = CustomTokenObtainPairSerializer.get_token(user)

            return Response({
                "access" : str(refresh.access_token),
                "refresh" : str(refresh)
            })
        
        return Response(serializer.errors , status=status.HTTP_400_BAD_REQUEST)
    

# ── My Profile ───────────────────────────────────────────────────────
# GET  → returns the logged-in user's profile
# PUT  → updates bio / avatar
class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self , request):
        user = request.user
        serializer = ProfileSerializer(user)
        return Response(serializer.data)

    def put(self, request):
        serializer = ProfileUpdateSerializer(request.user , data=request.data , partial=True)

        if serializer.is_valid():
            serializer.save()
            return Response(ProfileSerializer(request.user).data)

        return Response(serializer.errors , status=400)    


# ── Bulk user lookup by IDs ──────────────────────────────────────────
# Called by forum-service to get usernames + avatars for posts/comments.
# Example: GET /users/basic/?ids=1,5,12
class UserBasicListView(APIView):

    def get(self , request):
        ids_param = request.GET.get("ids" , "")

        if not ids_param:
            return Response([])
        
        try: 
            ids = [int(i.strip()) for i in ids_param.split(",") if i.strip()]
        
        except ValueError:
            return Response({"detail" : "Invalid ids Format"} , status=400)
        
        users = User.objects.filter(id__in = ids)
        serializer = UserBasicSerializer(users , many = True)
        return Response(serializer.data)


# ── Bulk user lookup by usernames ────────────────────────────────────
# Called when someone @mentions users in a comment.
# Example: GET /users/by-usernames/?usernames=varun,john
class UserByUsernameListView(APIView):
    def get(self , request):
        usernames_param = request.GET.get("usernames" , "")

        if not usernames_param:
            return Response([])
        
        usernames = [u.strip() for u in usernames_param.split(",") if u.strip()]
        users = User.objects.filter(username__in = usernames)
        serializer = UserBasicSerializer(users , many = True)

        return Response(serializer.data)


# ── Admin dashboard: list all users (paginated) ─────────────────────
# Returns 10 users per page by default.  GET /users/all/?page=2
class AllUsersView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self , request):
        if request.user.role not in ['admin' , 'moderator']:
            return Response({"detail": "Permission denied"} , status=status.HTTP_403_FORBIDDEN)

        # Read page & limit from query string, with safe defaults
        try:
            page = max(int(request.GET.get('page', 1)), 1)
        except (ValueError, TypeError):
            page = 1
        try:
            limit = min(max(int(request.GET.get('limit', 10)), 1), 50)  # cap at 50
        except (ValueError, TypeError):
            limit = 10

        all_users = User.objects.all().order_by('-date_joined')
        total_users = all_users.count()
        total_pages = max((total_users + limit - 1) // limit, 1)  # ceiling division, at least 1

        start = (page - 1) * limit
        end = start + limit
        users_page = all_users[start:end]

        serializer = ProfileSerializer(users_page, many=True)
        return Response({
            'users': serializer.data,
            'page': page,
            'total_pages': total_pages,
            'total_users': total_users,
        })


# ── Public profile page ──────────────────────────────────────────────
# Anyone can view another user's profile (no login needed)
class PublicProfileView(APIView):
    def get(self, request, username):
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response({"detail": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = ProfileSerializer(user)
        return Response(serializer.data)


# ── Change a user's role (admin only) ────────────────────────────────
# Admins can promote/demote users. Can't change your own role.
class UpdateRoleView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, user_id):
        if request.user.role != 'admin':
            return Response({"detail": "Only admins can change roles"}, status=status.HTTP_403_FORBIDDEN)

        try:
            target_user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"detail": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        new_role = request.data.get('role')
        if new_role not in ['admin', 'moderator', 'member']:
            return Response({"detail": "Invalid role. Must be admin, moderator, or member"}, status=status.HTTP_400_BAD_REQUEST)

        if target_user.id == request.user.id:
            return Response({"detail": "You cannot change your own role"}, status=status.HTTP_400_BAD_REQUEST)

        target_user.role = new_role
        target_user.save(update_fields=['role'])

        return Response({"message": f"Role updated to {new_role}", "user": ProfileSerializer(target_user).data})


class ForgotPasswordView(APIView):
    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            try:
                # If multiple users share the same email, pick the first one
                user = User.objects.filter(email=email).first()
            except Exception:
                return Response({"message": "If that email exists, a reset link has been generated."}, status=status.HTTP_200_OK)

            if user is None:
                return Response({"message": "If that email exists, a reset link has been generated."}, status=status.HTTP_200_OK)

            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)

            reset_link = f"http://localhost:5173/reset-password?uid={uid}&token={token}"

            # Try sending email
            email_sent = False
            try:
                from django.core.mail import send_mail
                from django.conf import settings
                if settings.EMAIL_HOST_USER:  # Only send if email is configured
                    send_mail(
                        subject='Reset Your Forum Password',
                        message=f'Hi {user.username},\n\nClick the link below to reset your password:\n\n{reset_link}\n\nIf you did not request this, ignore this email.',
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[email],
                        fail_silently=False,
                    )
                    email_sent = True
            except Exception as e:
                print(f"Email send failed: {e}")

            response_data = {
                "message": "A reset link has been generated." if not email_sent else "A reset link has been sent to your email.",
                "reset_link": reset_link,  # Always include for dev; remove in production
            }
            if email_sent:
                response_data.pop("reset_link")  # Don't expose link if email was sent

            return Response(response_data, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ResetPasswordView(APIView):
    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        if serializer.is_valid():
            try:
                uid = force_str(urlsafe_base64_decode(serializer.validated_data['uid']))
                user = User.objects.get(pk=uid)
            except (TypeError, ValueError, OverflowError, User.DoesNotExist):
                return Response({"detail": "Invalid reset link"}, status=status.HTTP_400_BAD_REQUEST)

            if not default_token_generator.check_token(user, serializer.validated_data['token']):
                return Response({"detail": "Invalid or expired reset link"}, status=status.HTTP_400_BAD_REQUEST)

            user.set_password(serializer.validated_data['new_password'])
            user.save()  # Full save to update password hash + any fields token generator depends on

            return Response({"message": "Password has been reset successfully"}, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
