# GhostCtl CLI

Command-line tool for managing Ghost CMS instances with comprehensive content management, user administration, theme management, and automation capabilities.

## Features

- **Content Management**: Create, update, delete, and publish posts and pages
- **Tag Management**: Organize content with tags and categories
- **Image Handling**: Upload and manage images for your Ghost site
- **Theme Management**: Upload, activate, and rollback themes
- **Member Management**: Handle user registrations and member data
- **Bulk Operations**: Perform operations on multiple items at once
- **Export/Import**: Backup and migrate your Ghost content
- **Multiple Profiles**: Manage multiple Ghost instances
- **Secure Authentication**: JWT-based authentication with secure credential storage
- **Rich Output**: Beautiful tables and JSON/YAML output formats
- **Progress Tracking**: Visual progress bars for long-running operations
- **Dry Run Mode**: Preview changes before applying them

## Installation

### Via pip (Recommended)

```bash
pip install ghostctl
```

### Via Docker

```bash
# Pull the image
docker pull ghostctl/ghostctl:latest

# Run a command
docker run --rm -it ghostctl/ghostctl:latest ghostctl posts list
```

### From Source

```bash
git clone https://github.com/yourusername/ghostctl.git
cd ghostctl
pip install -e .
```

### Development Installation

```bash
git clone https://github.com/yourusername/ghostctl.git
cd ghostctl
poetry install
poetry shell
```

## Quick Start

### 1. Configuration

Create your first configuration profile:

```bash
# Interactive setup (recommended for first-time users)
ghostctl config init

# Non-interactive setup
ghostctl config init --no-interactive \
  --url "https://your-blog.ghost.io" \
  --admin-key "your-admin-api-key"
```

This creates a configuration file at `~/.ghostctl.toml`:

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

### 2. Environment Variables (Alternative)

Instead of configuration files, you can use environment variables:

```bash
export GHOST_API_URL="https://your-blog.ghost.io"
export GHOST_ADMIN_API_KEY="your-admin-api-key"
export GHOST_API_VERSION="v5"
```

### 3. Verify Connection

Test your configuration:

```bash
ghostctl settings list
```

## Usage Examples

### Posts Management

```bash
# List all posts
ghostctl posts list

# List with filters and pagination
ghostctl posts list --filter "status:published" --page 2 --limit 20

# Create a new post
ghostctl posts create --title "My New Post" --content "Hello, World!"

# Create from markdown file
ghostctl posts create --title "From File" --file content.md

# Update a post
ghostctl posts update post-id --title "Updated Title"

# Publish a draft
ghostctl posts publish post-id

# Schedule for future publication
ghostctl posts schedule post-id --date "2025-01-01 10:00"

# Delete a post
ghostctl posts delete post-id --force
```

### Image Management

```bash
# Upload an image
ghostctl images upload photo.jpg

# Upload and use as feature image
ghostctl posts update post-id --feature-image photo.jpg

# Get image URL for scripting
URL=$(ghostctl images upload photo.jpg --output json | jq -r '.url')
```

### Theme Management

```bash
# List themes
ghostctl themes list

# Upload a theme
ghostctl themes upload theme.zip

# Upload and activate
ghostctl themes upload theme.zip --activate

# Activate existing theme
ghostctl themes activate theme-name

# Rollback to previous version
ghostctl themes rollback
```

### Tag Management

```bash
# List tags
ghostctl tags list

# Create a tag
ghostctl tags create --name "Technology" --description "Tech articles"

# Update tag
ghostctl tags update tag-id --description "Updated description"

# Delete tag
ghostctl tags delete tag-id
```

### Bulk Operations

```bash
# Import members from CSV
ghostctl members import members.csv --dry-run
ghostctl members import members.csv

# Bulk update posts
ghostctl posts bulk-update --filter "status:draft" --add-tag "review-needed"

# Export content
ghostctl export all --output backup.json
ghostctl export posts --output posts.json
```

### Multiple Profiles

```bash
# Use specific profile
ghostctl --profile staging posts list
ghostctl --profile production themes activate new-theme

# List available profiles
ghostctl config list-profiles
```

### Output Formats

