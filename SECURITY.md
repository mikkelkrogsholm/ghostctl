# Security Policy

## Overview

GhostCtl handles sensitive information including API keys, authentication tokens, and access to your Ghost CMS content. This document outlines security best practices and our approach to protecting your data.

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Credential Management

### API Key Security

**Never hardcode API keys in scripts or commit them to version control.**

#### ✅ Secure Practices

1. **Use Environment Variables**
   ```bash
   export GHOST_ADMIN_API_KEY="your-key-here"
   export GHOST_API_URL="https://your-site.com"
   ghostctl posts list
   ```

2. **Use Configuration Files with Proper Permissions**
   ```bash
   # Set restrictive permissions
   chmod 600 ~/.ghostctl.toml

   # Verify permissions
   ls -la ~/.ghostctl.toml
   # Should show: -rw------- (only owner can read/write)
   ```

3. **Use Secret Management Systems**
   ```bash
   # AWS Systems Manager Parameter Store
   export GHOST_ADMIN_API_KEY=$(aws ssm get-parameter \
     --name "/ghostctl/admin-key" \
     --with-decryption \
     --query 'Parameter.Value' \
     --output text)

   # HashiCorp Vault
   export GHOST_ADMIN_API_KEY=$(vault kv get -field=key secret/ghostctl)

   # Azure Key Vault
   export GHOST_ADMIN_API_KEY=$(az keyvault secret show \
     --vault-name MyKeyVault \
     --name ghostctl-admin-key \
     --query value -o tsv)
   ```

#### ❌ Insecure Practices

```bash
# DON'T: Hardcode in scripts
ghostctl --admin-key "1234567890abcdef" posts list

# DON'T: Store in shell history
export GHOST_ADMIN_API_KEY="1234567890abcdef"  # This goes to history

# DON'T: Use in CI/CD without secrets management
# docker run -e GHOST_ADMIN_API_KEY="plaintext-key" ghostctl
```

### Configuration File Security

#### Location and Permissions

GhostCtl configuration files should be protected with appropriate filesystem permissions:

```bash
# Create config directory with proper permissions
mkdir -p ~/.config/ghostctl
chmod 700 ~/.config/ghostctl

# Create config file with restrictive permissions
touch ~/.config/ghostctl/config.toml
chmod 600 ~/.config/ghostctl/config.toml
```

#### Configuration File Format

Store only non-sensitive configuration in the file:

```toml
# ~/.ghostctl.toml
[profiles.default]
api_url = "https://your-blog.ghost.io"
api_version = "v5"
# NOTE: API keys should be in environment variables, not here

[profiles.staging]
api_url = "https://staging.ghost.io"
api_version = "v5"
```

#### Environment Variable Override

Always use environment variables for sensitive data:

```bash
# Set in your shell profile (~/.bashrc, ~/.zshrc)
export GHOST_ADMIN_API_KEY="your-admin-key"
export GHOST_CONTENT_API_KEY="your-content-key"
```

### Docker Security

#### Secrets Management

```dockerfile
# Use secrets in Docker Compose
version: '3.8'
services:
  ghostctl:
    image: ghostctl:latest
    environment:
      - GHOST_API_URL=https://blog.example.com
    secrets:
      - ghost_admin_key
    command: ghostctl posts list

secrets:
  ghost_admin_key:
    file: ./secrets/admin_key.txt
```

#### Runtime Security

```bash
# Use Docker secrets
echo "your-admin-key" | docker secret create ghost_admin_key -

# Run with secrets
docker service create \
  --name ghostctl \
  --secret ghost_admin_key \
  --env GHOST_ADMIN_API_KEY_FILE=/run/secrets/ghost_admin_key \
  ghostctl:latest
```

### CI/CD Security

#### GitHub Actions

```yaml
# .github/workflows/deploy.yml
name: Deploy
on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Deploy content
        env:
          GHOST_API_URL: ${{ secrets.GHOST_API_URL }}
          GHOST_ADMIN_API_KEY: ${{ secrets.GHOST_ADMIN_API_KEY }}
        run: |
          pip install ghostctl
          ghostctl posts publish-scheduled
```

#### GitLab CI

