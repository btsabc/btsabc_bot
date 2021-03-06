import time
import importlib
import logging
from grapheneapi.graphenewsprotocol import GrapheneWebsocketProtocol
from grapheneexchange import GrapheneExchange
log = logging.getLogger(__name__)

config = None
bots = {}
dex = None


class BotProtocol(GrapheneWebsocketProtocol):
    """ Bot Protocol to interface with websocket notifications and
        forward notices to the bots
    """

    def onAccountUpdate(self, data):
        """ If the account updates, reload every market
        """
        log.debug("onAccountUpdate")
        for name in bots:
            bots[name].loadMarket(notify=True)
            bots[name].store()

    def onMarketUpdate(self, data):
        """ If a Market updates upgrades, reload every market
        """
        log.debug("onMarketUpdate")
        for name in bots:
            bots[name].loadMarket(notify=True)
            bots[name].store()

    def onAssetUpdate(self, data):
        """ This method is called only once after the websocket
            connection has successfully registered with the blockchain
            database
        """
        log.debug("onAssetUpdate")
        for name in bots:
            bots[name].loadMarket(notify=True)
            bots[name].asset_tick()
            bots[name].store()

    def onBlock(self, data) :
        """ Every block let the bots know via ``tick()``
        """
        log.debug("onBlock")
        for name in bots:
            bots[name].loadMarket(notify=True)
            bots[name].tick()
            bots[name].store()

    def onRegisterDatabase(self):
        """ This method is called only once after the websocket
            connection has successfully registered with the blockchain
            database
        """
        log.debug("onRegisterDatabase")
        for name in bots:
            bots[name].loadMarket(notify=True)
            bots[name].tick()
            bots[name].store()


def init(conf, **kwargs):
    """ Initialize the Bot Infrastructure and setup connection to the
        network
    """
    global dex, bots, config

    config = BotProtocol

    # Take the configuration variables and put them in the current
    # instance of BotProtocol. This step is required to let
    # GrapheneExchange know most of our variables as well!
    # We will also be able to hook into websocket messages from
    # within the configuration file!
    [setattr(config, key, conf[key]) for key in conf.keys()]

    if not hasattr(config, "prefix") or not config.prefix:
        log.debug("Setting default network (BTS)")
        config.prefix = "BTS"

    # Construct watch_markets attribute from all bots:
    watch_markets = set()
    for name in config.bots:
        watch_markets = watch_markets.union(config.bots[name].get("markets", []))
    setattr(config, "watch_markets", watch_markets)

    # Construct watch_assets attribute from all bots:
    watch_assets = set()
    for name in config.bots:
        watch_assets = watch_assets.union(config.bots[name].get("assets", []))
    setattr(config, "watch_assets", watch_assets)

    # Connect to the DEX
    dex    = GrapheneExchange(config,
                              safe_mode=config.safe_mode,
                              prefix=config.prefix)

    # Initialize all bots
    for index, name in enumerate(config.bots, 1):
        log.debug("Initializing bot %s" % name)
        if "module" not in config.bots[name]:
            raise ValueError("No 'module' defined for bot %s" % name)
        klass = getattr(
            importlib.import_module(config.bots[name]["module"]),
            config.bots[name]["bot"]
        )
        bots[name] = klass(config=config, name=name,
                           dex=dex, index=index)
        # Maybe the strategy/bot has some additional customized
        # initialized besides the basestrategy's __init__()
        log.debug("Calling %s.init()" % name)
        bots[name].loadMarket(notify=False)
        bots[name].init()
        bots[name].store()


def cancel_all():
    """ Cancel all orders of all markets that are served by the bots
    """
    for name in bots:
        log.info("Cancel-all %s" % name)
        bots[name].loadMarket(notify=False)
        bots[name].cancel_this_markets()
        bots[name].store()


def once():
    """ Execute the core unit of the bot
    """
    for name in bots:
        log.info("Executing bot %s" % name)
        bots[name].loadMarket(notify=True)
        bots[name].place()
        bots[name].store()


def orderplaced(orderid):
    """ Execute the core unit of the bot
    """
    for name in bots:
        log.info("Executing bot %s" % name)
        bots[name].orderPlaced(orderid)


def run():
    """ This call will run the bot in **continous mode** and make it
        receive notification from the network
    """
    dex.run()