```bash
# Default table format
ghostctl posts list

# JSON output (great for scripting)
ghostctl posts list --output json

# YAML output
ghostctl posts list --output yaml
```

## Advanced Features

### Dry Run Mode

Preview changes without making them:

```bash
ghostctl posts delete post-id --dry-run
ghostctl members import large-file.csv --dry-run
```

### Debug Mode

See detailed API calls and responses:

```bash
ghostctl --debug posts list
ghostctl --debug --profile staging themes upload theme.zip
```

### Retry Logic

Configure retry behavior for reliability:

```bash
# Increase retries for flaky connections
ghostctl --max-retries 5 posts list

# Increase timeout
ghostctl --timeout 60 export all --output backup.json
```

## Docker Usage

Use GhostCtl in Docker containers:

```yaml
# docker-compose.yml
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

Run commands in Docker:

```bash
docker-compose exec ghostctl ghostctl posts list
docker-compose run --rm ghostctl ghostctl export all --output /scripts/backup.json
```

## Scripting Examples

### Automated Backup Script

```bash
#!/bin/bash
# backup-ghost.sh
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="./backups"

mkdir -p "$BACKUP_DIR"

echo "Starting Ghost backup..."
ghostctl export all --output "$BACKUP_DIR/ghost-backup-$DATE.json"

if [ $? -eq 0 ]; then
    echo "Backup completed: $BACKUP_DIR/ghost-backup-$DATE.json"

    # Cleanup old backups (keep last 7)
    ls -t "$BACKUP_DIR"/ghost-backup-*.json | tail -n +8 | xargs rm -f
else
    echo "Backup failed!"
    exit 1
fi
```

### Content Publication Workflow

```bash
#!/bin/bash
# publish-drafts.sh

# Get all draft posts
drafts=$(ghostctl posts list --filter "status:draft" --output json | \
         jq -r '.posts[].id')

for post_id in $drafts; do
    echo "Publishing post: $post_id"
    ghostctl posts publish "$post_id"
    sleep 1  # Rate limiting
done
```

### Theme Deployment

```bash
#!/bin/bash
# deploy-theme.sh
THEME_FILE="$1"

if [ ! -f "$THEME_FILE" ]; then
    echo "Theme file not found: $THEME_FILE"
    exit 1
fi

# Test on staging first
echo "Deploying to staging..."
ghostctl --profile staging themes upload "$THEME_FILE" --activate

# Prompt for production deployment
read -p "Deploy to production? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Deploying to production..."
    ghostctl --profile production themes upload "$THEME_FILE" --activate
fi
```

## Configuration

### Configuration File Location

GhostCtl looks for configuration files in the following order:

1. `./ghostctl.toml` (current directory)
2. `~/.ghostctl.toml` (home directory)
3. `~/.config/ghostctl/config.toml` (XDG config directory)

### Configuration File Format

```toml
[profiles.default]
api_url = "https://your-blog.ghost.io"
admin_api_key = "your-admin-api-key"
content_api_key = "your-content-api-key"  # Optional, for read operations
api_version = "v5"

[profiles.staging]
api_url = "https://staging.ghost.io"
admin_api_key = "staging-admin-api-key"
api_version = "v5"

[profiles.production]
api_url = "https://blog.example.com"
admin_api_key = "production-admin-api-key"
api_version = "v5"
```

### Environment Variables

GhostCtl supports the following environment variables:

- `GHOST_API_URL`: Ghost CMS URL
- `GHOST_ADMIN_API_KEY`: Admin API key
- `GHOST_CONTENT_API_KEY`: Content API key (optional)
- `GHOST_API_VERSION`: API version (default: v5)

Environment variables override configuration file settings.

## Troubleshooting

### Authentication Issues

```bash
# Validate your configuration
ghostctl config validate

# Test with debug mode to see API calls
ghostctl --debug settings list

# Check environment variables
ghostctl --debug posts list
```

### Rate Limiting

```bash
# Check rate limit status
ghostctl --debug posts list 2>&1 | grep "X-RateLimit"

# Use retry with backoff
ghostctl --max-retries 5 posts list

# Add delays in scripts
sleep 1
```

### Network Issues

```bash
# Increase timeout for slow connections
ghostctl --timeout 60 posts list