```yaml
# .gitlab-ci.yml
deploy:
  stage: deploy
  variables:
    GHOST_API_URL: $GHOST_API_URL  # Set in GitLab CI/CD variables
  script:
    - pip install ghostctl
    - ghostctl posts publish-scheduled
  only:
    - main
```

#### Jenkins

```groovy
pipeline {
    agent any
    environment {
        GHOST_API_URL = credentials('ghost-api-url')
        GHOST_ADMIN_API_KEY = credentials('ghost-admin-key')
    }
    stages {
        stage('Deploy') {
            steps {
                sh 'pip install ghostctl'
                sh 'ghostctl posts publish-scheduled'
            }
        }
    }
}
```

## Network Security

### HTTPS Enforcement

GhostCtl enforces HTTPS for all API communications:

```bash
# ✅ Secure - HTTPS URLs
export GHOST_API_URL="https://blog.example.com"

# ❌ Insecure - HTTP URLs (will be rejected)
export GHOST_API_URL="http://blog.example.com"
```

### Proxy Configuration

For corporate environments with proxies:

```bash
# Set proxy with authentication
export HTTPS_PROXY="https://user:pass@proxy.company.com:8080"
export NO_PROXY="localhost,127.0.0.1,.local"

# Verify proxy is working
ghostctl --debug settings list
```

### Certificate Validation

GhostCtl validates SSL certificates by default. For development environments:

```bash
# Only for development - NOT recommended for production
export PYTHONHTTPSVERIFY=0  # Disables certificate verification
```

## Authentication Security

### JWT Token Handling

GhostCtl uses JWT tokens for authentication with Ghost's Admin API:

- Tokens are generated locally using your admin API key
- Tokens are short-lived (5 minutes by default)
- Tokens are not stored persistently
- New tokens are generated for each request

### API Key Rotation

Regularly rotate your API keys:

1. **Generate new API key in Ghost Admin**
   - Go to Settings > Integrations
   - Create new custom integration or regenerate existing key

2. **Update your environment variables**
   ```bash
   # Update environment variable
   export GHOST_ADMIN_API_KEY="new-key-here"

   # Test new key
   ghostctl settings list
   ```

3. **Update CI/CD secrets**
   - Update secrets in GitHub Actions, GitLab CI, etc.
   - Verify deployments still work

### Access Control

#### Principle of Least Privilege

Use Content API keys for read-only operations:

```bash
# Read-only operations
export GHOST_CONTENT_API_KEY="content-key"
ghostctl posts list        # Uses content API (read-only)
ghostctl tags list         # Uses content API (read-only)

# Write operations require admin API
export GHOST_ADMIN_API_KEY="admin-key"
ghostctl posts create --title "New Post"  # Uses admin API
```

#### API Key Scoping

Create separate integrations for different use cases:

```toml
# ~/.ghostctl.toml
[profiles.readonly]
api_url = "https://blog.example.com"
# Only set content_api_key for read operations

[profiles.publisher]
api_url = "https://blog.example.com"
# Set admin_api_key with limited scope

[profiles.admin]
api_url = "https://blog.example.com"
# Full admin access
```

## Data Protection

### Sensitive Data in Outputs

GhostCtl automatically redacts sensitive information:

```bash
# API keys are redacted in debug output
ghostctl --debug settings list
# Shows: Using API key: [REDACTED]

# Full URLs may contain sensitive info
ghostctl --debug posts list --output json | jq '.debug.request_url'
# API keys in URLs are automatically redacted
```

### Backup Security

When exporting data, protect backup files:

```bash
# Export with encryption
ghostctl export all --output backup.json
gpg --symmetric --cipher-algo AES256 backup.json
rm backup.json  # Remove unencrypted file

# Restore from encrypted backup
gpg --decrypt backup.json.gpg > backup.json
ghostctl import all --file backup.json
rm backup.json  # Clean up
```

### Local File Security

Secure temporary files and outputs:

```bash
# Set umask for restrictive file permissions
umask 077

# Export to secure directory
mkdir -p ~/secure-backups
chmod 700 ~/secure-backups
ghostctl export all --output ~/secure-backups/backup-$(date +%Y%m%d).json
```

