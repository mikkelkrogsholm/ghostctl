# GhostCtl CLI Reference

Complete command-line reference for GhostCtl, the Ghost CMS management tool.

## Global Options

These options are available for all commands:

```
--profile, -p TEXT        Configuration profile to use
--debug                   Enable debug output
--dry-run                 Show what would be done without making changes
--output, -o [table|json|yaml]  Output format (default: table)
--timeout INTEGER         Request timeout in seconds (default: 30)
--max-retries INTEGER     Maximum number of retry attempts (default: 3)
--version                 Show version and exit
--help, -h                Show help message and exit
```

## Main Commands

### ghostctl

```
Usage: ghostctl [OPTIONS] COMMAND [ARGS]...

  GhostCtl - Command-line tool for managing Ghost CMS instances.

  GhostCtl provides a comprehensive command-line interface for managing Ghost
  CMS instances including content management, user administration, theme
  management, and automation capabilities.

Options:
  --profile, -p TEXT              Configuration profile to use
  --debug                         Enable debug output
  --dry-run                       Show what would be done without making changes
  --output, -o [table|json|yaml]  Output format (table, json, yaml)
  --timeout INTEGER               Request timeout in seconds  [default: 30]
  --max-retries INTEGER           Maximum number of retry attempts  [default: 3]
  --version                       Show version and exit
  --help, -h                      Show this message and exit.

Commands:
  config    Manage configuration
  export    Export content
  images    Manage images
  members   Manage members
  pages     Manage pages
  posts     Manage posts
  settings  Manage settings
  tags      Manage tags
  themes    Manage themes
```

## config

Configuration management commands.

```
Usage: ghostctl config [OPTIONS] COMMAND [ARGS]...

  Manage configuration

Options:
  --help  Show this message and exit.

Commands:
  init           Initialize a new configuration profile
  list-profiles  List available configuration profiles
  validate       Validate configuration
  show           Show current configuration
  delete         Delete a configuration profile
```

### config init

```
Usage: ghostctl config init [OPTIONS]

  Initialize a new configuration profile.

  Creates a new configuration profile with Ghost CMS connection details.
  Can be run interactively or with provided options.

Options:
  --profile TEXT            Profile name  [default: default]
  --url TEXT               Ghost CMS URL
  --admin-key TEXT         Admin API key
  --content-key TEXT       Content API key
  --api-version TEXT       Ghost API version  [default: v5]
  --interactive / --no-interactive  Interactive setup  [default: interactive]
  --force                  Overwrite existing profile
  --help                   Show this message and exit.

Examples:
  # Interactive setup
  ghostctl config init

  # Non-interactive setup
  ghostctl config init --no-interactive --url "https://blog.example.com" --admin-key "key"

  # Create named profile
  ghostctl config init --profile production --url "https://blog.com"
```

### config list-profiles

```
Usage: ghostctl config list-profiles [OPTIONS]

  List available configuration profiles.

Options:
  --help  Show this message and exit.

Examples:
  ghostctl config list-profiles
```

### config validate

```
Usage: ghostctl config validate [OPTIONS]

  Validate configuration and test connection.

Options:
  --profile TEXT  Profile to validate
  --help          Show this message and exit.

Examples:
  ghostctl config validate
  ghostctl config validate --profile staging
```

### config show

```
Usage: ghostctl config show [OPTIONS]

  Show current configuration (redacts sensitive information).

Options:
  --profile TEXT  Profile to show
  --help          Show this message and exit.

Examples:
  ghostctl config show
  ghostctl config show --profile production
```

### config delete

```
Usage: ghostctl config delete [OPTIONS] PROFILE_NAME

  Delete a configuration profile.

Arguments:
  PROFILE_NAME  Name of profile to delete  [required]

Options:
  --force  Delete without confirmation
  --help   Show this message and exit.

Examples:
  ghostctl config delete staging
  ghostctl config delete old-profile --force
```

