#!/usr/bin/env python
# -*- coding:utf-8 -*-
__author__ = 'Marco'

"""

"""


class Cfg:
    NETWORK_ID = "TESTNET"
    NETWORK = {
        "TESTNET": {
            "NEAR_RPC_URL": "https://rpc.testnet.near.org",
            "FARMING_CONTRACT": "ref-farming.testnet",
            "REF_CONTRACT": "ref-finance.testnet",
            "REDIS_KEY": "FARMS_TESTNET",
            "REDIS_POOL_KEY": "POOLS_TESTNET",
            "REDIS_TOP_POOL_KEY": "TOP_POOLS_TESTNET",
            "REDIS_TOKEN_PRICE_KEY": "TOKEN_PRICE_TESTNET",
            "REDIS_TOKEN_METADATA_KEY": "TOKEN_METADATA_TESTNET",
            "INDEXER_DSN": "testnet_explorer",
            "INDEXER_UID": "public_readonly",
            "INDEXER_PWD": "nearprotocol",
            "INDEXER_HOST": "35.184.214.98",
            "INDEXER_PORT": "5432",
        },
        "MAINNET": {
            "NEAR_RPC_URL": "https://rpc.mainnet.near.org",
            "FARMING_CONTRACT": "ref-farming.near",
            "REF_CONTRACT": "ref-finance.near",
            "REDIS_KEY": "FARMS_MAINNET",
            "REDIS_POOL_KEY": "POOLS_MAINNET",
            "REDIS_TOP_POOL_KEY": "TOP_POOLS_MAINNET",
            "REDIS_TOKEN_PRICE_KEY": "TOKEN_PRICE_MAINNET",
            "REDIS_TOKEN_METADATA_KEY": "TOKEN_METADATA_MAINNET",
            "INDEXER_DSN": "mainnet_explorer",
            "INDEXER_UID": "public_readonly",
            "INDEXER_PWD": "nearprotocol",
            "INDEXER_HOST": "104.199.89.51",
            "INDEXER_PORT": "5432",
        }
    }
    TOKENS = {
        "TESTNET": [
            {"SYMBOL": "near", "NEAR_ID": "wrap.testnet", "MD_ID": "near", "DECIMAL": 24},
            {"SYMBOL": "nDAI", "NEAR_ID": "ndai.ft-fin.testnet", "MD_ID": "dai", "DECIMAL": 8},
            {"SYMBOL": "nUSDT", "NEAR_ID": "nusdt.ft-fin.testnet", "MD_ID": "tether", "DECIMAL": 6},
        ],
        "MAINNET": [
            {"SYMBOL": "near", "NEAR_ID": "wrap.near", "MD_ID": "near", "DECIMAL": 24},
            {"SYMBOL": "nDAI", "NEAR_ID": "6b175474e89094c44da98b954eedeac495271d0f.factory.bridge.near", "MD_ID": "dai", "DECIMAL": 18},
            {"SYMBOL": "nUSDT", "NEAR_ID": "dac17f958d2ee523a2206206994597c13d831ec7.factory.bridge.near", "MD_ID": "tether", "DECIMAL": 6},
        ],
    }
    MARKET_URL = "api.coingecko.com"


if __name__ == '__main__':
    print(type(Cfg))
    print(type(Cfg.TOKENS))
    print(type(Cfg.NETWORK_ID), Cfg.NETWORK_ID)