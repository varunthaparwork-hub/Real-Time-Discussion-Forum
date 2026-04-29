"""
Create an admin user for the forum.
Run this script once to set up the initial admin account.

Usage:
    cd auth-service
    python create_admin.py

You'll be prompted for a username, email, and password.
If the username already exists, it will be upgraded to admin role.
"""
import os
import sys
import django

# Set up Django so we can use its ORM outside of runserver
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "auth_service.settings")
sys.path.insert(0, os.path.dirname(__file__))
django.setup()

from accounts.models import User


def create_admin():
    print("\n=== Create Admin User ===\n")

    username = input("Username: ").strip()
    if not username:
        print("❌ Username cannot be empty.")
        return

    email = input("Email: ").strip()
    if not email:
        print("❌ Email cannot be empty.")
        return

    password = input("Password: ").strip()
    if len(password) < 8:
        print("❌ Password must be at least 8 characters.")
        return

    # Check if user already exists
    existing = User.objects.filter(username=username).first()
    if existing:
        existing.role = "admin"
        existing.is_staff = True
        existing.is_superuser = True
        existing.save()
        print(f"\n✅ User '{username}' already existed — upgraded to admin role.")
        return

    # Create a brand new admin user
    user = User.objects.create_user(
        username=username,
        email=email,
        password=password,
        role="admin",
        is_staff=True,
        is_superuser=True,
    )

    print(f"\n✅ Admin user created successfully!")
    print(f"   Username : {user.username}")
    print(f"   Email    : {user.email}")
    print(f"   Role     : {user.role}")
    print(f"   ID       : {user.id}")


if __name__ == "__main__":
    create_admin()
