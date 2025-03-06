from celery import Celery

def create_celery():
    celery = Celery(
        __name__,
        broker="redis://localhost:6379/0",
        backend="redis://localhost:6379/0"
    )
    celery.conf.update(task_routes={"*": {"queue": "default"}})
    return celery