## posts

Post management commands.

```
Usage: ghostctl posts [OPTIONS] COMMAND [ARGS]...

  Manage posts

Options:
  --help  Show this message and exit.

Commands:
  list           List posts
  create         Create a new post
  update         Update an existing post
  delete         Delete a post
  publish        Publish a draft post
  unpublish      Unpublish a post
  schedule       Schedule a post for future publication
  bulk-update    Bulk update multiple posts
  bulk-publish   Bulk publish multiple posts
  bulk-delete    Bulk delete multiple posts
```

### posts list

```
Usage: ghostctl posts list [OPTIONS]

  List posts with filtering, pagination, and sorting options.

Options:
  --filter TEXT          Filter posts (e.g., 'status:published', 'tag:news')
  --page INTEGER         Page number  [default: 1]
  --limit INTEGER        Number of posts per page  [default: 15]
  --include TEXT         Include related data  [default: tags,authors]
  --order TEXT           Sort order  [default: updated_at DESC]
  --all                  Fetch all posts (may take time)
  --progress             Show progress bar for long operations
  --help                 Show this message and exit.

Examples:
  # List all posts
  ghostctl posts list

  # List published posts only
  ghostctl posts list --filter "status:published"

  # List with pagination
  ghostctl posts list --page 2 --limit 20

  # List posts by tag
  ghostctl posts list --filter "tag:technology"

  # List all posts with progress
  ghostctl posts list --all --progress
```

### posts create

```
Usage: ghostctl posts create [OPTIONS]

  Create a new post.

Options:
  --title TEXT            Post title  [required]
  --content TEXT          Post content
  --file PATH             Read content from markdown file
  --status [draft|published|scheduled]  Post status  [default: draft]
  --slug TEXT             Custom URL slug
  --excerpt TEXT          Post excerpt
  --tags TEXT             Comma-separated list of tags
  --authors TEXT          Comma-separated list of author emails
  --feature-image PATH    Feature image file to upload
  --meta-title TEXT       SEO meta title
  --meta-description TEXT SEO meta description
  --canonical-url TEXT    Canonical URL
  --publish-at TEXT       Publication date (YYYY-MM-DD HH:MM or ISO format)
  --help                  Show this message and exit.

Examples:
  # Create draft post
  ghostctl posts create --title "My New Post" --content "Post content here"

  # Create and publish immediately
  ghostctl posts create --title "Published Post" --content "Content" --status published

  # Create from markdown file
  ghostctl posts create --title "From File" --file content.md

  # Create with metadata
  ghostctl posts create --title "SEO Post" --content "Content" --meta-title "SEO Title" --tags "seo,marketing"

  # Schedule for future
  ghostctl posts create --title "Future Post" --content "Content" --status scheduled --publish-at "2025-01-01 10:00"
```

### posts update

```
Usage: ghostctl posts update [OPTIONS] POST_ID

  Update an existing post.

Arguments:
  POST_ID  Post ID or slug  [required]

Options:
  --title TEXT            New post title
  --content TEXT          New post content
  --file PATH             Read content from markdown file
  --status [draft|published|scheduled]  Post status
  --slug TEXT             Custom URL slug
  --excerpt TEXT          Post excerpt
  --tags TEXT             Comma-separated list of tags (replaces existing)
  --add-tags TEXT         Comma-separated list of tags to add
  --remove-tags TEXT      Comma-separated list of tags to remove
  --authors TEXT          Comma-separated list of author emails
  --feature-image PATH    Feature image file to upload
  --meta-title TEXT       SEO meta title
  --meta-description TEXT SEO meta description
  --canonical-url TEXT    Canonical URL
  --publish-at TEXT       Publication date (YYYY-MM-DD HH:MM or ISO format)
  --help                  Show this message and exit.

Examples:
  # Update title
  ghostctl posts update post-id --title "Updated Title"

  # Update content from file
  ghostctl posts update post-id --file updated-content.md

  # Add tags
  ghostctl posts update post-id --add-tags "new-tag,another-tag"

  # Update feature image
  ghostctl posts update post-id --feature-image new-image.jpg
```

