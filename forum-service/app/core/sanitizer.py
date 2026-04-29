"""
Input sanitizer — strips dangerous HTML / script tags from user input.

Prevents stored XSS attacks by cleaning content before it's saved to
the database. Uses the bleach library with a strict whitelist:
  • No HTML tags allowed in thread titles
  • Only safe inline formatting in descriptions and comments
"""
import bleach

# Tags allowed in descriptions and comments (basic formatting only)
_ALLOWED_TAGS = ["b", "i", "em", "strong", "a", "code", "br"]
_ALLOWED_ATTRS = {"a": ["href", "title"]}


def sanitize_text(text: str) -> str:
    """Strip ALL HTML tags — used for titles and short text fields."""
    return bleach.clean(text, tags=[], strip=True).strip()


def sanitize_rich_text(text: str) -> str:
    """Allow only safe formatting tags — used for descriptions and comments."""
    return bleach.clean(
        text,
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRS,
        strip=True,
    ).strip()
