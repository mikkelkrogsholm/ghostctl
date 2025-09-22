<!-- Sync Impact Report
Version change: Template → 1.0.0 (initial ratification)
Modified principles: All new (8 principles created)
Added sections: Development Standards, CI/CD Requirements
Removed sections: Generic template sections
Templates requiring updates:
  ✅ plan-template.md - Constitution Check section to be aligned
  ✅ spec-template.md - Alignment verified
  ✅ tasks-template.md - Task categories aligned
Follow-up TODOs: RATIFICATION_DATE needs to be confirmed
-->

# Ghost Typer CLI Constitution

## Core Principles

### I. Reliability First
Every component MUST be predictable, idempotent, and fault-tolerant. All operations that
modify Ghost content MUST be idempotent - running the same command twice produces the same
result. Network failures, API rate limits, and partial failures MUST be handled gracefully
with clear recovery paths. No operation shall leave the system in an inconsistent state.

### II. Clear CLI User Experience
Every command MUST provide clear, actionable feedback. Progress indicators for long-running
operations are mandatory. Error messages MUST specify what failed, why, and how to fix it.
Command syntax follows Unix conventions: single-dash for short flags (-v), double-dash for
long flags (--verbose). Every command MUST have --help documentation with examples.

### III. Type Safety (Python 3.11+)
All Python code MUST use type hints comprehensively. No use of `Any` type without explicit
justification. Dataclasses or Pydantic models for all data structures. Type checking via
mypy MUST pass with strict mode enabled. Runtime type validation at all API boundaries.

### IV. Exhaustive API Testing
Every Ghost Admin API interaction MUST have corresponding tests. Mock all external API
calls in unit tests. Integration tests against real Ghost instance for critical paths.
Contract tests to verify API schema compatibility. Test coverage MUST include success
paths, error handling, rate limiting, and network failures.

### V. Secure Credential Management
Ghost Admin API keys MUST never appear in logs, error messages, or command history.
Support multiple secure storage methods: environment variables, keychain/secret service,
and encrypted config files. All credential storage MUST use platform-appropriate secure
storage (macOS Keychain, Windows Credential Store, Linux Secret Service). Clear
documentation on security best practices.

### VI. Zero Magic Policy
No hidden behaviors or implicit side effects. Every action MUST be explicit and
traceable. Configuration is explicit, not inferred. No auto-discovery of settings or
credentials unless explicitly requested via flags. All file modifications require
confirmation or explicit --force flag. Debug mode (--debug) shows exactly what the
tool is doing at each step.

### VII. Documentation by Example
Every command MUST have at least three documented examples covering: basic usage,
advanced usage with multiple flags, and error recovery scenarios. Examples MUST be
executable and tested. Man-page style documentation for all commands. Quick-start
guide with real-world scenarios. Troubleshooting guide with common issues and solutions.

### VIII. Fast CI/CD Pipeline
CI pipeline MUST complete in under 5 minutes for PR validation. Parallel test execution
by default. Dependency caching mandatory. Only affected tests run on file changes via
test selection. Build artifacts cached between runs. Deploy preview for documentation
changes. Automated performance regression detection.

## Development Standards

### Code Organization
- Domain-driven design with clear boundaries between layers
- Each module has single responsibility
- Dependency injection for testability
- Repository pattern for data access
- Service layer for business logic
- Clear separation between CLI interface and core logic

### Testing Requirements
- Test-first development for all new features
- Unit test coverage minimum 80%
- Integration tests for all user-facing commands
- Performance benchmarks for bulk operations
- Mutation testing to verify test quality

### Error Handling
- All exceptions MUST be caught and translated to user-friendly messages
- Structured logging with correlation IDs for debugging
- Retry logic with exponential backoff for transient failures
- Circuit breaker pattern for external service calls
- Graceful degradation when optional features fail

## CI/CD Requirements

### Pre-commit Checks
- Type checking with mypy --strict
- Code formatting with black and isort
- Linting with ruff
- Security scanning with bandit
- Commit message validation

### Pull Request Gates
- All tests pass
- Type checking passes
- Code coverage maintained or improved
- No security vulnerabilities
- Documentation updated for new features
- Performance benchmarks within acceptable range

### Release Process
- Semantic versioning strictly followed
- Changelog automatically generated from commits
- GitHub releases with binaries for all platforms
- PyPI package publication
- Docker images for containerized deployment
- Homebrew formula update for macOS

## Governance

### Amendment Process
All changes to this constitution require:
1. Documented rationale in pull request
2. Impact analysis on existing codebase
3. Migration plan for breaking changes
4. Team consensus or maintainer approval
5. Version bump following semantic versioning

### Versioning Policy
- MAJOR: Removal or redefinition of core principles
- MINOR: Addition of new principles or sections
- PATCH: Clarifications and non-semantic improvements

### Compliance Review
- Every pull request MUST reference relevant principles
- Violations require explicit justification in PR description
- Quarterly review of principle adherence
- Refactoring sprints when technical debt violates principles

**Version**: 1.0.0 | **Ratified**: TODO(RATIFICATION_DATE): Initial project setup date unknown | **Last Amended**: 2025-09-22