### posts delete

```
Usage: ghostctl posts delete [OPTIONS] POST_ID

  Delete a post.

Arguments:
  POST_ID  Post ID or slug  [required]

Options:
  --force  Delete without confirmation
  --help   Show this message and exit.

Examples:
  # Delete with confirmation
  ghostctl posts delete post-id

  # Force delete without confirmation
  ghostctl posts delete post-id --force
```

### posts publish

```
Usage: ghostctl posts publish [OPTIONS] POST_ID

  Publish a draft post immediately.

Arguments:
  POST_ID  Post ID or slug  [required]

Options:
  --help  Show this message and exit.

Examples:
  ghostctl posts publish post-id
```

### posts unpublish

```
Usage: ghostctl posts unpublish [OPTIONS] POST_ID

  Unpublish a post (convert to draft).

Arguments:
  POST_ID  Post ID or slug  [required]

Options:
  --help  Show this message and exit.

Examples:
  ghostctl posts unpublish post-id
```

### posts schedule

```
Usage: ghostctl posts schedule [OPTIONS] POST_ID

  Schedule a post for future publication.

Arguments:
  POST_ID  Post ID or slug  [required]

Options:
  --date TEXT  Publication date (YYYY-MM-DD HH:MM or ISO format)  [required]
  --help       Show this message and exit.

Examples:
  # Schedule for specific date and time
  ghostctl posts schedule post-id --date "2025-01-01 10:00"

  # Schedule using ISO format
  ghostctl posts schedule post-id --date "2025-01-01T10:00:00Z"
```

### posts bulk-update

```
Usage: ghostctl posts bulk-update [OPTIONS]

  Bulk update multiple posts matching filter criteria.

Options:
  --filter TEXT        Filter criteria for posts to update  [required]
  --status [draft|published|scheduled]  New status for all matching posts
  --add-tag TEXT       Tag to add to all matching posts
  --remove-tag TEXT    Tag to remove from all matching posts
  --add-author TEXT    Author email to add to all matching posts
  --remove-author TEXT Author email to remove from all matching posts
  --batch-size INTEGER Number of posts to process at once  [default: 10]
  --progress           Show progress bar
  --help               Show this message and exit.

Examples:
  # Add tag to all drafts
  ghostctl posts bulk-update --filter "status:draft" --add-tag "needs-review"

  # Publish all posts with specific tag
  ghostctl posts bulk-update --filter "tag:ready-to-publish" --status published
```

### posts bulk-publish

```
Usage: ghostctl posts bulk-publish [OPTIONS]

  Bulk publish multiple draft posts.

Options:
  --filter TEXT        Filter criteria for posts to publish  [default: status:draft]
  --batch-size INTEGER Number of posts to process at once  [default: 10]
  --progress           Show progress bar
  --help               Show this message and exit.

Examples:
  # Publish all drafts
  ghostctl posts bulk-publish

  # Publish drafts with specific tag
  ghostctl posts bulk-publish --filter "status:draft+tag:ready"
```

### posts bulk-delete

```
Usage: ghostctl posts bulk-delete [OPTIONS]

  Bulk delete multiple posts.

Options:
  --filter TEXT        Filter criteria for posts to delete  [required]
  --batch-size INTEGER Number of posts to process at once  [default: 10]
  --progress           Show progress bar
  --force              Delete without confirmation for each post
  --help               Show this message and exit.

Examples:
  # Delete all posts with specific tag
  ghostctl posts bulk-delete --filter "tag:old-content" --force

  # Delete drafts older than certain date
  ghostctl posts bulk-delete --filter "status:draft+created_at:<2024-01-01"
```

## pages

Page management commands (similar structure to posts).

