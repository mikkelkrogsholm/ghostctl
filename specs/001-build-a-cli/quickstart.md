# Quickstart Guide: ghostctl

This guide will help you get started with ghostctl, the command-line tool for managing Ghost CMS.

## Installation

### Via pip (recommended)
```bash
pip install ghostctl
```

### Via Docker
```bash
docker pull ghostctl/ghostctl:latest
```

### From source
```bash
git clone https://github.com/yourusername/ghostctl.git
cd ghostctl
pip install -e .
```

## Configuration

### 1. Set up your first profile

Create a configuration file at `~/.ghostctl.toml`:

```bash
ghostctl config init
```

Or manually create the file:

```toml
[profiles.default]
api_url = "https://your-blog.ghost.io"
admin_api_key = "your-admin-api-key"
api_version = "v5"

[profiles.staging]
api_url = "https://staging.ghost.io"
admin_api_key = "staging-admin-api-key"
api_version = "v5"
```

### 2. Using environment variables

```bash
export GHOST_API_URL="https://your-blog.ghost.io"
export GHOST_ADMIN_API_KEY="your-admin-api-key"
export GHOST_API_VERSION="v5"
```

### 3. Verify connection

```bash
ghostctl settings list
```

## Basic Usage

### Working with Posts

#### List all posts
```bash
# Default table format
ghostctl posts list

# JSON output
ghostctl posts list --output json

# Filter published posts
ghostctl posts list --filter "status:published"

# Pagination
ghostctl posts list --page 2 --limit 20
```

#### Create a new post
```bash
# Create draft post
ghostctl posts create --title "My New Post" --content "Post content here"

# Create and publish immediately
ghostctl posts create --title "Published Post" --content "Content" --status published

# Create from Markdown file
ghostctl posts create --title "From File" --file content.md
```

#### Update a post
```bash
# Update title
ghostctl posts update post-id --title "Updated Title"

# Publish a draft
ghostctl posts publish post-id

# Schedule for future
ghostctl posts schedule post-id --date "2025-01-01 10:00"
```

#### Delete a post
```bash
# Delete with confirmation
ghostctl posts delete post-id

# Force delete without confirmation
ghostctl posts delete post-id --force
```

### Working with Images

#### Upload an image
```bash
# Upload single image
ghostctl images upload photo.jpg

# Upload and get URL
URL=$(ghostctl images upload photo.jpg --output json | jq -r '.url')

# Upload as feature image for post
ghostctl posts update post-id --feature-image photo.jpg
```

### Working with Themes

#### List themes
```bash
ghostctl themes list
```

#### Upload and activate theme
```bash
# Upload theme
ghostctl themes upload my-theme.zip

# Activate theme
ghostctl themes activate my-theme

# Upload and activate in one command
ghostctl themes upload my-theme.zip --activate
```

#### Rollback theme
```bash
# Rollback to previous version
ghostctl themes rollback

# Rollback to specific version
ghostctl themes rollback --version 1.2.3
```

### Working with Tags

#### List tags
```bash
ghostctl tags list
```

#### Create tag
```bash
ghostctl tags create --name "Technology" --description "Tech articles"
```

#### Update tag
```bash
ghostctl tags update tag-id --description "Updated description"
```

#### Delete tag
```bash
ghostctl tags delete tag-id
```

### Bulk Operations

#### Import members from CSV
```bash
ghostctl members import members.csv --dry-run
ghostctl members import members.csv
```

#### Bulk update posts
```bash
# Add tag to multiple posts
ghostctl posts bulk-update --filter "status:draft" --add-tag "needs-review"

# Publish all drafts
ghostctl posts bulk-publish --filter "status:draft"
```

#### Export content
```bash
# Export all content
ghostctl export all --output backup.json

# Export specific resources
ghostctl export posts --output posts.json
ghostctl export members --output members.csv
```

## Advanced Features

### Dry Run Mode
Test commands without making changes:
```bash
ghostctl posts delete post-id --dry-run
ghostctl members import large-file.csv --dry-run
```

### Debug Mode
See detailed API calls and responses:
```bash
ghostctl --debug posts list
```

### Using Profiles
```bash
# Use staging profile
ghostctl --profile staging posts list

# Use production profile
ghostctl --profile production posts publish post-id
```