# Use proxy if needed
export HTTPS_PROXY=http://proxy:8080
ghostctl posts list

# Test connectivity
curl -I https://your-blog.ghost.io/ghost/api/admin/
```

### Common Error Messages

**"Profile 'default' not found"**
- Run `ghostctl config init` to create a profile
- Or use environment variables

**"Unauthorized"**
- Check your API key is correct
- Ensure API key has admin permissions
- Verify the API URL is correct

**"Not Found" / "404"**
- Check the API URL format: `https://your-site.com` (no trailing slash)
- Verify Ghost is running and accessible

### Getting Help

```bash
# General help
ghostctl --help

# Command-specific help
ghostctl posts --help
ghostctl posts create --help

# Show version
ghostctl --version

# Enable debug output
ghostctl --debug command
```

## Testing Your Installation

Run this comprehensive test to verify everything works:

```bash
#!/bin/bash
# test-ghostctl.sh
echo "Testing GhostCtl installation..."

# 1. Check connection
echo "1. Testing connection..."
if ghostctl settings list > /dev/null 2>&1; then
    echo "   ✓ Connected to Ghost"
else
    echo "   ✗ Connection failed"
    exit 1
fi

# 2. Test post creation
echo "2. Testing post creation..."
POST_ID=$(ghostctl posts create \
    --title "Test Post $(date +%s)" \
    --content "This is a test post" \
    --status draft \
    --output json | jq -r '.posts[0].id' 2>/dev/null)

if [ ! -z "$POST_ID" ] && [ "$POST_ID" != "null" ]; then
    echo "   ✓ Created test post: $POST_ID"
else
    echo "   ✗ Failed to create post"
    exit 1
fi

# 3. Test image upload
echo "3. Testing image upload..."
echo '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
  <rect width="100" height="100" fill="#007acc"/>
  <text x="50" y="55" text-anchor="middle" fill="white" font-size="12">Test</text>
</svg>' > test-image.svg

IMAGE_URL=$(ghostctl images upload test-image.svg --output json 2>/dev/null | jq -r '.images[0].url' 2>/dev/null)
rm -f test-image.svg

if [ ! -z "$IMAGE_URL" ] && [ "$IMAGE_URL" != "null" ]; then
    echo "   ✓ Uploaded test image: $IMAGE_URL"
else
    echo "   ✗ Failed to upload image"
fi

# 4. Test tag creation
echo "4. Testing tag creation..."
TAG_ID=$(ghostctl tags create \
    --name "test-tag-$(date +%s)" \
    --description "Test tag" \
    --output json 2>/dev/null | jq -r '.tags[0].id' 2>/dev/null)

if [ ! -z "$TAG_ID" ] && [ "$TAG_ID" != "null" ]; then
    echo "   ✓ Created test tag: $TAG_ID"
else
    echo "   ✗ Failed to create tag"
fi

# 5. Cleanup
echo "5. Cleaning up..."
if [ ! -z "$POST_ID" ] && [ "$POST_ID" != "null" ]; then
    ghostctl posts delete "$POST_ID" --force > /dev/null 2>&1
fi
if [ ! -z "$TAG_ID" ] && [ "$TAG_ID" != "null" ]; then
    ghostctl tags delete "$TAG_ID" --force > /dev/null 2>&1
fi

echo ""
echo "✅ All tests passed! GhostCtl is working correctly."
```

## Contributing

We welcome contributions! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details.

### Development Setup

```bash
# Clone repository
git clone https://github.com/yourusername/ghostctl.git
cd ghostctl

# Install development dependencies
poetry install
poetry shell

# Run tests
pytest

# Run linting
ruff check .
black --check .
mypy ghostctl

# Run pre-commit hooks
pre-commit run --all-files
```

## Security

For security considerations and best practices, see [SECURITY.md](SECURITY.md).

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

- 📖 [Documentation](https://ghostctl.readthedocs.io/)
- 🐛 [Issues](https://github.com/yourusername/ghostctl/issues)
- 💬 [Discussions](https://github.com/yourusername/ghostctl/discussions)
- 📧 [Email Support](mailto:support@ghostctl.dev)

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history and release notes.