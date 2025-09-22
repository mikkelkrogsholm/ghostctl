"""Ghost CMS API client.

This module provides a high-level client for interacting with Ghost CMS
Admin and Content APIs, including authentication, retry logic, error
handling, pagination, and rate limiting awareness.
"""

import os
import time
from typing import Dict, List, Any, Optional, Union, Iterator, Tuple
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from .config import Profile
from .utils.auth import AuthManager
from .utils.retry import RetryManager, CircuitBreaker
from .exceptions import (
    APIError,
    BadRequestError,
    UnauthorizedError,
    ForbiddenError,
    NotFoundError,
    ServerError,
    RateLimitError,
    AuthenticationError,
)


class GhostClient:
    """High-level client for Ghost CMS API operations."""

    def __init__(
        self,
        profile: Optional[Profile] = None,
        url: Optional[str] = None,
        admin_key: Optional[str] = None,
        content_key: Optional[str] = None,
        timeout: int = 30,
        retry_attempts: int = 3,
        debug: bool = False,
    ) -> None:
        """Initialize Ghost API client.

        Args:
            profile: Configuration profile
            url: Ghost CMS instance URL (if profile not provided)
            admin_key: Admin API key (if profile not provided)
            content_key: Content API key (if profile not provided)
            timeout: Request timeout in seconds
            retry_attempts: Number of retry attempts

        Raises:
            ValueError: If insufficient configuration is provided
        """
        # Check for environment variable overrides
        env_url = os.getenv("GHOST_API_URL")
        env_admin_key = os.getenv("GHOST_ADMIN_API_KEY")
        env_content_key = os.getenv("GHOST_CONTENT_API_KEY")

        # Configure from profile or direct parameters, with env var overrides
        if profile:
            self.url = str(env_url or profile.url).rstrip("/")
            self.admin_key = env_admin_key or profile.admin_key
            self.content_key = env_content_key or profile.content_key
            self.timeout = profile.timeout
            self.retry_attempts = profile.retry_attempts
            self.version = profile.version
        else:
            if not (env_url or url):
                raise ValueError("Either profile, url parameter, or GHOST_API_URL environment variable must be provided")

            self.url = str(env_url or url).rstrip("/")
            self.admin_key = env_admin_key or admin_key
            self.content_key = env_content_key or content_key
            self.timeout = timeout
            self.retry_attempts = retry_attempts
            self.version = "v5.0"

        self.debug = debug
        self._rate_limit_info = {}

        # Initialize authentication manager
        self.auth = AuthManager(
            admin_key=self.admin_key,
            content_key=self.content_key,
            ghost_url=self.url,
            timeout=self.timeout,
        )

        # Initialize retry manager
        self.retry_manager = RetryManager(
            max_retries=self.retry_attempts,
            base_delay=1.0,
            max_delay=30.0,
            backoff_factor=2.0,
            jitter=True,
        )

        # Initialize circuit breaker for admin API
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=60.0,
            expected_exception=requests.exceptions.RequestException,
        )

        # Initialize requests session with connection pooling
        self.session = requests.Session()
        self._configure_session()

    def _configure_session(self) -> None:
        """Configure the requests session with retry strategy."""
        # Configure retry strategy for the session
        retry_strategy = Retry(
            total=0,  # We handle retries ourselves
            connect=2,  # Connection retries
            read=2,  # Read retries
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504],
        )

        adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=10, pool_maxsize=20)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def _parse_rate_limit_headers(self, response: requests.Response) -> Dict[str, Any]:
        """Parse rate limit headers from response.

        Args:
            response: Response object

        Returns:
            Dictionary with rate limit information
        """
        return {
            "limit": response.headers.get("X-RateLimit-Limit"),
            "remaining": response.headers.get("X-RateLimit-Remaining"),
            "reset": response.headers.get("X-RateLimit-Reset"),
            "retry_after": response.headers.get("Retry-After"),
        }

    def _handle_response(self, response: requests.Response) -> Dict[str, Any]:
        """Handle API response and convert errors to appropriate exceptions.

        Args:
            response: Response object

        Returns:
            Parsed JSON response

        Raises:
            APIError: For various HTTP error conditions
        """
        # Parse rate limit headers
        rate_limit_info = self._parse_rate_limit_headers(response)

        # Store rate limit info for monitoring
        if not hasattr(self, '_rate_limit_info'):
            self._rate_limit_info = {}
        self._rate_limit_info.update(rate_limit_info)
        # Extract error details from response
        error_data = {}
        try:
            error_data = response.json()
        except Exception:
            pass

        # Handle specific status codes
        if response.status_code == 400:
            raise BadRequestError(
                "Bad request",
                status_code=response.status_code,
                response_data=error_data,
            )
        elif response.status_code == 401:
            raise UnauthorizedError(
                "Unauthorized - check your API keys",
                status_code=response.status_code,
                response_data=error_data,
            )
        elif response.status_code == 403:
            raise ForbiddenError(
                "Forbidden - insufficient permissions",
                status_code=response.status_code,
                response_data=error_data,
            )
        elif response.status_code == 404:
            raise NotFoundError(
                "Resource not found",
                status_code=response.status_code,
                response_data=error_data,
            )
        elif response.status_code == 422:
            error_messages = []
            if "errors" in error_data:
                error_messages = [err.get("message", "Validation error") for err in error_data["errors"]]

            raise BadRequestError(
                f"Validation error: {'; '.join(error_messages) if error_messages else 'Invalid data'}",
                status_code=response.status_code,
                response_data=error_data,
            )
        elif response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            remaining = response.headers.get("X-RateLimit-Remaining", "0")
            reset_time = response.headers.get("X-RateLimit-Reset")

            message = f"Rate limit exceeded. Remaining: {remaining}"
            if reset_time:
                message += f", resets at: {reset_time}"
            if retry_after:
                message += f", retry after: {retry_after} seconds"

            raise RateLimitError(
                message,
                status_code=response.status_code,
                response_data=error_data,
                retry_after=int(retry_after) if retry_after else None,
            )
        elif response.status_code >= 500:
            raise ServerError(
                f"Server error: {response.status_code}",
                status_code=response.status_code,
                response_data=error_data,
            )

        # Check for successful response
        response.raise_for_status()

        # Log rate limit warnings if getting close to limit
        remaining = rate_limit_info.get("remaining")
        if remaining and remaining.isdigit() and int(remaining) < 10:
            print(f"Warning: Only {remaining} API requests remaining")

        return response.json()

    def _make_request(
        self,
        method: str,
        endpoint: str,
        use_admin_api: bool = True,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Make an API request with retry logic and error handling.

        Args:
            method: HTTP method
            endpoint: API endpoint
            use_admin_api: Whether to use Admin API authentication
            **kwargs: Additional request parameters

        Returns:
            Parsed JSON response

        Raises:
            APIError: For various API error conditions
        """
        def make_request() -> Dict[str, Any]:
            # Use session for connection pooling
            if self.debug:
                print(f"[DEBUG] Making {method} request to {self.url}{endpoint}")
                if kwargs.get("params"):
                    print(f"[DEBUG] Params: {kwargs['params']}")

            response = self.session.request(
                method=method,
                url=f"{self.url}{endpoint}",
                timeout=self.timeout,
                **kwargs,
            )

            if self.debug:
                print(f"[DEBUG] Response status: {response.status_code}")
                print(f"[DEBUG] Rate limit headers: {self._parse_rate_limit_headers(response)}")

            return self._handle_response(response)

        def authenticated_request() -> Dict[str, Any]:
            if self.debug:
                print(f"[DEBUG] Making authenticated {method} request to {endpoint}")
                print(f"[DEBUG] Using admin API: {use_admin_api}")

            return self.auth.authenticated_request(
                method=method,
                endpoint=endpoint,
                use_admin_api=use_admin_api,
                session=self.session,
                debug=self.debug,
                **kwargs,
            )

        # Use circuit breaker for admin API requests
        if use_admin_api:
            return self.circuit_breaker.call(
                lambda: self.retry_manager.execute_with_retry(authenticated_request)
            )
        else:
            return self.retry_manager.execute_with_retry(authenticated_request)

    def get_all_pages(
        self,
        endpoint: str,
        resource_key: str,
        limit: int = 15,
        **kwargs: Any,
    ) -> Iterator[Dict[str, Any]]:
        """Get all pages of results from a paginated endpoint.

        Args:
            endpoint: API endpoint
            resource_key: Key in response containing the resources (e.g., 'posts', 'tags')
            limit: Items per page
            **kwargs: Additional request parameters

        Yields:
            Individual items from all pages
        """
        page = 1
        while True:
            params = kwargs.get("params", {})
            params.update({"limit": limit, "page": page})
            kwargs["params"] = params

            response = self._make_request("GET", endpoint, **kwargs)

            items = response.get(resource_key, [])
            if not items:
                break

            for item in items:
                yield item

            # Check if there are more pages
            meta = response.get("meta", {})
            pagination = meta.get("pagination", {})

            if not pagination.get("next"):
                break

            page += 1

            # Respect rate limits
            if hasattr(self, '_rate_limit_info'):
                remaining = self._rate_limit_info.get("remaining")
                if remaining and remaining.isdigit() and int(remaining) < 5:
                    print("Rate limit approaching, pausing...")
                    time.sleep(1)

    def get_all_items(
        self,
        endpoint: str,
        resource_key: str,
        limit: int = 15,
        show_progress: bool = False,
        progress_description: str = "Fetching items",
        **kwargs: Any,
    ) -> List[Dict[str, Any]]:
        """Get all items from a paginated endpoint with optional progress bar.

        Args:
            endpoint: API endpoint
            resource_key: Key in response containing the resources
            limit: Items per page
            show_progress: Whether to show progress bar
            progress_description: Description for progress bar
            **kwargs: Additional request parameters

        Returns:
            List of all items
        """
        items = []

        if show_progress:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                transient=True,
            ) as progress:
                # First, get total count if possible
                first_response = self._make_request("GET", endpoint, params={"limit": 1, "page": 1})
                meta = first_response.get("meta", {})
                pagination = meta.get("pagination", {})
                total = pagination.get("total", 0)

                task = progress.add_task(progress_description, total=total)

                for item in self.get_all_pages(endpoint, resource_key, limit, **kwargs):
                    items.append(item)
                    progress.update(task, advance=1)
        else:
            items = list(self.get_all_pages(endpoint, resource_key, limit, **kwargs))

        return items

    # Posts API methods
    def get_posts(
        self,
        limit: int = 15,
        page: int = 1,
        filter_query: Optional[str] = None,
        include: Optional[List[str]] = None,
        fields: Optional[List[str]] = None,
        formats: Optional[List[str]] = None,
        order: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get posts from Ghost CMS.

        Args:
            limit: Number of posts to retrieve
            page: Page number
            filter_query: Filter query string
            include: Related data to include
            fields: Fields to return
            formats: Content formats to include

        Returns:
            Posts response data
        """
        params = {"limit": limit, "page": page}

        if filter_query:
            params["filter"] = filter_query
        if include:
            params["include"] = ",".join(include)
        if fields:
            params["fields"] = ",".join(fields)
        if formats:
            params["formats"] = ",".join(formats)
        if order:
            params["order"] = order

        return self._make_request("GET", "/ghost/api/admin/posts/", params=params)

    def get_all_posts(
        self,
        filter_query: Optional[str] = None,
        include: Optional[List[str]] = None,
        show_progress: bool = False,
    ) -> List[Dict[str, Any]]:
        """Get all posts with pagination handling.

        Args:
            filter_query: Filter query string
            include: Related data to include
            show_progress: Whether to show progress bar

        Returns:
            List of all posts
        """
        params = {}
        if filter_query:
            params["filter"] = filter_query
        if include:
            params["include"] = ",".join(include)

        return self.get_all_items(
            "/ghost/api/admin/posts/",
            "posts",
            show_progress=show_progress,
            progress_description="Fetching posts",
            params=params,
        )

    def get_post(self, post_id: str, include: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get a specific post by ID.

        Args:
            post_id: Post ID
            include: Related data to include

        Returns:
            Post response data
        """
        params = {}
        if include:
            params["include"] = ",".join(include)

        return self._make_request("GET", f"/ghost/api/admin/posts/{post_id}/", params=params)

    def create_post(self, post_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new post.

        Args:
            post_data: Post data

        Returns:
            Created post response data
        """
        return self._make_request(
            "POST",
            "/ghost/api/admin/posts/",
            json={"posts": [post_data]},
        )

    def update_post(self, post_id: str, post_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing post.

        Args:
            post_id: Post ID
            post_data: Updated post data

        Returns:
            Updated post response data
        """
        return self._make_request(
            "PUT",
            f"/ghost/api/admin/posts/{post_id}/",
            json={"posts": [post_data]},
        )

    def delete_post(self, post_id: str) -> bool:
        """Delete a post.

        Args:
            post_id: Post ID

        Returns:
            True if deletion was successful
        """
        try:
            self._make_request("DELETE", f"/ghost/api/admin/posts/{post_id}/")
            return True
        except NotFoundError:
            return False

    # Tags API methods
    def get_all_tags(
        self,
        filter_query: Optional[str] = None,
        include: Optional[List[str]] = None,
        show_progress: bool = False,
    ) -> List[Dict[str, Any]]:
        """Get all tags with pagination handling.

        Args:
            filter_query: Filter query string
            include: Related data to include
            show_progress: Whether to show progress bar

        Returns:
            List of all tags
        """
        params = {}
        if filter_query:
            params["filter"] = filter_query
        if include:
            params["include"] = ",".join(include)

        return self.get_all_items(
            "/ghost/api/admin/tags/",
            "tags",
            show_progress=show_progress,
            progress_description="Fetching tags",
            params=params,
        )

    def get_tags(
        self,
        limit: int = 15,
        page: int = 1,
        filter_query: Optional[str] = None,
        include: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Get tags from Ghost CMS.

        Args:
            limit: Number of tags to retrieve
            page: Page number
            filter_query: Filter query string
            include: Related data to include

        Returns:
            Tags response data
        """
        params = {"limit": limit, "page": page}

        if filter_query:
            params["filter"] = filter_query
        if include:
            params["include"] = ",".join(include)

        return self._make_request("GET", "/ghost/api/admin/tags/", params=params)

    def get_tag(self, tag_id: str, include: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get a specific tag by ID.

        Args:
            tag_id: Tag ID
            include: Related data to include

        Returns:
            Tag response data
        """
        params = {}
        if include:
            params["include"] = ",".join(include)

        return self._make_request("GET", f"/ghost/api/admin/tags/{tag_id}/", params=params)

    def create_tag(self, tag_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new tag.

        Args:
            tag_data: Tag data

        Returns:
            Created tag response data
        """
        return self._make_request(
            "POST",
            "/ghost/api/admin/tags/",
            json={"tags": [tag_data]},
        )

    def update_tag(self, tag_id: str, tag_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing tag.

        Args:
            tag_id: Tag ID
            tag_data: Updated tag data

        Returns:
            Updated tag response data
        """
        return self._make_request(
            "PUT",
            f"/ghost/api/admin/tags/{tag_id}/",
            json={"tags": [tag_data]},
        )

    def delete_tag(self, tag_id: str) -> bool:
        """Delete a tag.

        Args:
            tag_id: Tag ID

        Returns:
            True if deletion was successful
        """
        try:
            self._make_request("DELETE", f"/ghost/api/admin/tags/{tag_id}/")
            return True
        except NotFoundError:
            return False

    # Site information methods
    def get_site_info(self) -> Dict[str, Any]:
        """Get site information.

        Returns:
            Site information data
        """
        return self._make_request("GET", "/ghost/api/admin/site/")

    def get_config(self) -> Dict[str, Any]:
        """Get site configuration.

        Returns:
            Site configuration data
        """
        return self._make_request("GET", "/ghost/api/admin/config/")

    # User methods
    def get_users(
        self,
        limit: int = 15,
        page: int = 1,
        include: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Get users from Ghost CMS.

        Args:
            limit: Number of users to retrieve
            page: Page number
            include: Related data to include

        Returns:
            Users response data
        """
        params = {"limit": limit, "page": page}

        if include:
            params["include"] = ",".join(include)

        return self._make_request("GET", "/ghost/api/admin/users/", params=params)

    def get_current_user(self) -> Dict[str, Any]:
        """Get current user information.

        Returns:
            Current user data
        """
        return self._make_request("GET", "/ghost/api/admin/users/me/")

    # Image upload methods
    def upload_image(self, image_path: str, purpose: str = "image") -> Dict[str, Any]:
        """Upload an image to Ghost CMS.

        Args:
            image_path: Path to image file
            purpose: Purpose of the image (image, profile_image, cover_image)

        Returns:
            Upload response data
        """
        with open(image_path, "rb") as f:
            files = {"file": f}
            data = {"purpose": purpose}

            return self._make_request(
                "POST",
                "/ghost/api/admin/images/upload/",
                files=files,
                data=data,
            )

    # Theme methods
    def get_themes(self) -> Dict[str, Any]:
        """Get installed themes.

        Returns:
            Themes response data
        """
        return self._make_request("GET", "/ghost/api/admin/themes/")

    def get_active_theme(self) -> Dict[str, Any]:
        """Get active theme information.

        Returns:
            Active theme data
        """
        return self._make_request("GET", "/ghost/api/admin/themes/?filter=active:true")

    def upload_theme(self, theme_path: str) -> Dict[str, Any]:
        """Upload a theme to Ghost CMS.

        Args:
            theme_path: Path to theme zip file

        Returns:
            Upload response data
        """
        with open(theme_path, "rb") as f:
            files = {"file": f}

            return self._make_request(
                "POST",
                "/ghost/api/admin/themes/upload/",
                files=files,
            )

    def activate_theme(self, theme_name: str) -> Dict[str, Any]:
        """Activate a theme.

        Args:
            theme_name: Name of theme to activate

        Returns:
            Activation response data
        """
        return self._make_request(
            "PUT",
            f"/ghost/api/admin/themes/{theme_name}/activate/",
        )

    # Bulk operations with progress tracking
    def bulk_update_posts(
        self,
        updates: List[Tuple[str, Dict[str, Any]]],
        show_progress: bool = True,
    ) -> List[Dict[str, Any]]:
        """Perform bulk updates on posts.

        Args:
            updates: List of (post_id, update_data) tuples
            show_progress: Whether to show progress bar

        Returns:
            List of updated posts
        """
        results = []

        if show_progress:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
            ) as progress:
                task = progress.add_task("Updating posts", total=len(updates))

                for post_id, update_data in updates:
                    try:
                        result = self.update_post(post_id, update_data)
                        results.append(result)
                    except Exception as e:
                        results.append({"error": str(e), "post_id": post_id})

                    progress.update(task, advance=1)

                    # Respect rate limits
                    if hasattr(self, '_rate_limit_info'):
                        remaining = self._rate_limit_info.get("remaining")
                        if remaining and remaining.isdigit() and int(remaining) < 5:
                            time.sleep(0.5)
        else:
            for post_id, update_data in updates:
                try:
                    result = self.update_post(post_id, update_data)
                    results.append(result)
                except Exception as e:
                    results.append({"error": str(e), "post_id": post_id})

        return results

    def bulk_delete_posts(
        self,
        post_ids: List[str],
        show_progress: bool = True,
    ) -> List[Dict[str, Any]]:
        """Perform bulk deletion of posts.

        Args:
            post_ids: List of post IDs to delete
            show_progress: Whether to show progress bar

        Returns:
            List of deletion results
        """
        results = []

        if show_progress:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
            ) as progress:
                task = progress.add_task("Deleting posts", total=len(post_ids))

                for post_id in post_ids:
                    try:
                        success = self.delete_post(post_id)
                        results.append({"post_id": post_id, "deleted": success})
                    except Exception as e:
                        results.append({"post_id": post_id, "error": str(e), "deleted": False})

                    progress.update(task, advance=1)

                    # Respect rate limits
                    if hasattr(self, '_rate_limit_info'):
                        remaining = self._rate_limit_info.get("remaining")
                        if remaining and remaining.isdigit() and int(remaining) < 5:
                            time.sleep(0.5)
        else:
            for post_id in post_ids:
                try:
                    success = self.delete_post(post_id)
                    results.append({"post_id": post_id, "deleted": success})
                except Exception as e:
                    results.append({"post_id": post_id, "error": str(e), "deleted": False})

        return results

    # Utility methods
    def test_connection(self) -> bool:
        """Test connection to Ghost CMS.

        Returns:
            True if connection is successful
        """
        try:
            self.get_site_info()
            return True
        except Exception:
            return False

    def get_rate_limit_info(self) -> Dict[str, Any]:
        """Get current rate limit information.

        Returns:
            Dictionary with rate limit information
        """
        return getattr(self, '_rate_limit_info', {})

    def get_stats(self) -> Dict[str, Any]:
        """Get client statistics.

        Returns:
            Dictionary with client statistics
        """
        return {
            "retry_stats": self.retry_manager.get_metrics(),
            "circuit_breaker_stats": self.circuit_breaker.get_state_info(),
            "rate_limit_info": self.get_rate_limit_info(),
        }