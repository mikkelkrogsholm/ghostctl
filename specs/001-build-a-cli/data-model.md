# Data Model: Ghost CMS Management CLI

**Date**: 2025-09-22
**Feature**: ghostctl - Ghost CMS Management CLI

## Core Entities

### 1. Post/Page
```python
class Post(BaseModel):
    id: str
    uuid: str
    title: str
    slug: str
    mobiledoc: Optional[str] = None
    lexical: Optional[str] = None
    html: Optional[str] = None
    feature_image: Optional[str] = None
    featured: bool = False
    status: Literal["draft", "published", "scheduled"]
    visibility: Literal["public", "members", "paid", "tiers"]
    created_at: datetime
    updated_at: datetime
    published_at: Optional[datetime] = None
    custom_excerpt: Optional[str] = None
    codeinjection_head: Optional[str] = None
    codeinjection_foot: Optional[str] = None
    custom_template: Optional[str] = None
    canonical_url: Optional[str] = None
    tags: List[Tag] = []
    authors: List[Author] = []
    primary_author: Author
    primary_tag: Optional[Tag] = None
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    og_image: Optional[str] = None
    og_title: Optional[str] = None
    og_description: Optional[str] = None
    twitter_image: Optional[str] = None
    twitter_title: Optional[str] = None
    twitter_description: Optional[str] = None

class Page(Post):
    # Pages are identical to Posts but stored separately
    pass
```

### 2. Tag
```python
class Tag(BaseModel):
    id: str
    name: str
    slug: str
    description: Optional[str] = None
    feature_image: Optional[str] = None
    visibility: Literal["public", "internal"]
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    og_image: Optional[str] = None
    og_title: Optional[str] = None
    og_description: Optional[str] = None
    twitter_image: Optional[str] = None
    twitter_title: Optional[str] = None
    twitter_description: Optional[str] = None
    codeinjection_head: Optional[str] = None
    codeinjection_foot: Optional[str] = None
    canonical_url: Optional[str] = None
    accent_color: Optional[str] = None
    created_at: datetime
    updated_at: datetime
```

### 3. Member
```python
class Member(BaseModel):
    id: str
    uuid: str
    email: EmailStr
    name: Optional[str] = None
    note: Optional[str] = None
    geolocation: Optional[str] = None
    status: Literal["free", "paid", "comped"]
    labels: List[Label] = []
    created_at: datetime
    updated_at: datetime
    last_seen_at: Optional[datetime] = None
    subscriptions: List[Subscription] = []
    avatar_image: Optional[str] = None
    email_count: int = 0
    email_opened_count: int = 0
    email_open_rate: Optional[float] = None
```

### 4. Newsletter
```python
class Newsletter(BaseModel):
    id: str
    uuid: str
    name: str
    description: Optional[str] = None
    slug: str
    sender_name: Optional[str] = None
    sender_email: Optional[EmailStr] = None
    sender_reply_to: Literal["newsletter", "support"]
    status: Literal["active", "archived"]
    visibility: Literal["members", "paid"]
    subscribe_on_signup: bool = True
    sort_order: int = 0
    header_image: Optional[str] = None
    show_header_icon: bool = True
    show_header_title: bool = True
    title_font_category: Literal["serif", "sans_serif"]
    title_alignment: Literal["center", "left"]
    show_feature_image: bool = True
    body_font_category: Literal["serif", "sans_serif"]
    footer_content: Optional[str] = None
    show_badge: bool = True
    created_at: datetime
    updated_at: datetime
```

### 5. Tier
```python
class Tier(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    slug: str
    active: bool = True
    type: Literal["free", "paid"]
    welcome_page_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    visibility: Literal["public", "none"]
    trial_days: int = 0

    # Paid tier specific
    currency: Optional[str] = None
    monthly_price: Optional[int] = None
    yearly_price: Optional[int] = None

    # Benefits
    benefits: List[str] = []
```

### 6. Offer
```python
class Offer(BaseModel):
    id: str
    name: str
    code: str
    display_title: str
    display_description: Optional[str] = None
    type: Literal["percent", "fixed", "trial"]
    amount: int  # Percentage or cents
    duration: Literal["once", "forever", "repeating", "trial"]
    duration_in_months: Optional[int] = None
    currency: Optional[str] = None
    status: Literal["active", "archived"]
    redemption_count: int = 0
    tier: Tier
    created_at: datetime
    updated_at: datetime
```

### 7. Webhook
```python
class Webhook(BaseModel):
    id: str
    event: str  # e.g., "post.published", "member.added"
    target_url: HttpUrl
    name: Optional[str] = None
    secret: Optional[str] = None
    api_version: str = "v5"
    integration_id: str
    status: Literal["enabled", "disabled"]
    last_triggered_at: Optional[datetime] = None
    last_triggered_status: Optional[str] = None
    last_triggered_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime
```

