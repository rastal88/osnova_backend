"""Forms of this project, served at /api/v1/forms/<name>.

Add a Form here and its texts to the "forms" section of app/core/locales/*.json
(see app/core/forms/schema.py for the keys). The frontend renders the form
from GET /forms/<name>; POST /forms/<name> validates and delivers it.
"""

from app.core.forms import Form, FormField

FORMS: tuple[Form, ...] = (
    Form(
        name="contact",
        fields=(
            FormField("name", required=True, min_length=2, max_length=100),
            FormField("email", type="email", required=True),
            FormField("phone", type="tel"),
            FormField("topic", type="select", options=("question", "order", "other")),
            FormField("message", type="textarea", required=True, min_length=10),
            FormField("consent", type="consent"),
        ),
    ),
)
