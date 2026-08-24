"""Registry of social providers (Postiz equivalent).

Real providers are listed in _REAL_PROVIDERS below; everything else falls
back to GenericSocialProvider so existing DB rows / frontend platform lists
keep working. MeWe, Skool, and Moltbook are deliberately left on the generic
fallback — none of the three have a documented public API (Postiz's own
support for them leans on private/cookie-based endpoints or a browser
extension), and fabricating undocumented endpoints isn't something to ship.
"""

from .base import NeedsReconnect, SocialPostError, SocialProvider, generate_pkce_pair
from .generic import GenericSocialProvider

from .bluesky import BlueskyProvider
from .dev_to import DevToProvider
from .discord import DiscordProvider
from .dribbble import DribbbleProvider
from .facebook import FacebookProvider
from .farcaster import FarcasterProvider
from .gmb import GMBProvider
from .hashnode import HashnodeProvider
from .instagram import InstagramProvider
from .kick import KickProvider
from .lemmy import LemmyProvider
from .linkedin import LinkedInProvider
from .listmonk import ListmonkProvider
from .mastodon import MastodonProvider
from .medium import MediumProvider
from .nostr import NostrProvider
from .pinterest import PinterestProvider
from .reddit import RedditProvider
from .slack import SlackProvider
from .telegram import TelegramProvider
from .threads import ThreadsProvider
from .tiktok import TikTokProvider
from .tumblr import TumblrProvider
from .twitch import TwitchProvider
from .vk import VKProvider
from .whop import WhopProvider
from .wordpress import WordPressProvider
from .x import XProvider
from .youtube import YouTubeProvider

# All 32 Postiz platform slugs, unchanged from the original stub so existing
# social_posts rows / frontend selectors keep working.
PROVIDERS_MAP: dict[str, str] = {
    "x": "X (Twitter)",
    "linkedin": "LinkedIn",
    "instagram": "Instagram",
    "facebook": "Facebook",
    "threads": "Threads",
    "youtube": "YouTube",
    "tiktok": "TikTok",
    "reddit": "Reddit",
    "pinterest": "Pinterest",
    "mastodon": "Mastodon",
    "bluesky": "Bluesky",
    "discord": "Discord",
    "slack": "Slack",
    "telegram": "Telegram",
    "dev_to": "Dev.to",
    "dribbble": "Dribbble",
    "farcaster": "Farcaster",
    "gmb": "Google Business Profile",
    "hashnode": "Hashnode",
    "kick": "Kick",
    "lemmy": "Lemmy",
    "listmonk": "Listmonk",
    "medium": "Medium",
    "mewe": "MeWe",
    "moltbook": "Moltbook",
    "nostr": "Nostr",
    "skool": "Skool",
    "tumblr": "Tumblr",
    "twitch": "Twitch",
    "vk": "VK",
    "whop": "Whop",
    "wordpress": "WordPress",
}

# Real implementations. Everything not listed here uses GenericSocialProvider.
_REAL_PROVIDERS: dict[str, SocialProvider] = {
    "x": XProvider(),
    "linkedin": LinkedInProvider(),
    "instagram": InstagramProvider(),
    "facebook": FacebookProvider(),
    "threads": ThreadsProvider(),
    "youtube": YouTubeProvider(),
    "tiktok": TikTokProvider(),
    "reddit": RedditProvider(),
    "pinterest": PinterestProvider(),
    "mastodon": MastodonProvider(),
    "bluesky": BlueskyProvider(),
    "discord": DiscordProvider(),
    "slack": SlackProvider(),
    "telegram": TelegramProvider(),
    "dev_to": DevToProvider(),
    "dribbble": DribbbleProvider(),
    "farcaster": FarcasterProvider(),
    "gmb": GMBProvider(),
    "hashnode": HashnodeProvider(),
    "kick": KickProvider(),
    "lemmy": LemmyProvider(),
    "listmonk": ListmonkProvider(),
    "medium": MediumProvider(),
    "nostr": NostrProvider(),
    "tumblr": TumblrProvider(),
    "twitch": TwitchProvider(),
    "vk": VKProvider(),
    "whop": WhopProvider(),
    "wordpress": WordPressProvider(),
}

PROVIDERS: dict[str, SocialProvider] = {
    slug: _REAL_PROVIDERS.get(slug) or GenericSocialProvider(slug, name)
    for slug, name in PROVIDERS_MAP.items()
}


def get_provider(slug: str) -> SocialProvider:
    if slug in PROVIDERS:
        return PROVIDERS[slug]
    return GenericSocialProvider(slug, slug.capitalize())


def is_real_provider(slug: str) -> bool:
    return slug in _REAL_PROVIDERS