```
Usage: ghostctl pages [OPTIONS] COMMAND [ARGS]...

  Manage pages

Options:
  --help  Show this message and exit.

Commands:
  list     List pages
  create   Create a new page
  update   Update an existing page
  delete   Delete a page
  publish  Publish a draft page
```

## tags

Tag management commands.

```
Usage: ghostctl tags [OPTIONS] COMMAND [ARGS]...

  Manage tags

Options:
  --help  Show this message and exit.

Commands:
  list    List tags
  create  Create a new tag
  update  Update an existing tag
  delete  Delete a tag
```

### tags list

```
Usage: ghostctl tags list [OPTIONS]

  List all tags.

Options:
  --filter TEXT    Filter tags (e.g., 'name:technology')
  --order TEXT     Sort order  [default: name ASC]
  --limit INTEGER  Number of tags per page  [default: 50]
  --include TEXT   Include related data  [default: count.posts]
  --help           Show this message and exit.

Examples:
  ghostctl tags list
  ghostctl tags list --filter "name:tech"
```

### tags create

```
Usage: ghostctl tags create [OPTIONS]

  Create a new tag.

Options:
  --name TEXT         Tag name  [required]
  --slug TEXT         Custom URL slug
  --description TEXT  Tag description
  --color TEXT        Tag color (hex code)
  --image PATH        Tag image file to upload
  --meta-title TEXT   SEO meta title
  --meta-description TEXT  SEO meta description
  --help              Show this message and exit.

Examples:
  # Create simple tag
  ghostctl tags create --name "Technology"

  # Create tag with metadata
  ghostctl tags create --name "JavaScript" --description "JS articles" --color "#f7df1e"
```

### tags update

```
Usage: ghostctl tags update [OPTIONS] TAG_ID

  Update an existing tag.

Arguments:
  TAG_ID  Tag ID or slug  [required]

Options:
  --name TEXT         New tag name
  --slug TEXT         Custom URL slug
  --description TEXT  Tag description
  --color TEXT        Tag color (hex code)
  --image PATH        Tag image file to upload
  --meta-title TEXT   SEO meta title
  --meta-description TEXT  SEO meta description
  --help              Show this message and exit.

Examples:
  ghostctl tags update tag-id --description "Updated description"
  ghostctl tags update javascript --color "#f0db4f"
```

### tags delete

```
Usage: ghostctl tags delete [OPTIONS] TAG_ID

  Delete a tag.

Arguments:
  TAG_ID  Tag ID or slug  [required]

Options:
  --force  Delete without confirmation
  --help   Show this message and exit.

Examples:
  ghostctl tags delete tag-id
  ghostctl tags delete old-tag --force
```

## images

Image management commands.

```
Usage: ghostctl images [OPTIONS] COMMAND [ARGS]...

  Manage images

Options:
  --help  Show this message and exit.

Commands:
  upload  Upload an image
  list    List uploaded images
  delete  Delete an image
```

### images upload

```
Usage: ghostctl images upload [OPTIONS] IMAGE_FILE

  Upload an image to Ghost CMS.

Arguments:
  IMAGE_FILE  Path to image file  [required]

Options:
  --purpose [image|profile_image|cover|icon]  Upload purpose  [default: image]
  --alt-text TEXT                            Alt text for accessibility
  --help                                     Show this message and exit.

Examples:
  # Upload regular image
  ghostctl images upload photo.jpg

  # Upload profile image
  ghostctl images upload avatar.png --purpose profile_image

  # Upload with alt text
  ghostctl images upload chart.png --alt-text "Sales chart for Q4"
```

### images list

```
Usage: ghostctl images list [OPTIONS]

  List uploaded images.

Options:
  --limit INTEGER  Number of images to list  [default: 50]
  --help           Show this message and exit.

Examples:
  ghostctl images list
  ghostctl images list --limit 100
```

### images delete

