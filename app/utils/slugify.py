import re
from sqlalchemy.orm import Session


def slugify(text: str) -> str:
    """
    Convert text to a URL-friendly slug.

    Args:
        text: The text to convert to a slug

    Returns:
        A lowercase, hyphenated slug
    """
    if not text:
        return ""

    # Convert to lowercase
    slug = text.lower()

    # Replace spaces and underscores with hyphens
    slug = re.sub(r'[\s_]+', '-', slug)

    # Remove all non-alphanumeric characters except hyphens
    slug = re.sub(r'[^a-z0-9-]', '', slug)

    # Remove multiple consecutive hyphens
    slug = re.sub(r'-+', '-', slug)

    # Strip hyphens from start and end
    slug = slug.strip('-')

    return slug


def generate_unique_slug(db: Session, model_class, base_text: str, exclude_id: int = None) -> str:
    """
    Generate a unique slug for a model instance.

    Args:
        db: Database session
        model_class: The SQLAlchemy model class
        base_text: The text to base the slug on
        exclude_id: Optional ID to exclude from uniqueness check (for updates)

    Returns:
        A unique slug for the model
    """
    base_slug = slugify(base_text)

    if not base_slug:
        base_slug = "item"

    slug = base_slug
    counter = 1

    while True:
        # Check if slug exists
        query = db.query(model_class).filter(model_class.slug == slug)

        # Exclude current record if updating
        if exclude_id is not None:
            query = query.filter(model_class.id != exclude_id)

        existing = query.first()

        if not existing:
            return slug

        # Slug exists, try with counter
        counter += 1
        slug = f"{base_slug}-{counter}"
