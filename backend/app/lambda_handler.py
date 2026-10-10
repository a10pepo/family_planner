import os

os.environ.setdefault("STORAGE_BACKEND", "dynamodb")


def make_handler():
    from mangum import Mangum

    from app.api import create_app

    return Mangum(create_app(), lifespan="off")


handler = make_handler()