```
Usage: ghostctl images delete [OPTIONS] IMAGE_URL

  Delete an uploaded image.

Arguments:
  IMAGE_URL  Full URL of the image to delete  [required]

Options:
  --force  Delete without confirmation
  --help   Show this message and exit.

Examples:
  ghostctl images delete "https://blog.example.com/content/images/2024/photo.jpg"
  ghostctl images delete "https://blog.example.com/content/images/2024/photo.jpg" --force
```

## themes

Theme management commands.

```
Usage: ghostctl themes [OPTIONS] COMMAND [ARGS]...

  Manage themes

Options:
  --help  Show this message and exit.

Commands:
  list      List themes
  upload    Upload a theme
  activate  Activate a theme
  delete    Delete a theme
  rollback  Rollback to previous theme version
  download  Download active theme
```

### themes list

```
Usage: ghostctl themes list [OPTIONS]

  List all installed themes.

Options:
  --help  Show this message and exit.

Examples:
  ghostctl themes list
```

### themes upload

```
Usage: ghostctl themes upload [OPTIONS] THEME_FILE

  Upload a theme to Ghost CMS.

Arguments:
  THEME_FILE  Path to theme ZIP file  [required]

Options:
  --activate      Activate theme after upload
  --overwrite     Overwrite existing theme with same name
  --validate-only Validate theme without uploading
  --help          Show this message and exit.

Examples:
  # Upload theme
  ghostctl themes upload my-theme.zip

  # Upload and activate
  ghostctl themes upload my-theme.zip --activate

  # Validate theme without uploading
  ghostctl themes upload my-theme.zip --validate-only
```

### themes activate

```
Usage: ghostctl themes activate [OPTIONS] THEME_NAME

  Activate an installed theme.

Arguments:
  THEME_NAME  Name of theme to activate  [required]

Options:
  --help  Show this message and exit.

Examples:
  ghostctl themes activate casper
  ghostctl themes activate my-custom-theme
```

### themes delete

```
Usage: ghostctl themes delete [OPTIONS] THEME_NAME

  Delete an installed theme.

Arguments:
  THEME_NAME  Name of theme to delete  [required]

Options:
  --force  Delete without confirmation
  --help   Show this message and exit.

Examples:
  ghostctl themes delete old-theme
  ghostctl themes delete unused-theme --force
```

### themes rollback

```
Usage: ghostctl themes rollback [OPTIONS]

  Rollback to previous theme version.

Options:
  --version TEXT  Specific version to rollback to
  --help          Show this message and exit.

Examples:
  # Rollback to previous version
  ghostctl themes rollback

  # Rollback to specific version
  ghostctl themes rollback --version 1.2.3
```

### themes download

```
Usage: ghostctl themes download [OPTIONS]

  Download the currently active theme.

Options:
  --output PATH  Output file path  [default: active-theme.zip]
  --help         Show this message and exit.

Examples:
  ghostctl themes download
  ghostctl themes download --output backup-theme.zip
```

## members

Member management commands.

```
Usage: ghostctl members [OPTIONS] COMMAND [ARGS]...

  Manage members

Options:
  --help  Show this message and exit.

Commands:
  list     List members
  create   Create a new member
  update   Update an existing member
  delete   Delete a member
  import   Import members from CSV
  export   Export members to CSV
```

### members list

```
Usage: ghostctl members list [OPTIONS]

  List members with filtering and pagination.

Options:
  --filter TEXT    Filter members (e.g., 'status:paid', 'name:john')
  --order TEXT     Sort order  [default: created_at DESC]
  --limit INTEGER  Number of members per page  [default: 50]
  --page INTEGER   Page number  [default: 1]
  --include TEXT   Include related data
  --help           Show this message and exit.

Examples:
  # List all members
  ghostctl members list

  # List paid members only
  ghostctl members list --filter "status:paid"

  # List with pagination
  ghostctl members list --page 2 --limit 100
```

### members create

