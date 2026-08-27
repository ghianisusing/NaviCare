from django.urls import path

from .views import ConversationDetailView, ConversationListCreateView, ConversationMessagesView

app_name = "conversations"

urlpatterns = [
    path("", ConversationListCreateView.as_view(), name="list-create"),
    path("<int:pk>/", ConversationDetailView.as_view(), name="detail"),
    path("<int:pk>/messages/", ConversationMessagesView.as_view(), name="messages"),
]
