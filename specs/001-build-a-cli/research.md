# Research Findings: Ghost CMS Management CLI

**Date**: 2025-09-22
**Feature**: ghostctl - Ghost CMS Management CLI

## Technical Decisions

### 1. Ghost Admin API Authentication
**Decision**: Use PyJWT for JWT token generation
**Rationale**:
- Ghost Admin API requires JWT tokens signed with the admin API key
- PyJWT is the standard Python library for JWT handling
- Supports HS256 algorithm required by Ghost
**Alternatives considered**:
- python-jose: More complex, unnecessary features
- Manual implementation: Error-prone, reinventing the wheel

### 2. HTTP Client Library
**Decision**: Use Requests with retry mechanism
**Rationale**:
- Most mature and widely-used Python HTTP library
- Built-in session management for connection pooling
- Easy to add retry logic with urllib3.util.retry
**Alternatives considered**:
- httpx: Async support unnecessary for CLI tool
- aiohttp: Complexity of async not justified for this use case

### 3. CLI Framework
**Decision**: Use Typer
**Rationale**:
- Modern Python CLI framework built on Click
- Automatic help generation from type hints
- Native support for subcommands (posts, tags, etc.)
- Excellent documentation and examples support
**Alternatives considered**:
- Click: More verbose, less modern API
- argparse: Too low-level for complex CLI
- Fire: Less control over CLI structure

### 4. Data Validation
**Decision**: Use Pydantic v2
**Rationale**:
- Native Python type hints support
- Automatic validation at API boundaries
- JSON Schema generation for Ghost API compatibility
- Excellent error messages
**Alternatives considered**:
- marshmallow: More verbose, less integrated with type hints
- dataclasses: No built-in validation
- attrs: Less feature-rich for validation

### 5. Configuration Management
**Decision**: Use tomllib (Python 3.11+ stdlib) with TOML format
**Rationale**:
- TOML is human-readable and standard for Python tools
- tomllib is part of stdlib in Python 3.11+
- Supports nested configuration for multiple profiles
**Alternatives considered**:
- ConfigParser with INI: Less expressive format
- JSON: Not human-friendly for editing
- YAML: Additional dependency, security concerns

### 6. Output Formatting
**Decision**: Rich for tables, built-in json, PyYAML for YAML
**Rationale**:
- Rich provides beautiful terminal output with minimal code
- Native JSON support in Python stdlib
- PyYAML is the standard for YAML in Python
**Alternatives considered**:
- tabulate: Less feature-rich than Rich
- PrettyTable: Outdated, less maintained
- Custom formatting: Unnecessary complexity

### 7. Testing Strategy
**Decision**: pytest with pytest-mock and pytest-httpx
**Rationale**:
- pytest is the de facto standard for Python testing
- pytest-mock simplifies mocking Ghost API calls
- pytest-httpx for testing HTTP interactions
**Alternatives considered**:
- unittest: More verbose, less features
- nose2: Less popular, fewer plugins

### 8. Rate Limiting Strategy
**Decision**: Exponential backoff with circuit breaker pattern
**Rationale**:
- Ghost API has 100 req/min limit
- Exponential backoff prevents hammering the API
- Circuit breaker prevents cascading failures
**Implementation**:
- Initial retry delay: 1 second
- Max retries: 5
- Backoff multiplier: 2
- Circuit opens after 3 consecutive failures

### 9. Credential Storage
**Decision**: Multiple methods with clear precedence
**Rationale**:
- Environment variables for CI/CD (highest priority)
- TOML profiles for local development
- Keyring integration for secure storage (future enhancement)
**Security measures**:
- Never log API keys
- Mask keys in debug output
- Clear documentation on secure practices

### 10. Bulk Operations Approach
**Decision**: Chunked processing with progress bars
**Rationale**:
- Process in chunks of 10-20 items
- Rich progress bars for user feedback
- Transaction-like behavior with rollback on failure
**Alternatives considered**:
- Parallel processing: Ghost API rate limits make this impractical
- Single transaction: Too risky for large operations

## Resolved Clarifications

### From Specification

1. **Rate limit strategy** (FR-045)
   - Resolved: Exponential backoff with max 5 retries
   - Circuit breaker after 3 consecutive failures
   - Clear user feedback on rate limit hits

2. **Maximum posts/members handling** (FR-042)
   - Resolved: Support up to 100k items with pagination
   - Use Ghost API pagination (15 items default, 100 max)
   - Lazy loading for list operations

3. **Response time requirements** (FR-043)
   - Resolved: <500ms for single operations
   - <10s for 100-item bulk operations
   - Progress indication after 1s

4. **Large export handling**
   - Resolved: Stream to file for exports >10MB
   - Chunked reading for imports
   - Memory-efficient processing

5. **Modifiable settings** (FR-026)
   - Resolved: Support these settings initially:
     - Site title, description, logo, icon
     - Default locale, timezone
     - Social accounts
     - Meta data settings
   - Extensible design for future settings

## Ghost API Specifics

### API Versions
- Target Ghost API v5.0+ (current stable)
- Version negotiation via Accept-Version header
- Graceful degradation for older versions

### Authentication Flow
1. Generate JWT token with admin API key
2. Include token in Authorization header
3. Token expires after 5 minutes
4. Auto-refresh on expiry

### Content Format
- Ghost uses Mobiledoc format for content
- Support both HTML and Mobiledoc input
- Lexical format support for Ghost 5.0+

### Image Upload
- Requires multipart/form-data
- Supports JPEG, PNG, GIF, SVG, ICO
- Max file size: 50MB (configurable per Ghost instance)

### Theme Management
- Themes uploaded as ZIP files
- Validation via GScan before activation
- Keep last 3 versions for rollback

## Dependencies Summary

### Core Dependencies
```toml
[tool.poetry.dependencies]
python = "^3.11"
typer = "^0.12.0"
requests = "^2.32.0"
pyjwt = "^2.8.0"
pydantic = "^2.5.0"
rich = "^13.7.0"
pyyaml = "^6.0"
python-dateutil = "^2.9.0"
```

### Development Dependencies
```toml
[tool.poetry.group.dev.dependencies]
pytest = "^8.0.0"
pytest-mock = "^3.12.0"
pytest-cov = "^4.1.0"
mypy = "^1.8.0"
black = "^24.0.0"
isort = "^5.13.0"
ruff = "^0.3.0"
bandit = "^1.7.0"
```

## Performance Optimizations

1. **Connection Pooling**: Reuse HTTP connections via requests.Session
2. **Response Caching**: Cache read operations for 60 seconds
3. **Lazy Loading**: Don't fetch full content unless requested
4. **Bulk Operations**: Process in chunks with configurable size
5. **Progress Feedback**: Show progress for operations >1 second

## Error Handling Strategy

1. **Network Errors**: Retry with exponential backoff
2. **Auth Errors**: Clear message to check credentials
3. **Validation Errors**: Show exact field and constraint violated
4. **Rate Limits**: Wait and retry with user feedback
5. **Partial Failures**: Report succeeded/failed items separately

## Next Steps

With all technical decisions made and clarifications resolved, we can proceed to Phase 1: Design & Contracts. The research confirms our technical stack is appropriate for the requirements and aligns with the constitution principles.