### 8. Theme
```python
class Theme(BaseModel):
    name: str
    package: Dict[str, Any]  # package.json contents
    active: bool = False
    templates: List[str] = []

    # Version tracking for rollback
    version: str
    previous_versions: List[str] = []
```

### 9. Image
```python
class Image(BaseModel):
    url: HttpUrl
    ref: Optional[str] = None  # Storage reference
```

### 10. Settings
```python
class Settings(BaseModel):
    # Site settings
    title: str
    description: str
    logo: Optional[HttpUrl] = None
    icon: Optional[HttpUrl] = None
    accent_color: str
    locale: str = "en"
    timezone: str = "UTC"

    # Social accounts
    facebook: Optional[str] = None
    twitter: Optional[str] = None

    # Meta settings
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    og_image: Optional[HttpUrl] = None
    og_title: Optional[str] = None
    og_description: Optional[str] = None
    twitter_image: Optional[HttpUrl] = None
    twitter_title: Optional[str] = None
    twitter_description: Optional[str] = None

    # Code injection
    codeinjection_head: Optional[str] = None
    codeinjection_foot: Optional[str] = None
```

### 11. Profile (CLI Configuration)
```python
class Profile(BaseModel):
    name: str = "default"
    api_url: HttpUrl
    admin_api_key: SecretStr
    api_version: str = "v5"

    # Optional settings
    default_output_format: Literal["table", "json", "yaml"] = "table"
    page_size: int = 15
    max_retries: int = 5
    timeout: int = 30
```

## Validation Rules

### Post/Page Validation
- `slug` must be URL-safe (lowercase, alphanumeric, hyphens)
- `status` transitions: draft → published, published → draft, any → scheduled
- `published_at` required when status is "published" or "scheduled"
- `visibility` "tiers" requires tier assignments
- Either `mobiledoc`, `lexical`, or `html` must be provided for content

### Tag Validation
- `slug` must be unique and URL-safe
- `visibility` "internal" tags start with "#"
- `accent_color` must be valid hex color

### Member Validation
- `email` must be valid and unique
- `status` "paid" requires active subscription
- `labels` are created automatically if they don't exist

### Newsletter Validation
- `slug` must be unique and URL-safe
- `sender_email` required if `sender_name` is set
- `sort_order` must be unique among active newsletters

### Tier Validation
- `slug` must be unique and URL-safe
- `type` "paid" requires pricing information
- `monthly_price` and `yearly_price` in cents (integer)
- At least one price required for paid tiers

### Offer Validation
- `code` must be unique and uppercase
- `type` "percent" requires amount 0-100
- `type` "fixed" requires amount in cents and currency
- `duration` "repeating" requires `duration_in_months`
- Must be associated with a paid tier

### Webhook Validation
- `target_url` must be HTTPS in production
- `event` must be valid Ghost event
- `secret` recommended for security

## State Transitions

### Post Status Flow
```
draft → published (publish)
draft → scheduled (schedule with future date)
published → draft (unpublish)
scheduled → published (when time arrives)
scheduled → draft (unschedule)
```

### Member Status Flow
```
free → paid (subscribe)
paid → free (cancel subscription)
any → comped (comp membership)
comped → free (remove comp)
```

### Newsletter Status Flow
```
active → archived (archive)
archived → active (reactivate)
```

### Tier Status Flow
```
active → archived (archive, hides from portal)
archived → active (reactivate)
```

## Bulk Operation Schemas

### CSV Import Format (Members)
```csv
email,name,note,labels,created_at,complimentary_plan
john@example.com,John Doe,VIP customer,"vip,early-adopter",2024-01-01,true
```

### JSON Import Format (Posts)
```json
{
  "posts": [
    {
      "title": "Post Title",
      "slug": "post-slug",
      "html": "<p>Content</p>",
      "status": "draft",
      "tags": ["tag1", "tag2"]
    }
  ]
}
```

### Export Format
```json
{
  "meta": {
    "exported_on": "2025-01-01T00:00:00Z",
    "version": "5.0.0"
  },
  "data": {
    "posts": [...],
    "pages": [...],
    "tags": [...],
    "members": [...],
    "newsletters": [...]
  }
}
```

## API Response Envelopes

### Single Resource
```json
{
  "posts": [
    {
      "id": "...",
      "title": "..."
    }
  ]
}
```

### Collection with Pagination
```json
{
  "posts": [...],
  "meta": {
    "pagination": {
      "page": 1,
      "limit": 15,
      "pages": 10,
      "total": 150,
      "next": 2,
      "prev": null
    }
  }
}
```

### Error Response
```json
{
  "errors": [
    {
      "message": "Validation error",
      "context": "Title is required",
      "type": "ValidationError",
      "property": "title"
    }
  ]
}
```