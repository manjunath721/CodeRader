"""
Canonical, user-facing error catalog (master spec §43).

Routes/services should raise CodeResilienceError (or a subclass) rather than
letting raw exceptions/stack traces reach the client. FastAPI exception
handlers (registered in app/main.py) translate these into clean JSON
responses: {"detail": <message>, "code": <code>}.
"""
from fastapi import status


class CodeResilienceError(Exception):
    code: str = "INTERNAL_ERROR"
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    message: str = "An unexpected error occurred."

    def __init__(self, message: str | None = None):
        super().__init__(message or self.message)
        if message:
            self.message = message


class RepositoryNotAccessibleError(CodeResilienceError):
    code = "REPO_NOT_ACCESSIBLE"
    status_code = status.HTTP_400_BAD_REQUEST
    message = "Repository not accessible."


class InvalidGitURLError(CodeResilienceError):
    code = "INVALID_GIT_URL"
    status_code = status.HTTP_400_BAD_REQUEST
    message = "Invalid Git URL."


class AnalysisFailedError(CodeResilienceError):
    code = "ANALYSIS_FAILED"
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    message = "Analysis failed."


class NoCommitsFoundError(CodeResilienceError):
    code = "NO_COMMITS_FOUND"
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    message = "No commits found."


class DeveloperDetectionFailedError(CodeResilienceError):
    code = "DEVELOPER_DETECTION_FAILED"
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    message = "Unable to detect developers."


class GitHubAuthRequiredError(CodeResilienceError):
    code = "GITHUB_AUTH_REQUIRED"
    status_code = status.HTTP_401_UNAUTHORIZED
    message = "GitHub authentication required."


class AIProviderUnavailableError(CodeResilienceError):
    code = "AI_PROVIDER_UNAVAILABLE"
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    message = "AI provider unavailable."


class DatabaseUnavailableError(CodeResilienceError):
    code = "DATABASE_UNAVAILABLE"
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    message = "Database unavailable."
