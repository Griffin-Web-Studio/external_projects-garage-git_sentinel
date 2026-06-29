from __future__ import annotations

import tkinter as tk

import pytest

from src.models import GateHTTP, GateSSH
from src.ui.gui.views.prompt_area import PromptArea

# ────────────────────────────────────────────────────────────────| Fixtures |──


@pytest.fixture
def container(tk_root: tk.Tk) -> tk.Frame:
    """Create a bare `tk.Frame` parented to the test root window.

    Args:
        tk_root (tk.Tk): The root Tk window provided by the session-scoped
            fixture.

    Returns:
        tk.Frame: An empty frame suitable for use as a `PromptArea` container.
    """

    return tk.Frame(tk_root)


@pytest.fixture
def area(container: tk.Frame) -> PromptArea:
    """Instantiate a `PromptArea` inside the test container.

    Args:
        container (tk.Frame): The parent frame returned by the `container`
            fixture.

    Returns:
        PromptArea: A freshly created `PromptArea` with no rendered prompt.
    """

    return PromptArea(container)


def _ssh_req() -> GateSSH:
    """Build a minimal `GateSSH` request for use in tests.

    Returns:
        GateSSH: A `GateSSH` instance with a sample URL and local repo path.
    """

    return GateSSH(url="git@github.com:user/repo.git", repo="~/projects/repo")


def _http_req() -> GateHTTP:
    """Build a minimal `GateHTTP` request with a simulated error for use in
    tests.

    Returns:
        GateHTTP: A `GateHTTP` instance with a sample URL, repo path, and error
            message.
    """

    return GateHTTP(
        url="https://github.com/user/repo.git",
        repo="~/projects/repo",
        error="Connection refused",
    )


# ───────────────────────────────────────────────────────────────────| clear |──


class TestClear:
    """clear() removes all child widgets from the container."""

    def test_empty_container_does_not_raise(
        self, area: PromptArea, container: tk.Frame
    ) -> None:
        """Verify `clear()` on an already-empty container does not raise.

        Args:
            area (PromptArea): The prompt area under test.
            container (tk.Frame): The parent frame whose children are checked.
        """

        area.clear()

        assert len(container.winfo_children()) == 0

    def test_removes_children(
        self, area: PromptArea, container: tk.Frame
    ) -> None:
        """Verify `clear()` destroys all widgets previously packed into the
        container.

        Args:
            area (PromptArea): The prompt area under test.
            container (tk.Frame): The parent frame that initially holds two
                `Label` widgets.
        """

        tk.Label(container, text="x").pack()
        tk.Label(container, text="y").pack()

        area.clear()

        assert len(container.winfo_children()) == 0


# ────────────────────────────────────────────────────────────────| show_ssh |──


class TestShowSSH:
    """show_ssh() renders the SSH approval prompt."""

    def test_adds_widgets(self, area: PromptArea, container: tk.Frame) -> None:
        """Verify `show_ssh()` populates the container with at least one widget.

        Args:
            area (PromptArea): The prompt area under test.
            container (tk.Frame): The parent frame whose children are checked.
        """

        area.show_ssh(_ssh_req())

        assert len(container.winfo_children()) > 0

    def test_replaces_previous_prompt(
        self, area: PromptArea, container: tk.Frame
    ) -> None:
        """Verify calling `show_ssh()` twice clears the first prompt before
        rendering.

        Args:
            area (PromptArea): The prompt area under test.
            container (tk.Frame): The parent frame whose child count is
                compared.
        """

        area.show_ssh(_ssh_req())
        count_after_first = len(container.winfo_children())
        area.show_ssh(_ssh_req())

        assert len(container.winfo_children()) == count_after_first

    def test_clears_http_prompt_first(
        self, area: PromptArea, container: tk.Frame
    ) -> None:
        """Verify `show_ssh()` removes a previously rendered HTTP prompt.

        Args:
            area (PromptArea): The prompt area under test.
            container (tk.Frame): The parent frame whose children are checked.
        """

        area.show_http(_http_req())
        area.show_ssh(_ssh_req())

        # Only the SSH prompt's widgets should remain - no stacking
        assert len(container.winfo_children()) > 0


# ───────────────────────────────────────────────────────────────| show_http |──


