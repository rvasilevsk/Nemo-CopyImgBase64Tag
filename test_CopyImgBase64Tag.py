import os
from pathlib import Path

import pytest

from CopyImgBase64Tag import unexpand_user

data = [
    ("/home/nika/Desktop", "~/Desktop"),
    ("/home/liza/Desktop", "/home/liza/Desktop"),
    (Path("/home/nika/Desktop"), Path("~/Desktop")),
    (Path("/home/liza/Desktop"), Path("/home/liza/Desktop")),
    # (Path("/home/nika/Desktop"), Path("/home/nika/Desktop")),
]


@pytest.mark.parametrize("path, res", data)
def test_unexpand_user(path, res):
    os.environ["HOME"] = "/home/nika"
    assert unexpand_user(path) == res


data = [
    (Path("/home/nika/Desktop"), Path("/home/nika/Desktop")),
]


@pytest.mark.parametrize("path, res", data)
def test_unexpand_user_wrong(path, res):
    os.environ["HOME"] = "/home/nika"
    assert unexpand_user(path) != res
