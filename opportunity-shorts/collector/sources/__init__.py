from .ashby import AshbySource
from .greenhouse import GreenhouseSource
from .lever import LeverSource
from .remote_apis import HimalayasSource, RemotiveSource
from .rss import RssSource
from .public_portals import AicteSource, UnstopSource
from .official_pages import OfficialPageSource

ATS_SOURCES = {"greenhouse": GreenhouseSource(), "lever": LeverSource(), "ashby": AshbySource()}
OTHER_SOURCES = {"himalayas": HimalayasSource(), "remotive": RemotiveSource(), "rss": RssSource(),
                 'unstop': UnstopSource(), 'aicte': AicteSource(), 'official_pages': OfficialPageSource()}
