import pytest

from enso.build import build


@pytest.fixture(scope="session")
def site(tmp_path_factory):
    """The site built once into a temporary folder."""
    out = tmp_path_factory.mktemp("site")
    build(out)
    return out