### Output Formats

#### Table (default)
```bash
ghostctl posts list
```

#### JSON
```bash
ghostctl posts list --output json
```

#### YAML
```bash
ghostctl posts list --output yaml
```

### Scripting Examples

#### Backup all posts
```bash
#!/bin/bash
DATE=$(date +%Y%m%d)
ghostctl export posts --output "backup-posts-$DATE.json"
```

#### Publish scheduled posts
```bash
#!/bin/bash
ghostctl posts list --filter "status:scheduled" --output json | \
  jq -r '.posts[] | select(.published_at < now) | .id' | \
  xargs -I {} ghostctl posts publish {}
```

#### Monitor failed webhooks
```bash
#!/bin/bash
ghostctl webhooks list --output json | \
  jq '.webhooks[] | select(.last_triggered_status == "failed")'
```

## Docker Compose Example

```yaml
version: '3.8'

services:
  ghost:
    image: ghost:5-alpine
    environment:
      - url=http://localhost:2368
    volumes:
      - ghost-data:/var/lib/ghost/content
    ports:
      - "2368:2368"

  ghostctl:
    image: ghostctl/ghostctl:latest
    environment:
      - GHOST_API_URL=http://ghost:2368
      - GHOST_ADMIN_API_KEY=${GHOST_ADMIN_API_KEY}
    depends_on:
      - ghost
    volumes:
      - ./scripts:/scripts
    command: tail -f /dev/null

volumes:
  ghost-data:
```

## Testing Your Setup

Run this test script to verify everything is working:

```bash
#!/bin/bash
echo "Testing ghostctl setup..."

# 1. Check connection
echo "1. Checking connection..."
ghostctl settings list > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "   ✓ Connected to Ghost"
else
    echo "   ✗ Connection failed"
    exit 1
fi

# 2. Create test post
echo "2. Creating test post..."
POST_ID=$(ghostctl posts create \
    --title "Test Post $(date +%s)" \
    --content "This is a test" \
    --status draft \
    --output json | jq -r '.posts[0].id')

if [ ! -z "$POST_ID" ]; then
    echo "   ✓ Created post: $POST_ID"
else
    echo "   ✗ Failed to create post"
    exit 1
fi

# 3. Upload test image
echo "3. Testing image upload..."
echo '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
  <rect width="100" height="100" fill="blue"/>
</svg>' > test.svg

IMAGE_URL=$(ghostctl images upload test.svg --output json | jq -r '.images[0].url')
rm test.svg

if [ ! -z "$IMAGE_URL" ]; then
    echo "   ✓ Uploaded image: $IMAGE_URL"
else
    echo "   ✗ Failed to upload image"
fi

# 4. Create test tag
echo "4. Creating test tag..."
TAG_ID=$(ghostctl tags create \
    --name "Test Tag $(date +%s)" \
    --output json | jq -r '.tags[0].id')

if [ ! -z "$TAG_ID" ]; then
    echo "   ✓ Created tag: $TAG_ID"
else
    echo "   ✗ Failed to create tag"
fi

# 5. Cleanup
echo "5. Cleaning up..."
ghostctl posts delete $POST_ID --force
ghostctl tags delete $TAG_ID --force

echo ""
echo "All tests passed! ghostctl is working correctly."
```

## Troubleshooting

### Authentication Errors
```bash
# Check your API key
ghostctl config validate

# Test with debug mode
ghostctl --debug settings list
```

### Rate Limiting
```bash
# Check rate limit status
ghostctl --debug posts list 2>&1 | grep "X-RateLimit"

# Use retry with backoff
ghostctl --max-retries 5 posts list
```

### Network Issues
```bash
# Increase timeout
ghostctl --timeout 60 posts list

# Use proxy
export HTTPS_PROXY=http://proxy:8080
ghostctl posts list
```

## Getting Help

```bash
# General help
ghostctl --help

# Command-specific help
ghostctl posts --help
ghostctl posts create --help

# Show version
ghostctl --version
```

## Next Steps

- Set up GitHub Actions for automated content publishing
- Configure webhooks for integration with other services
- Explore the full API documentation
- Join the community forum for tips and tricks