```
Usage: ghostctl members create [OPTIONS]

  Create a new member.

Options:
  --email TEXT     Member email address  [required]
  --name TEXT      Member name
  --note TEXT      Member note
  --subscribe      Subscribe to newsletter
  --send-email     Send welcome email
  --labels TEXT    Comma-separated list of labels
  --help           Show this message and exit.

Examples:
  # Create basic member
  ghostctl members create --email "user@example.com" --name "John Doe"

  # Create member with subscription
  ghostctl members create --email "subscriber@example.com" --subscribe --send-email

  # Create member with labels
  ghostctl members create --email "vip@example.com" --labels "vip,premium"
```

### members import

```
Usage: ghostctl members import [OPTIONS] CSV_FILE

  Import members from a CSV file.

Arguments:
  CSV_FILE  Path to CSV file with member data  [required]

Options:
  --mapping TEXT   Custom field mapping (email:0,name:1,note:2)
  --subscribe      Subscribe all imported members
  --send-email     Send welcome emails to imported members
  --batch-size INTEGER  Number of members to import at once  [default: 100]
  --progress       Show progress bar
  --help           Show this message and exit.

Examples:
  # Import from CSV
  ghostctl members import members.csv

  # Import with custom mapping
  ghostctl members import data.csv --mapping "email:0,name:1,labels:3"

  # Import with subscription
  ghostctl members import members.csv --subscribe --progress
```

### members export

```
Usage: ghostctl members export [OPTIONS]

  Export members to a CSV file.

Options:
  --output PATH    Output CSV file path  [default: members.csv]
  --filter TEXT    Filter members to export
  --fields TEXT    Comma-separated list of fields to export
  --help           Show this message and exit.

Examples:
  # Export all members
  ghostctl members export

  # Export to specific file
  ghostctl members export --output premium-members.csv --filter "status:paid"

  # Export specific fields
  ghostctl members export --fields "email,name,created_at"
```

## export

Content export commands.

```
Usage: ghostctl export [OPTIONS] COMMAND [ARGS]...

  Export content

Options:
  --help  Show this message and exit.

Commands:
  all      Export all content
  posts    Export posts only
  pages    Export pages only
  members  Export members only
  tags     Export tags only
  settings Export settings only
```

### export all

```
Usage: ghostctl export all [OPTIONS] OUTPUT_FILE

  Export all Ghost content to a JSON file.

Arguments:
  OUTPUT_FILE  Output file path (.json)  [required]

Options:
  --include-members / --no-members      Include member data  [default: include-members]
  --include-content / --no-content      Include posts and pages  [default: include-content]
  --include-settings / --no-settings    Include site settings  [default: include-settings]
  --include-themes / --no-themes        Include theme information
  --compress                            Compress output file
  --help                                Show this message and exit.

Examples:
  # Export everything
  ghostctl export all backup.json

  # Export without members
  ghostctl export all content-only.json --no-members

  # Export with compression
  ghostctl export all backup.json --compress
```

### export posts

```
Usage: ghostctl export posts [OPTIONS]

  Export posts to JSON or CSV format.

Options:
  --output PATH    Output file path  [default: posts.json]
  --format [json|csv]  Output format  [default: json]
  --filter TEXT    Filter posts to export
  --include TEXT   Include related data  [default: tags,authors]
  --help           Show this message and exit.

Examples:
  # Export all posts to JSON
  ghostctl export posts

  # Export to CSV
  ghostctl export posts --output posts.csv --format csv

  # Export published posts only
  ghostctl export posts --filter "status:published"
```

## settings

Settings management commands.

```
Usage: ghostctl settings [OPTIONS] COMMAND [ARGS]...

  Manage settings

Options:
  --help  Show this message and exit.

Commands:
  list    List current settings
  get     Get a specific setting
  set     Set a setting value
  backup  Backup current settings
  restore Restore settings from backup
```

### settings list

