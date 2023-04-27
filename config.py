#!/usr/bin/env python
# -*- coding:utf-8 -*-
__author__ = 'Marco'

# load private info
try:
    from rpc_info import TESTNET_RPC_URL, MAINNET_RPC_URL
except ImportError:
    TESTNET_RPC_URL= ["https://rpc.testnet.near.org", ]
    MAINNET_RPC_URL= ["https://rpc.mainnet.near.org", ]

try:
    from redis_info import REDIS_HOST, REDIS_PORT
except ImportError:
    REDIS_HOST = "127.0.0.1"
    REDIS_PORT = "6379"

try:
    from indexer_info import INDEXER_DSN, INDEXER_UID, INDEXER_PWD, INDEXER_HOST, INDEXER_PORT
except ImportError:
    INDEXER_DSN = "mainnet_explorer"
    INDEXER_UID = "public_readonly"
    INDEXER_PWD = "nearprotocol"
    INDEXER_HOST = "104.199.89.51"
    INDEXER_PORT = "5432"

try:
    from db_info import DB_DSN, DB_UID, DB_PWD, DB_HOST, DB_PORT
except ImportError:
    DB_DSN = "ref"
    DB_UID = "root"
    DB_PWD = "root"
    DB_HOST = "127.0.0.1"
    DB_PORT = "3306"


try:
    from db_info import NEAR_LAKE_DB_DSN, NEAR_LAKE_DB_UID, NEAR_LAKE_DB_PWD, NEAR_LAKE_DB_HOST, NEAR_LAKE_DB_PORT, NEAR_LAKE_DCL_DB_DSN
except ImportError:
    NEAR_LAKE_DB_DSN = "ref"
    NEAR_LAKE_DB_UID = "root"
    NEAR_LAKE_DB_PWD = "root"
    NEAR_LAKE_DB_HOST = "127.0.0.1"
    NEAR_LAKE_DB_PORT = "3306"
    NEAR_LAKE_DCL_DB_DSN = "ref_dcl_mainnet"

"""

"""

