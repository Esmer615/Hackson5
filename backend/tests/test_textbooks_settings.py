from django.conf import settings

UPLOAD_LIMIT_BYTES = 50 * 1024 * 1024


def test_textbooks_app_is_installed():
    assert "apps.textbooks" in settings.INSTALLED_APPS


def test_media_and_deepseek_settings_are_configured():
    assert settings.MEDIA_URL == "/media/"
    assert settings.MEDIA_ROOT.name == "media"
    assert settings.MEDIA_ROOT.parent == settings.BASE_DIR
    assert isinstance(settings.DEEPSEEK_API_KEY, str)
    assert settings.DEEPSEEK_BASE_URL == "https://api.deepseek.com"
    assert settings.DEEPSEEK_MODEL == "deepseek-chat"
    assert settings.DEMO_MAX_PAGES == 12
    assert settings.QUALITY_MAX_PAGES == 80
    assert settings.DATA_UPLOAD_MAX_MEMORY_SIZE == UPLOAD_LIMIT_BYTES
    assert settings.FILE_UPLOAD_MAX_MEMORY_SIZE == UPLOAD_LIMIT_BYTES
