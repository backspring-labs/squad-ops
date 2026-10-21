"""ReviewRequestPort: opening a review request on the product's forge (SIP-0112 FR-06; E.4.3).

The product's own contribution process, reached for a ``review_request`` Project once its owner
contributes a run's verified change. The branch is already pushed through the managed clone
(``SourceRepositoryPort.push_capture``). This port only asks the forge to review it.
"""

from abc import ABC, abstractmethod


class ReviewRequestFailed(RuntimeError):
    """The forge refused or couldn't be reached, with the reason. Nothing was opened."""


class ReviewRequestPort(ABC):
    @abstractmethod
    async def open_review_request(
        self, *, repo_uri: str, head: str, base: str, title: str, body: str, token: str
    ) -> str:
        """Open a review request of branch ``head`` against ``base`` and return its URL. An
        open one for the same head is returned rather than duplicated, so a retry opens one.

        Raises:
            ReviewRequestFailed: The repository isn't on this forge, the token is refused, or
                the forge answered with an error.
        """
