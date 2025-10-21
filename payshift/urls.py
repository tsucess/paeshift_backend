"""
URL configuration for payshift project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),

    # API Documentation
    # TODO: Add drf_spectacular documentation endpoints when package is installed
    # path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    # path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    # path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

    # App URLs
    path('accountsapp/', include('accounts.urls')),
    path('core/', include('core.urls')),
    path('disputes/', include('disputes.urls')),
    path('adminaccess/', include('adminaccess.urls')),
    # path('chat/', include('chatapp.urls')),
    path('jobs/', include('jobs.urls')),
    path('payment/', include('payment.urls')),
    path('notifications/', include('notifications.urls')),
    path('rating/', include('rating.urls')),
    path('gamification/', include('gamification.urls')),
    path('userlocation/', include('userlocation.urls')),
    path('jobchat/', include('jobchat.urls')),
    path('godmode/', include('godmode.urls')),
]

# Serve media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

    # Django Debug Toolbar (Phase 2.2d) - Disabled due to auto-reload issues
    # urlpatterns += [
    #     path('__debug__/', include('debug_toolbar.urls')),
    # ]
