import html
import re
import string

from app.models.notifications import NotificationBodyFormat
from app.services.notifications.errors import NotificationDomainError

PLACEHOLDER_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
SAFE_HTML_TAGS = ("b", "strong", "i", "em", "u", "br", "p", "ul", "ol", "li", "span")
SAFE_HTML_RE = re.compile(r"&lt;(/?(?:%s))&gt;" % "|".join(SAFE_HTML_TAGS), flags=re.IGNORECASE)


def render_template(template: str, values: dict[str, object], allowed_placeholders: set[str] | None = None) -> str:
    placeholders = extract_placeholders(template)
    if allowed_placeholders is not None:
        unexpected = placeholders - allowed_placeholders
        if unexpected:
            raise NotificationDomainError(f"Unexpected template placeholders: {', '.join(sorted(unexpected))}")
    missing = [name for name in sorted(placeholders) if name not in values]
    if missing:
        raise NotificationDomainError(f"Missing template values: {', '.join(missing)}")
    safe_values = {key: _scalar_to_string(value) for key, value in values.items() if key in placeholders}
    try:
        return template.format(**safe_values)
    except (KeyError, ValueError, IndexError) as exc:
        raise NotificationDomainError("Template rendering failed") from exc


def render_body(template: str, values: dict[str, object], body_format: NotificationBodyFormat, allowed_placeholders: set[str] | None = None) -> str:
    rendered = render_template(template, values, allowed_placeholders)
    if body_format == NotificationBodyFormat.HTML:
        return sanitize_minimal_html(rendered)
    return rendered


def extract_placeholders(template: str) -> set[str]:
    formatter = string.Formatter()
    placeholders: set[str] = set()
    try:
        parsed = list(formatter.parse(template))
    except ValueError as exc:
        raise NotificationDomainError("Invalid template syntax") from exc
    for _, field_name, format_spec, conversion in parsed:
        if field_name is None:
            continue
        if format_spec or conversion:
            raise NotificationDomainError("Template format specs and conversions are not allowed")
        if not PLACEHOLDER_RE.fullmatch(field_name):
            raise NotificationDomainError("Template placeholders must be simple identifiers")
        if field_name.startswith("_") or "__" in field_name:
            raise NotificationDomainError("Private template placeholders are not allowed")
        placeholders.add(field_name)
    return placeholders


def sanitize_minimal_html(value: str) -> str:
    escaped = html.escape(value, quote=False)
    return SAFE_HTML_RE.sub(lambda match: f"<{match.group(1).lower()}>", escaped)


def _scalar_to_string(value: object) -> str:
    if value is None or isinstance(value, (dict, list, tuple, set)):
        raise NotificationDomainError("Template values must be approved scalar values")
    return str(value)