class Cfg:
    NETWORK_ID = "MAINNET"
    REFSUBGRAPH_URL = "https://api.thegraph.com/subgraphs/name/coolsnake/refsubgraph"
    REDIS = {
        "REDIS_HOST": REDIS_HOST,
        "REDIS_PORT": REDIS_PORT,
    }
    NETWORK = {
        "DEVNET": {
            "NEAR_RPC_URL": TESTNET_RPC_URL,
            "FARMING_CONTRACT": "farm110.ref-dev.testnet",
            "REF_CONTRACT": "exchange.ref-dev.testnet",
            "XREF_CONTRACT": "xref.ref-dev.testnet",
            "BOOSTFARM_CONTRACT": "boostfarm.ref-dev.testnet",
            "ORDERLY_CONTRACT": "asset-manager.orderly.testnet",
            "REDIS_KEY": "FARMS_TESTNET_DEV",
            "REDIS_POOL_KEY": "POOLS_TESTNET_DEV",
            "REDIS_POOL_BY_TOKEN_KEY": "POOLS_BY_TOKEN_TESTNET_DEV",
            "REDIS_TOP_POOL_KEY": "TOP_POOLS_TESTNET_DEV",
            "REDIS_TOKEN_PRICE_KEY": "TOKEN_PRICE_TESTNET_DEV",
            "REDIS_HISTORY_TOKEN_PRICE_KEY": "HISTORY_TOKEN_PRICE_TESTNET_DEV",
            "REDIS_TOKEN_METADATA_KEY": "TOKEN_METADATA_TESTNET_DEV",
            "REDIS_WHITELIST_KEY": "WHITELIST_TESTNET_DEV",
            "INDEXER_DSN": "testnet_explorer",
            "INDEXER_UID": "public_readonly",
            "INDEXER_PWD": "nearprotocol",
            "INDEXER_HOST": "35.184.214.98",
            "INDEXER_PORT": "5432",
            "DB_DSN": DB_DSN,
            "DB_UID": DB_UID,
            "DB_PWD": DB_PWD,
            "DB_HOST": DB_HOST,
            "DB_PORT": DB_PORT,
        },
        "TESTNET": {
            "NEAR_RPC_URL": TESTNET_RPC_URL,
            "FARMING_CONTRACT": "v2.ref-farming.testnet",
            "REF_CONTRACT": "ref-finance-101.testnet",
            "XREF_CONTRACT": "xref.ref-dev.testnet",
            "USN_CONTRACT": "usdn.testnet",
            "DCL_POOL_CONTRACT": "dcl.ref-dev.testnet",
            "DCL_CONTRACT": "dcl.ref-dev.testnet",
            "ORDERLY_CONTRACT": "asset-manager.orderly.testnet",
            "REDIS_KEY": "FARMS_TESTNET",
            "REDIS_POOL_KEY": "POOLS_TESTNET",
            "REDIS_POOL_BY_TOKEN_KEY": "POOLS_BY_TOKEN_TESTNET",
            "REDIS_TOP_POOL_KEY": "TOP_POOLS_TESTNET",
            "REDIS_TOKEN_PRICE_KEY": "TOKEN_PRICE_TESTNET",
            "REDIS_HISTORY_TOKEN_PRICE_KEY": "HISTORY_TOKEN_PRICE_TESTNET",
            "REDIS_PROPOSAL_ID_HASH_KEY": "PROPOSAL_ID_HASH_TESTNET",
            "REDIS_TOKEN_METADATA_KEY": "TOKEN_METADATA_TESTNET",
            "REDIS_WHITELIST_KEY": "WHITELIST_TESTNET",
            "REDIS_DCL_POOLS_VOLUME_24H_KEY": "DCL_POOLS_VOLUME_24H_TESTNET",
            "REDIS_DCL_POOLS_VOLUME_LIST_KEY": "DCL_POOLS_VOLUME_LIST_TESTNET",
            "REDIS_DCL_POOLS_TVL_LIST_KEY": "DCL_POOLS_TVL_LIST_TESTNET",
            "INDEXER_DSN": "testnet_explorer",
            "INDEXER_UID": "public_readonly",
            "INDEXER_PWD": "nearprotocol",
            "INDEXER_HOST": "35.184.214.98",
            "INDEXER_PORT": "5432",
            "DB_DSN": DB_DSN,
            "DB_UID": DB_UID,
            "DB_PWD": DB_PWD,
            "DB_HOST": DB_HOST,
            "DB_PORT": DB_PORT,
        },
        "MAINNET": {
            "NEAR_RPC_URL": MAINNET_RPC_URL,
            "FARMING_CONTRACT": "v2.ref-farming.near",
            "REF_CONTRACT": "v2.ref-finance.near",
            "XREF_CONTRACT": "xtoken.ref-finance.near",
            "BOOSTFARM_CONTRACT": "boostfarm.ref-labs.near",
            "USN_CONTRACT": "usn",
            "DCL_POOL_CONTRACT": "dclv2.ref-labs.near",
            "DCL_CONTRACT": "dclv2.ref-labs.near",
            "ORDERLY_CONTRACT": "asset-manager.orderly-network.near",
            "REDIS_KEY": "FARMS_MAINNET",
            "REDIS_POOL_BY_TOKEN_KEY": "POOLS_BY_TOKEN_MAINNET",
            "REDIS_POOL_KEY": "POOLS_MAINNET",
            "REDIS_TOP_POOL_KEY": "TOP_POOLS_MAINNET",
            "REDIS_TOKEN_PRICE_KEY": "TOKEN_PRICE_MAINNET",
            "REDIS_HISTORY_TOKEN_PRICE_KEY": "HISTORY_TOKEN_PRICE_MAINNET",
            "REDIS_PROPOSAL_ID_HASH_KEY": "PROPOSAL_ID_HASH_MAINNET",
            "REDIS_TOKEN_METADATA_KEY": "TOKEN_METADATA_MAINNET",
            "REDIS_WHITELIST_KEY": "WHITELIST_MAINNET",
            "REDIS_DCL_POOLS_VOLUME_24H_KEY": "DCL_POOLS_VOLUME_24H_MAINNET",
            "REDIS_DCL_POOLS_VOLUME_LIST_KEY": "DCL_POOLS_VOLUME_LIST_MAINNET",
            "REDIS_DCL_POOLS_TVL_LIST_KEY": "DCL_POOLS_TVL_LIST_MAINNET",
            "REDIS_ACCOUNT_POOL_ASSETS_KEY": "ACCOUNT_POOL_ASSETS_MAINNET",
            "INDEXER_DSN": INDEXER_DSN,
            "INDEXER_UID": INDEXER_UID,
            "INDEXER_PWD": INDEXER_PWD,
            "INDEXER_HOST": INDEXER_HOST,
            "INDEXER_PORT": INDEXER_PORT,
            "DB_DSN": DB_DSN,
            "DB_UID": DB_UID,
            "DB_PWD": DB_PWD,
            "DB_HOST": DB_HOST,
            "DB_PORT": DB_PORT,
            "NEAR_LAKE_DB_DSN": NEAR_LAKE_DB_DSN,
            "NEAR_LAKE_DB_UID": NEAR_LAKE_DB_UID,
            "NEAR_LAKE_DB_PWD": NEAR_LAKE_DB_PWD,
            "NEAR_LAKE_DB_HOST": NEAR_LAKE_DB_HOST,
            "NEAR_LAKE_DB_PORT": NEAR_LAKE_DB_PORT,
            "NEAR_LAKE_DCL_DB_DSN": NEAR_LAKE_DCL_DB_DSN,
            "BLOCK_HEIGHT_FOLDER_PATH": "/data/web/indexer-helper/backends/",
        }
    }
    TOKENS = {
        "DEVNET": [
            {"SYMBOL": "near", "NEAR_ID": "wrap.testnet", "MD_ID": "near", "DECIMAL": 24},
            {"SYMBOL": "nDAI", "NEAR_ID": "ndai.ft-fin.testnet", "MD_ID": "dai", "DECIMAL": 8},
            {"SYMBOL": "nUSDT", "NEAR_ID": "nusdt.ft-fin.testnet", "MD_ID": "tether", "DECIMAL": 6},
            {"SYMBOL": "ref", "NEAR_ID": "rft.tokenfactory.testnet", "MD_ID": "dai", "DECIMAL": 8},
            {"SYMBOL": "ref2", "NEAR_ID": "ref.fakes.testnet", "MD_ID": "dai", "DECIMAL": 18},
            {"SYMBOL": "nUSDC", "NEAR_ID": "nusdc.ft-fin.testnet", "MD_ID": "usd-coin", "DECIMAL": 6},
            {"SYMBOL": "nWETH", "NEAR_ID": "weth.fakes.testnet", "MD_ID": "weth", "DECIMAL": 18},
            {"SYMBOL": "STNEAR", "NEAR_ID": "stnear.fakes.testnet", "MD_ID": "near", "DECIMAL": 24},
            {"SYMBOL": "ETH", "NEAR_ID": "eth.fakes.testnet", "MD_ID": "ethereum", "DECIMAL": 18},
            {"SYMBOL": "HAPI", "NEAR_ID": "hapi.fakes.testnet", "MD_ID": "dai", "DECIMAL": 18},
            {"SYMBOL": "SKYWARD", "NEAR_ID": "skyward.fakes.testnet", "MD_ID": "dai", "DECIMAL": 18},
            {"SYMBOL": "BANANA", "NEAR_ID": "banana.ft-fin.testnet", "MD_ID": "dai", "DECIMAL": 18},
            {"SYMBOL": "PARAS", "NEAR_ID": "paras.fakes.testnet", "MD_ID": "dai", "DECIMAL": 18},
            {"SYMBOL": "PULSE", "NEAR_ID": "pulse.fakes.testnet", "MD_ID": "dai", "DECIMAL": 18},
            {"SYMBOL": "AURORA", "NEAR_ID": "aurora.fakes.testnet", "MD_ID": "dai", "DECIMAL": 18},
            {"SYMBOL": "OCT", "NEAR_ID": "oct.fakes.testnet", "MD_ID": "dai", "DECIMAL": 18},
            {"SYMBOL": "USDT", "NEAR_ID": "usdt.fakes.testnet", "MD_ID": "dai", "DECIMAL": 6},
            {"SYMBOL": "USDC", "NEAR_ID": "usdc.fakes.testnet", "MD_ID": "dai", "DECIMAL": 6},
            {"SYMBOL": "DAI", "NEAR_ID": "dai.fakes.testnet", "MD_ID": "dai", "DECIMAL": 18},
            {"SYMBOL": "HBTC", "NEAR_ID": "hbtc.fakes.testnet", "MD_ID": "huobi-btc", "DECIMAL": 18},
            {"SYMBOL": "WBTC", "NEAR_ID": "wbtc.fakes.testnet", "MD_ID": "wrapped-bitcoin", "DECIMAL": 8},
            {"SYMBOL": "cUSD", "NEAR_ID": "cusd.fakes.testnet", "MD_ID": "celo-dollar", "DECIMAL": 24},
            {"SYMBOL": "STNEAR", "NEAR_ID": "meta-v2.pool.testnet", "MD_ID": "exchange.ref-dev.testnet|621|wrap.testnet", "DECIMAL": 24},
            {"SYMBOL": "LINEAR", "NEAR_ID": "linear-protocol.testnet", "MD_ID": "exchange.ref-dev.testnet|622|wrap.testnet", "DECIMAL": 24},
            {"SYMBOL": "xREF", "NEAR_ID": "xref.ref-dev.testnet", "MD_ID": "xref.ref-dev.testnet|NA|ref.fakes.testnet", "DECIMAL": 18},
        ],
        "TESTNET": [
            {"SYMBOL": "near", "NEAR_ID": "wrap.testnet", "MD_ID": "near", "DECIMAL": 24},
            {"SYMBOL": "nDAI", "NEAR_ID": "ndai.ft-fin.testnet", "MD_ID": "dai", "DECIMAL": 8},
            {"SYMBOL": "nUSDT", "NEAR_ID": "nusdt.ft-fin.testnet", "MD_ID": "tether", "DECIMAL": 6},
            {"SYMBOL": "ref", "NEAR_ID": "rft.tokenfactory.testnet", "MD_ID": "dai", "DECIMAL": 8},
            {"SYMBOL": "ref2", "NEAR_ID": "ref.fakes.testnet", "MD_ID": "dai", "DECIMAL": 18},
            {"SYMBOL": "nUSDC", "NEAR_ID": "nusdc.ft-fin.testnet", "MD_ID": "usd-coin", "DECIMAL": 6},
            {"SYMBOL": "nWETH", "NEAR_ID": "weth.fakes.testnet", "MD_ID": "weth", "DECIMAL": 18},
            {"SYMBOL": "STNEAR", "NEAR_ID": "stnear.fakes.testnet", "MD_ID": "near", "DECIMAL": 24},
            {"SYMBOL": "ETH", "NEAR_ID": "eth.fakes.testnet", "MD_ID": "ethereum", "DECIMAL": 18},
            {"SYMBOL": "HAPI", "NEAR_ID": "hapi.fakes.testnet", "MD_ID": "dai", "DECIMAL": 18},

            {"SYMBOL": "SKYWARD", "NEAR_ID": "skyward.fakes.testnet", "MD_ID": "dai", "DECIMAL": 18}, 
            {"SYMBOL": "BANANA", "NEAR_ID": "banana.ft-fin.testnet", "MD_ID": "dai", "DECIMAL": 18},
            {"SYMBOL": "PARAS", "NEAR_ID": "paras.fakes.testnet", "MD_ID": "dai", "DECIMAL": 18},
            {"SYMBOL": "PULSE", "NEAR_ID": "pulse.fakes.testnet", "MD_ID": "dai", "DECIMAL": 18},
            {"SYMBOL": "AURORA", "NEAR_ID": "aurora.fakes.testnet", "MD_ID": "dai", "DECIMAL": 18},
	        {"SYMBOL": "OCT", "NEAR_ID": "oct.fakes.testnet", "MD_ID": "dai", "DECIMAL": 18},
            {"SYMBOL": "USDT", "NEAR_ID": "usdt.fakes.testnet", "MD_ID": "dai", "DECIMAL": 6},
            {"SYMBOL": "USDC", "NEAR_ID": "usdc.fakes.testnet", "MD_ID": "dai", "DECIMAL": 6},
            {"SYMBOL": "DAI", "NEAR_ID": "dai.fakes.testnet", "MD_ID": "dai", "DECIMAL": 18},
            {"SYMBOL": "HBTC", "NEAR_ID": "hbtc.fakes.testnet", "MD_ID": "huobi-btc", "DECIMAL": 18},
            {"SYMBOL": "WBTC", "NEAR_ID": "wbtc.fakes.testnet", "MD_ID": "wrapped-bitcoin", "DECIMAL": 8},
            {"SYMBOL": "cUSD", "NEAR_ID": "cusd.fakes.testnet", "MD_ID": "celo-dollar", "DECIMAL": 24},
            {"SYMBOL": "STNEAR", "NEAR_ID": "meta-v2.pool.testnet", "MD_ID": "ref-finance-101.testnet|568|wrap.testnet", "DECIMAL": 24},
            {"SYMBOL": "LINEAR", "NEAR_ID": "linear-protocol.testnet", "MD_ID": "ref-finance-101.testnet|571|wrap.testnet", "DECIMAL": 24},
            {"SYMBOL": "NEARX", "NEAR_ID": "dev-1656877137694-34571929023079", "MD_ID": "dev-1656877137694-34571929023079|NA|wrap.testnet", "DECIMAL": 24},
            {"SYMBOL": "xREF", "NEAR_ID": "xref.ref-finance.testnet", "MD_ID": "xref.ref-finance.testnet|NA|ref.fakes.testnet", "DECIMAL": 18},
        ],
        "MAINNET": [
            {"SYMBOL": "near", "NEAR_ID": "wrap.near", "MD_ID": "near", "DECIMAL": 24},
            {"SYMBOL": "nUSDC", "NEAR_ID": "a0b86991c6218b36c1d19d4a2e9eb0ce3606eb48.factory.bridge.near", "MD_ID": "usd-coin", "DECIMAL": 6},
            {"SYMBOL": "nUSDT", "NEAR_ID": "dac17f958d2ee523a2206206994597c13d831ec7.factory.bridge.near", "MD_ID": "tether", "DECIMAL": 6},            
            {"SYMBOL": "nDAI", "NEAR_ID": "6b175474e89094c44da98b954eedeac495271d0f.factory.bridge.near", "MD_ID": "dai", "DECIMAL": 18},
            {"SYMBOL": "nWETH", "NEAR_ID": "c02aaa39b223fe8d0a0e5c4f27ead9083c756cc2.factory.bridge.near", "MD_ID": "weth", "DECIMAL": 18},
            {"SYMBOL": "n1INCH", "NEAR_ID": "111111111117dc0aa78b770fa6a738034120c302.factory.bridge.near", "MD_ID": "1inch", "DECIMAL": 18},
            {"SYMBOL": "nGRT", "NEAR_ID": "c944e90c64b2c07662a292be6244bdf05cda44a7.factory.bridge.near", "MD_ID": "the-graph", "DECIMAL": 18},
            {"SYMBOL": "SKYWARD", "NEAR_ID": "token.skyward.near", "MD_ID": "v2.ref-finance.near|0|wrap.near", "DECIMAL": 18},
            {"SYMBOL": "REF", "NEAR_ID": "token.v2.ref-finance.near", "MD_ID": "v2.ref-finance.near|79|wrap.near", "DECIMAL": 18},
            {"SYMBOL": "BANANA", "NEAR_ID": "berryclub.ek.near", "MD_ID": "v2.ref-finance.near|5|wrap.near", "DECIMAL": 18},
            {"SYMBOL": "nHT", "NEAR_ID": "6f259637dcd74c767781e37bc6133cd6a68aa161.factory.bridge.near", "MD_ID": "huobi-token", "DECIMAL": 18},
            {"SYMBOL": "nGTC", "NEAR_ID": "de30da39c46104798bb5aa3fe8b9e0e1f348163f.factory.bridge.near", "MD_ID": "gitcoin", "DECIMAL": 18},
            {"SYMBOL": "nUNI", "NEAR_ID": "1f9840a85d5af5bf1d1762f925bdaddc4201f984.factory.bridge.near", "MD_ID": "uniswap", "DECIMAL": 18},
            {"SYMBOL": "nWBTC", "NEAR_ID": "2260fac5e5542a773aa44fbcfedf7c193bc2c599.factory.bridge.near", "MD_ID": "wrapped-bitcoin", "DECIMAL": 8},
            {"SYMBOL": "nLINK", "NEAR_ID": "514910771af9ca656af840dff83e8264ecf986ca.factory.bridge.near", "MD_ID": "chainlink", "DECIMAL": 18},
            {"SYMBOL": "PARAS", "NEAR_ID": "token.paras.near", "MD_ID": "v2.ref-finance.near|377|wrap.near", "DECIMAL": 18},
            {"SYMBOL": "STNEAR", "NEAR_ID": "meta-pool.near", "MD_ID": "v2.ref-finance.near|3514|wrap.near", "DECIMAL": 24},
            {"SYMBOL": "marmaj", "NEAR_ID": "marmaj.tkn.near", "MD_ID": "v2.ref-finance.near|11|wrap.near", "DECIMAL": 18},
            {"SYMBOL": "PULSE", "NEAR_ID": "52a047ee205701895ee06a375492490ec9c597ce.factory.bridge.near", "MD_ID": "v2.ref-finance.near|852|wrap.near", "DECIMAL": 18},
            {"SYMBOL": "ETH", "NEAR_ID": "aurora", "MD_ID": "ethereum", "DECIMAL": 18},
            {"SYMBOL": "AURORA", "NEAR_ID": "aaaaaa20d9e0e2461697782ef11675f668207961.factory.bridge.near", "MD_ID": "v2.ref-finance.near|1395|wrap.near", "DECIMAL": 18},
            {"SYMBOL": "DBIO", "NEAR_ID": "dbio.near", "MD_ID": "v2.ref-finance.near|1371|wrap.near", "DECIMAL": 18},
            {"SYMBOL": "OCT", "NEAR_ID": "f5cfbc74057c610c8ef151a439252680ac68c6dc.factory.bridge.near", "MD_ID": "v2.ref-finance.near|47|wrap.near", "DECIMAL": 18},
            {"SYMBOL": "HAPI", "NEAR_ID": "d9c2d319cd7e6177336b0a9c93c21cb48d84fb54.factory.bridge.near", "MD_ID": "v2.ref-finance.near|250|wrap.near", "DECIMAL": 18},
            {"SYMBOL": "META", "NEAR_ID": "meta-token.near", "MD_ID": "v2.ref-finance.near|1559|wrap.near", "DECIMAL": 24},
            {"SYMBOL": "nUSDO", "NEAR_ID": "v3.oin_finance.near", "MD_ID": "v2.ref-finance.near|2043|wrap.near", "DECIMAL": 8},
            {"SYMBOL": "FLX", "NEAR_ID": "3ea8ea4237344c9931214796d9417af1a1180770.factory.bridge.near", "MD_ID": "v2.ref-finance.near|2330|wrap.near", "DECIMAL": 18},
            {"SYMBOL": "PXT", "NEAR_ID": "pixeltoken.near", "MD_ID": "v2.ref-finance.near|1178|wrap.near", "DECIMAL": 6},
            {"SYMBOL": "MYRIA", "NEAR_ID": "myriadcore.near", "MD_ID": "v2.ref-finance.near|2448|wrap.near", "DECIMAL": 18},
            {"SYMBOL": "CELO", "NEAR_ID": "celo.token.a11bd.near", "MD_ID": "celo", "DECIMAL": 24},
            {"SYMBOL": "cUSD", "NEAR_ID": "cusd.token.a11bd.near", "MD_ID": "celo-dollar", "DECIMAL": 24},
            {"SYMBOL": "ABR", "NEAR_ID": "abr.a11bd.near", "MD_ID": "allbridge", "DECIMAL": 24},
            {"SYMBOL": "SOL", "NEAR_ID": "sol.token.a11bd.near", "MD_ID": "solana", "DECIMAL": 24},
            {"SYMBOL": "UTO", "NEAR_ID": "utopia.secretskelliessociety.near", "MD_ID": "v2.ref-finance.near|2973|wrap.near", "DECIMAL": 8},
            {"SYMBOL": "WOO", "NEAR_ID": "4691937a7508860f876c9c0a2a617e7d9e945d4b.factory.bridge.near", "MD_ID": "woo-network", "DECIMAL": 18},
            {"SYMBOL": "LINEAR", "NEAR_ID": "linear-protocol.near", "MD_ID": "v2.ref-finance.near|3515|wrap.near", "DECIMAL": 24},
            {"SYMBOL": "HBTC", "NEAR_ID": "0316eb71485b0ab14103307bf65a021042c6d380.factory.bridge.near", "MD_ID": "huobi-btc", "DECIMAL": 18},
            {"SYMBOL": "Cheddar", "NEAR_ID": "token.cheddar.near", "MD_ID": "v2.ref-finance.near|2769|wrap.near", "DECIMAL": 24},
            {"SYMBOL": "PEM", "NEAR_ID": "token.pembrock.near", "MD_ID": "v2.ref-finance.near|3449|wrap.near", "DECIMAL": 18},
            {"SYMBOL": "BRRR", "NEAR_ID": "token.burrow.near", "MD_ID": "v2.ref-finance.near|3474|wrap.near", "DECIMAL": 18},
            {"SYMBOL": "ATO", "NEAR_ID": "atocha-token.near", "MD_ID": "v2.ref-finance.near|3519|wrap.near", "DECIMAL": 18},
            {"SYMBOL": "NearX", "NEAR_ID": "nearx.stader-labs.near", "MD_ID": "nearx.stader-labs.near|NA|wrap.near", "DECIMAL": 24},
            {"SYMBOL": "SD", "NEAR_ID": "30d20208d987713f46dfd34ef128bb16c404d10f.factory.bridge.near", "MD_ID": "stader", "DECIMAL": 18},
            {"SYMBOL": "xREF", "NEAR_ID": "xtoken.ref-finance.near", "MD_ID": "xtoken.ref-finance.near|NA|token.v2.ref-finance.near", "DECIMAL": 18},
            {"SYMBOL": "SWEAT", "NEAR_ID": "token.sweat", "MD_ID": "v2.ref-finance.near|3667|wrap.near", "DECIMAL": 18},
            {"SYMBOL": "NearX", "NEAR_ID": "v2-nearx.stader-labs.near", "MD_ID": "v2-nearx.stader-labs.near|NA|wrap.near", "DECIMAL": 24},
            {"SYMBOL": "SEAT", "NEAR_ID": "token.stlb.near", "MD_ID": "v2.ref-finance.near|3714|wrap.near", "DECIMAL": 5},
            {"SYMBOL": "NEKO", "NEAR_ID": "ftv2.nekotoken.near", "MD_ID": "v2.ref-finance.near|3804|a0b86991c6218b36c1d19d4a2e9eb0ce3606eb48.factory.bridge.near", "DECIMAL": 24},
            {"SYMBOL": "UMINT", "NEAR_ID": "e99de844ef3ef72806cf006224ef3b813e82662f.factory.bridge.near", "MD_ID": "v2.ref-finance.near|3815|wrap.near", "DECIMAL": 18},
            {"SYMBOL": "pNEAR", "NEAR_ID": "phoenix-bonds.near", "MD_ID": "v2.ref-finance.near|3819|wrap.near", "DECIMAL": 24},
            {"SYMBOL": "1MIL", "NEAR_ID": "a4ef4b0b23c1fc81d3f9ecf93510e64f58a4a016.factory.bridge.near", "MD_ID": "v2.ref-finance.near|276|wrap.near", "DECIMAL": 18},
            {"SYMBOL": "CUCUMBER", "NEAR_ID": "farm.berryclub.ek.near", "MD_ID": "v2.ref-finance.near|35|wrap.near", "DECIMAL": 18},
            {"SYMBOL": "POTATO", "NEAR_ID": "v1.dacha-finance.near", "MD_ID": "v2.ref-finance.near|1857|wrap.near", "DECIMAL": 18},
            {"SYMBOL": "OIN", "NEAR_ID": "9aeb50f542050172359a0e1a25a9933bc8c01259.factory.bridge.near", "MD_ID": "oin-finance", "DECIMAL": 8},
            {"SYMBOL": "UST", "NEAR_ID": "ust.token.a11bd.near", "MD_ID": "v2.ref-finance.near|2985|wrap.near", "DECIMAL": 24},
            {"SYMBOL": "LUNA", "NEAR_ID": "luna.token.a11bd.near", "MD_ID": "terra-luna-2", "DECIMAL": 24},
            {"SYMBOL": "DEIP", "NEAR_ID": "deip-token.near", "MD_ID": "v2.ref-finance.near|3076|wrap.near", "DECIMAL": 18},
            # {"SYMBOL": "FAR", "NEAR_ID": "far.tokens.fewandfar.near", "MD_ID": "v2.ref-finance.near|1932|wrap.near", "DECIMAL": 8},
            {"SYMBOL": "BSTN", "NEAR_ID": "059a1f1dea1020297588c316ffc30a58a1a0d4a2.factory.bridge.near", "MD_ID": "bastion-protocol", "DECIMAL": 18},
            {"SYMBOL": "TAO", "NEAR_ID": "fusotao-token.near", "MD_ID": "fusotao", "DECIMAL": 18},
            {"SYMBOL": "DISC", "NEAR_ID": "discovol-token.near", "MD_ID": "v2.ref-finance.near|3657|wrap.near", "DECIMAL": 14},
            {"SYMBOL": "APYS", "NEAR_ID": "apys.token.a11bd.near", "MD_ID": "v2.ref-finance.near|3599|wrap.near", "DECIMAL": 24},
        ],
    }
    MARKET_URL = "api.coingecko.com"


if __name__ == '__main__':
    print(type(Cfg))
    print(type(Cfg.TOKENS))
    print(type(Cfg.NETWORK_ID), Cfg.NETWORK_ID)
    print(Cfg.NETWORK["TESTNET"]["NEAR_RPC_URL"])