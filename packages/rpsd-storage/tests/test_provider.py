"""
Tests for StorageProvider base class.
"""

from rpsd_storage.provider import StorageProvider


class TestStorageProviderExtensionFromMime:
    """Test StorageProvider.extension_from_mime() staticmethod."""

    def test_common_mime_types(self):
        """Test common MIME type to extension mappings."""
        assert StorageProvider.extension_from_mime("application/json") == ".json"
        assert StorageProvider.extension_from_mime("text/plain") == ".txt"
        assert StorageProvider.extension_from_mime("text/html") == ".html"
        assert StorageProvider.extension_from_mime("application/pdf") == ".pdf"
        assert StorageProvider.extension_from_mime("image/png") == ".png"
        assert StorageProvider.extension_from_mime("image/jpeg") == ".jpg"

    def test_xml_mime_types(self):
        """Test XML-related MIME types use correct extension."""
        # application/xml should return .xml, not .xsl (override)
        assert StorageProvider.extension_from_mime("application/xml") == ".xml"
        assert StorageProvider.extension_from_mime("text/xml") == ".xml"

    def test_unknown_mime_type_fallback(self):
        """Test that unknown MIME types fall back to .xml."""
        assert StorageProvider.extension_from_mime("unknown/type") == ".xml"
        assert StorageProvider.extension_from_mime("application/x-custom") == ".xml"
        assert StorageProvider.extension_from_mime("") == ".xml"

    def test_additional_common_types(self):
        """Test additional common MIME types."""
        # Note: application/javascript not in standard mimetypes, falls back
        assert StorageProvider.extension_from_mime("text/javascript") == ".js"
        assert StorageProvider.extension_from_mime("text/css") == ".css"
        assert StorageProvider.extension_from_mime("application/zip") == ".zip"
        assert StorageProvider.extension_from_mime("text/csv") == ".csv"

    def test_image_types(self):
        """Test various image MIME types."""
        assert StorageProvider.extension_from_mime("image/gif") == ".gif"
        assert StorageProvider.extension_from_mime("image/svg+xml") == ".svg"
        assert StorageProvider.extension_from_mime("image/webp") == ".webp"

    def test_audio_video_types(self):
        """Test audio and video MIME types."""
        assert StorageProvider.extension_from_mime("audio/mpeg") in [".mp3", ".mpga"]
        assert StorageProvider.extension_from_mime("video/mp4") == ".mp4"
        # Note: audio/wav not in standard mimetypes, use audio/x-wav
        assert StorageProvider.extension_from_mime("audio/x-wav") == ".wav"

    def test_office_document_types(self):
        """Test office document MIME types."""
        assert (
            StorageProvider.extension_from_mime(
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            )
            == ".docx"
        )
        assert (
            StorageProvider.extension_from_mime(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            == ".xlsx"
        )

    def test_staticmethod_accessible_without_instance(self):
        """Test that staticmethod can be called without instance."""
        # Should work without instantiating a provider
        result = StorageProvider.extension_from_mime("application/json")
        assert result == ".json"
        assert isinstance(result, str)
