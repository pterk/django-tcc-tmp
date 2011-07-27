from celery.task import task


@task
def send_notifications(comment_id):
    pass


@task
def spam_check(comment_id):
    pass


@task
def prime_cache(comment_id):
    pass
