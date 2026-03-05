
from django.contrib import admin
from django.urls import path
from django.views.decorators.csrf import csrf_exempt
from strawberry.django.views import AsyncGraphQLView
from .schema import schema, get_context

AsyncGraphQLView.as_view(
    schema=schema,
    graphiql=True,
)
urlpatterns = [
    path('admin/', admin.site.urls),
    path(
        'graphql/',
        csrf_exempt(
            AsyncGraphQLView.as_view(schema=schema, graphiql=True,  )
        )
    ),
]