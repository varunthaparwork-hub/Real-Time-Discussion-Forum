from django.urls import path
from .views import (
    LoginView, RegisterView, ProfileView,
    UserBasicListView, UserByUsernameListView, AllUsersView, ForgotPasswordView, ResetPasswordView,
    PublicProfileView, UpdateRoleView,
)

# All these URLs are prefixed with /api/auth/ (set in auth_service/urls.py)
urlpatterns = [
    # Public endpoints (no login needed)
    path('register/' , RegisterView.as_view()),             # POST — create account
    path('login/' , LoginView.as_view()),                   # POST — get JWT tokens
    path('forgot-password/', ForgotPasswordView.as_view()), # POST — request reset link
    path('reset-password/', ResetPasswordView.as_view()),   # POST — set new password

    # Protected endpoints (login required)
    path('profile/' , ProfileView.as_view()),               # GET/PUT — own profile

    # Public profile (anyone can view)
    path('profile/<str:username>/', PublicProfileView.as_view()),  # GET — view someone's profile

    # Internal endpoints (called by forum-service, not by users directly)
    path('users/basic/' , UserBasicListView.as_view()),            # GET ?ids=1,2,3
    path('users/by-usernames/' , UserByUsernameListView.as_view()),# GET ?usernames=varun,john

    # Admin endpoints
    path('users/all/' , AllUsersView.as_view()),                   # GET — list all users
    path('users/<int:user_id>/role/', UpdateRoleView.as_view()),   # PUT — change someone's role
]
