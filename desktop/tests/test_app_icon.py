"""
Coverage for create_app_icon()'s multi-size support, added so a build-time
.ico export can embed one crisp pixmap per size instead of one bitmap
scaled up by Windows. The artwork itself is drawn once in a 64x64
coordinate space and scaled via QPainter.scale() -- these tests check the
sizes actually available in the resulting QIcon, not the artwork.
"""
from background_services.notifications.notification_service import create_app_icon


def test_default_call_keeps_the_single_64px_size(qapp):
    icon = create_app_icon()
    sizes = icon.availableSizes()
    assert len(sizes) == 1
    assert (sizes[0].width(), sizes[0].height()) == (64, 64)


def test_explicit_sizes_produce_one_pixmap_each(qapp):
    icon = create_app_icon(sizes=[16, 32, 48, 256])
    available = {(s.width(), s.height()) for s in icon.availableSizes()}
    assert available == {(16, 16), (32, 32), (48, 48), (256, 256)}
    for size in (16, 32, 48, 256):
        pixmap = icon.pixmap(size, size)
        assert not pixmap.isNull()
