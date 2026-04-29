"""
Mention parser — finds @username patterns in comment text.
For example, if someone writes "Great post @varun!", this extracts ["varun"].
Used to send notifications to mentioned users.
"""
import re

MENTION_PATTERN = r'@([A-Za-z0-9_]+)'

def extract_usernames(text:str) -> list[str]:
    return list(set(re.findall(MENTION_PATTERN , text)))