```
Usage: ghostctl settings list [OPTIONS]

  List current Ghost settings.

Options:
  --filter TEXT  Filter settings by key pattern
  --help         Show this message and exit.

Examples:
  # List all settings
  ghostctl settings list

  # List specific settings
  ghostctl settings list --filter "title"
```

### settings get

```
Usage: ghostctl settings get [OPTIONS] SETTING_KEY

  Get the value of a specific setting.

Arguments:
  SETTING_KEY  Setting key to retrieve  [required]

Options:
  --help  Show this message and exit.

Examples:
  ghostctl settings get title
  ghostctl settings get timezone
```

### settings set

```
Usage: ghostctl settings set [OPTIONS] SETTING_KEY VALUE

  Set the value of a specific setting.

Arguments:
  SETTING_KEY  Setting key to update  [required]
  VALUE        New value for the setting  [required]

Options:
  --help  Show this message and exit.

Examples:
  ghostctl settings set title "My New Blog Title"
  ghostctl settings set timezone "America/New_York"
```

## Filter Syntax

Many commands support filtering with a consistent syntax:

### Basic Filters
- `status:published` - Filter by status
- `tag:technology` - Filter by tag
- `author:john@example.com` - Filter by author

### Date Filters
- `created_at:>2024-01-01` - Created after date
- `updated_at:<2024-12-31` - Updated before date
- `published_at:2024-01-01..2024-12-31` - Published in date range

### Combining Filters
- `status:published+tag:news` - Multiple conditions (AND)
- `status:draft,status:scheduled` - Alternative conditions (OR)

### Text Filters
- `title:~"marketing"` - Title contains text
- `slug:^"how-to"` - Slug starts with text
- `content:~"tutorial"` - Content contains text

## Output Formats

All list commands support multiple output formats:

### Table Format (Default)
```bash
ghostctl posts list
# Displays formatted table with columns
```

### JSON Format
```bash
ghostctl posts list --output json
# Returns structured JSON data
```

### YAML Format
```bash
ghostctl posts list --output yaml
# Returns YAML formatted data
```

## Environment Variables

GhostCtl recognizes these environment variables:

- `GHOST_API_URL` - Ghost CMS URL
- `GHOST_ADMIN_API_KEY` - Admin API key
- `GHOST_CONTENT_API_KEY` - Content API key (for read operations)
- `GHOST_API_VERSION` - API version (default: v5)
- `HTTPS_PROXY` - HTTPS proxy URL
- `GHOSTCTL_CONFIG_FILE` - Custom config file path

## Exit Codes

GhostCtl uses standard exit codes:

- `0` - Success
- `1` - General error
- `2` - Misuse of shell command
- `130` - Interrupted by user (Ctrl+C)

## Examples by Use Case

### Content Management Workflow

```bash
# Create draft post
ghostctl posts create --title "New Article" --file content.md

# Review and add tags
ghostctl posts update post-123 --add-tags "tutorial,beginner"

# Publish when ready
ghostctl posts publish post-123
```

### Bulk Operations

```bash
# Tag all drafts for review
ghostctl posts bulk-update --filter "status:draft" --add-tag "needs-review"

# Publish all reviewed posts
ghostctl posts bulk-publish --filter "tag:ready-to-publish"
```

### Backup and Migration

```bash
# Full backup
ghostctl export all backup-$(date +%Y%m%d).json

# Migrate content between instances
ghostctl --profile source export posts --output posts.json
ghostctl --profile target import posts --file posts.json
```

### Theme Management

```bash
# Deploy new theme
ghostctl themes upload new-theme.zip --activate

# Rollback if issues
ghostctl themes rollback
```

### Member Management

```bash
# Import new members
ghostctl members import new-subscribers.csv --subscribe

# Export premium members
ghostctl members export --filter "status:paid" --output premium.csv
```

---

For more examples and detailed usage, see the [README](README.md) and [online documentation](https://ghostctl.readthedocs.io/).