## Logging and Monitoring

### Security Logging

Monitor for security events:

```bash
# Enable audit logging in Ghost
# Check Ghost logs for API access patterns

# Monitor failed authentication attempts
tail -f /var/log/ghost/ghost.log | grep "401\|403"

# Monitor GhostCtl usage
ghostctl --debug posts list 2>&1 | logger -t ghostctl
```

### Access Monitoring

Track API usage:

```bash
# Log all GhostCtl commands
echo "$(date): $USER executed: ghostctl $*" >> ~/.ghostctl_audit.log

# Wrapper script for auditing
#!/bin/bash
# ghostctl-audit.sh
echo "$(date): $USER@$(hostname) executed: ghostctl $*" | \
  logger -t ghostctl-audit
exec ghostctl "$@"
```

## Incident Response

### Compromised API Key

If you suspect your API key is compromised:

1. **Immediately rotate the API key**
   ```bash
   # In Ghost Admin: Settings > Integrations > Regenerate Key
   ```

2. **Update all systems**
   ```bash
   # Update environment variables
   export GHOST_ADMIN_API_KEY="new-key"

   # Update CI/CD secrets
   # Update configuration files
   ```

3. **Audit recent activity**
   ```bash
   # Check Ghost admin logs
   # Review recent posts/changes
   ghostctl posts list --filter "updated_at:>$(date -d '24 hours ago' -Iseconds)"
   ```

4. **Monitor for unauthorized changes**
   ```bash
   # Regular content audits
   ghostctl export posts --output posts-audit.json
   diff previous-audit.json posts-audit.json
   ```

### Security Vulnerabilities

If you discover a security vulnerability:

1. **Do not create public issues**
2. **Contact us privately** at security@ghostctl.dev
3. **Provide detailed information**:
   - Steps to reproduce
   - Impact assessment
   - Proposed fix (if any)

## Compliance Considerations

### GDPR Compliance

When handling member data:

```bash
# Export specific member data for GDPR requests
ghostctl members export --filter "email:user@example.com" --output gdpr-export.json

# Delete member data (right to be forgotten)
ghostctl members delete member-id --force
```

### Data Retention

Implement data retention policies:

```bash
#!/bin/bash
# cleanup-old-exports.sh
find ~/ghost-backups -name "*.json" -mtime +90 -delete
find ~/.ghostctl_audit.log -mtime +365 -delete
```

### Audit Trails

Maintain audit trails for compliance:

```bash
# Comprehensive logging wrapper
#!/bin/bash
# ghostctl-logged.sh
{
    echo "AUDIT: $(date -Iseconds) User:$USER Host:$(hostname) Command:ghostctl $*"
    ghostctl "$@" 2>&1
    echo "AUDIT: $(date -Iseconds) Exit Code:$?"
} | tee -a /var/log/ghostctl-audit.log
```

## Security Checklist

### Development Environment

- [ ] API keys stored in environment variables
- [ ] Configuration files have restrictive permissions (600)
- [ ] No API keys in version control
- [ ] HTTPS URLs only
- [ ] Regular key rotation schedule

### Production Environment

- [ ] Secrets management system in use
- [ ] Principle of least privilege applied
- [ ] Monitoring and logging enabled
- [ ] Backup encryption implemented
- [ ] Incident response plan documented
- [ ] Regular security audits scheduled

### CI/CD Pipeline

- [ ] Secrets stored in CI/CD secret management
- [ ] No sensitive data in logs
- [ ] Secure artifact storage
- [ ] Access controls on pipelines
- [ ] Regular dependency updates

## Additional Resources

- [Ghost Admin API Security](https://ghost.org/docs/admin-api/#authentication)
- [OWASP API Security Top 10](https://owasp.org/www-project-api-security/)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)
- [12-Factor App Security](https://12factor.net/config)

## Contact

For security-related questions or to report vulnerabilities:

- 🔒 Security Email: security@ghostctl.dev
- 🔐 PGP Key: [Download](https://ghostctl.dev/security.asc)
- 🛡️ Security Advisories: [GitHub Security](https://github.com/yourusername/ghostctl/security)

---

*This security policy is reviewed quarterly and updated as needed.*