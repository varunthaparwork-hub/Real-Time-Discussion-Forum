from django.db import models
from django.contrib.auth.models import AbstractUser


# The main user table — every person who signs up gets a row here.
# Extends Django's built-in user (which already has username, email, password)
# and adds a few extra fields on top.
class User(AbstractUser):
    # What power level the user has — most people are just "member"
    ROLE_CHOICES = (
        ('admin' , 'Admin'),
        ('moderator' , 'Moderator'),
        ('member' , 'Member'),
    ) 

    role = models.CharField(max_length=10 , choices=ROLE_CHOICES, default='member')
    bio = models.TextField(blank=True , null=True)       # short "about me" text
    avatar = models.TextField(blank=True , null=True)     # profile picture URL