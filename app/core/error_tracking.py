"""Optional error tracking in Sentry (or a Sentry-compatible service: GlitchTip, ...).

Off while SENTRY_DSN is empty: sentry_sdk is not even imported. With a DSN it needs
requirements/sentry.txt (in Docker: EXTRA_REQUIREMENTS=sentry). Unhandled errors of
the API and of Celery tasks and ERROR log lines become events; nothing personal is
sent: no request bodies (passwords, form submissions), cookies, auth headers, user IP
or local variables, and INFO lines (form submissions with FORMS_DELIVERY=log) are not
kept as breadcrumbs.

The web process, the worker and beat all start through create_app(), so one call
covers them.
"""

import logging

from app.config import config


def setup_error_tracking() -> None:
    if not config.SENTRY_DSN:
        return
    try:
        import sentry_sdk
        from sentry_sdk.integrations.logging import LoggingIntegration
    except ImportError as exc:
        raise RuntimeError(
            "SENTRY_DSN requires sentry-sdk: pip install -r requirements/sentry.txt "
            "(Docker: EXTRA_REQUIREMENTS=sentry)"
        ) from exc

    sentry_sdk.init(
        dsn=config.SENTRY_DSN,
        environment=config.SENTRY_ENVIRONMENT,
        release=f"osnova-backend@{config.APP_VERSION}",
        # No user data by default (send_default_pii and data_collection left unset turn
        # on the SDK's own scrubber); bodies and frame variables are left out on top
        max_request_body_size="never",
        include_local_variables=False,
        traces_sample_rate=config.SENTRY_TRACES_SAMPLE_RATE,
        integrations=[LoggingIntegration(level=logging.WARNING, event_level=logging.ERROR)],
    )
