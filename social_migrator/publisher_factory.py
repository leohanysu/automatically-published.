from .publishers import MetaPublisher, TikTokPublisher, XPublisher, YouTubePublisher, PinterestPublisher


def get_publisher(platform: str):
    publishers = {
        "meta": MetaPublisher,
        "tiktok": TikTokPublisher,
        "x": XPublisher,
        "youtube": YouTubePublisher,
        "pinterest": PinterestPublisher,
    }
    try:
        return publishers[platform]()
    except KeyError:
        raise ValueError(f"不支持的平台: {platform}")