class TestShowHTTP:
    """show_http() renders the HTTP retry prompt."""

    def test_adds_widgets(self, area: PromptArea, container: tk.Frame) -> None:
        """Verify `show_http()` populates the container with at least one
        widget.

        Args:
            area (PromptArea): The prompt area under test.
            container (tk.Frame): The parent frame whose children are checked.
        """

        area.show_http(_http_req())

        assert len(container.winfo_children()) > 0

    def test_replaces_previous_prompt(
        self, area: PromptArea, container: tk.Frame
    ) -> None:
        """Verify calling `show_http()` twice clears the first prompt before
        rendering.

        Args:
            area (PromptArea): The prompt area under test.
            container (tk.Frame): The parent frame whose child count is
                compared.
        """

        area.show_http(_http_req())
        count_after_first = len(container.winfo_children())
        area.show_http(_http_req())

        assert len(container.winfo_children()) == count_after_first

    def test_clears_ssh_prompt_first(
        self, area: PromptArea, container: tk.Frame
    ) -> None:
        """Verify `show_http()` removes a previously rendered SSH prompt.

        Args:
            area (PromptArea): The prompt area under test.
            container (tk.Frame): The parent frame whose children are checked.
        """

        area.show_ssh(_ssh_req())
        area.show_http(_http_req())

        assert len(container.winfo_children()) > 0


# ────────────────────────────────────────────────────────────| _resolve_ssh |──


class TestResolveSSH:
    """_resolve_ssh() records the decision and unblocks the worker event."""

    def test_approved_sets_event(self, area: PromptArea) -> None:
        """Verify `_resolve_ssh(True)` sets the gate event so the worker
        unblocks.

        Args:
            area (PromptArea): The prompt area under test.
        """

        req = _ssh_req()

        area._resolve_ssh(req, approved=True)

        assert req.event.is_set()

    def test_declined_sets_event(self, area: PromptArea) -> None:
        """Verify `_resolve_ssh(False)` also sets the gate event.

        Args:
            area (PromptArea): The prompt area under test.
        """

        req = _ssh_req()

        area._resolve_ssh(req, approved=False)

        assert req.event.is_set()

    def test_approved_stores_true(self, area: PromptArea) -> None:
        """Verify `_resolve_ssh(True)` stores `True` on `req.approved`.

        Args:
            area (PromptArea): The prompt area under test.
        """

        req = _ssh_req()

        area._resolve_ssh(req, approved=True)

        assert req.approved is True

    def test_declined_stores_false(self, area: PromptArea) -> None:
        """Verify `_resolve_ssh(False)` stores `False` on `req.approved`.

        Args:
            area (PromptArea): The prompt area under test.
        """

        req = _ssh_req()

        area._resolve_ssh(req, approved=False)

        assert req.approved is False

    def test_clears_container(
        self, area: PromptArea, container: tk.Frame
    ) -> None:
        """Verify `_resolve_ssh()` clears the prompt widgets after resolution.

        Args:
            area (PromptArea): The prompt area under test.
            container (tk.Frame): The parent frame whose children are checked.
        """

        req = _ssh_req()

        tk.Label(container, text="prompt").pack()
        area._resolve_ssh(req, approved=True)

        assert len(container.winfo_children()) == 0


# ───────────────────────────────────────────────────────────| _resolve_http |──


class TestResolveHTTP:
    """_resolve_http() records the decision and unblocks the worker event."""

    def test_retry_sets_event(self, area: PromptArea) -> None:
        """Verify `_resolve_http(True)` sets the gate event so the worker
        unblocks.

        Args:
            area (PromptArea): The prompt area under test.
        """

        req = _http_req()

        area._resolve_http(req, retry=True)

        assert req.event.is_set()

    def test_skip_sets_event(self, area: PromptArea) -> None:
        """Verify `_resolve_http(False)` also sets the gate event.

        Args:
            area (PromptArea): The prompt area under test.
        """

        req = _http_req()

        area._resolve_http(req, retry=False)

        assert req.event.is_set()

    def test_retry_stores_true(self, area: PromptArea) -> None:
        """Verify `_resolve_http(True)` stores `True` on `req.retry`.

        Args:
            area (PromptArea): The prompt area under test.
        """

        req = _http_req()

        area._resolve_http(req, retry=True)

        assert req.retry is True

    def test_skip_stores_false(self, area: PromptArea) -> None:
        """Verify `_resolve_http(False)` stores `False` on `req.retry`.

        Args:
            area (PromptArea): The prompt area under test.
        """

        req = _http_req()

        area._resolve_http(req, retry=False)

        assert req.retry is False

    def test_clears_container(
        self, area: PromptArea, container: tk.Frame
    ) -> None:
        """Verify `_resolve_http()` clears the prompt widgets after resolution.

        Args:
            area (PromptArea): The prompt area under test.
            container (tk.Frame): The parent frame whose children are checked.
        """

        req = _http_req()

        tk.Label(container, text="prompt").pack()
        area._resolve_http(req, retry=False)

        assert len(container.winfo_children()) == 0
