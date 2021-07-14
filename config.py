#!/usr/bin/env python
# -*- coding:utf-8 -*-
__author__ = 'Marco'

"""

"""


class Cfg:
    NETWORK_ID = "MAINNET"
    NETWORK = {
        "TESTNET": {
            "NEAR_RPC_URL": [
                "https://rpc.testnet.near.org", 
            ],
            "FARMING_CONTRACT": "ref-farming.testnet",
            "REF_CONTRACT": "ref-finance.testnet",
            "REDIS_KEY": "FARMS_TESTNET",
            "REDIS_POOL_KEY": "POOLS_TESTNET",
            "REDIS_POOL_BY_TOKEN_KEY": "POOLS_BY_TOKEN_TESTNET",
            "REDIS_TOP_POOL_KEY": "TOP_POOLS_TESTNET",
            "REDIS_TOKEN_PRICE_KEY": "TOKEN_PRICE_TESTNET",
            "REDIS_TOKEN_METADATA_KEY": "TOKEN_METADATA_TESTNET",
            "REDIS_WHITELIST_KEY": "WHITELIST_TESTNET",
            "INDEXER_DSN": "testnet_explorer",
            "INDEXER_UID": "public_readonly",
            "INDEXER_PWD": "nearprotocol",
            "INDEXER_HOST": "35.184.214.98",
            "INDEXER_PORT": "5432",
        },
        "MAINNET": {
            "NEAR_RPC_URL": [
                "https://rpc.mainnet.near.org", 
            ],
            "FARMING_CONTRACT": "ref-farming.near",
            "REF_CONTRACT": "ref-finance.near",
            "REDIS_KEY": "FARMS_MAINNET",
            "REDIS_POOL_BY_TOKEN_KEY": "POOLS_BY_TOKEN_MAINNET",
            "REDIS_POOL_KEY": "POOLS_MAINNET",
            "REDIS_TOP_POOL_KEY": "TOP_POOLS_MAINNET",
            "REDIS_TOKEN_PRICE_KEY": "TOKEN_PRICE_MAINNET",
            "REDIS_TOKEN_METADATA_KEY": "TOKEN_METADATA_MAINNET",
            "REDIS_WHITELIST_KEY": "WHITELIST_MAINNET",
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
            {"SYMBOL": "ref", "NEAR_ID": "rft.tokenfactory.testnet", "MD_ID": "ref-finance.testnet|24|wrap.testnet", "DECIMAL": 8},
        ],
        "MAINNET": [
            {"SYMBOL": "near", "NEAR_ID": "wrap.near", "MD_ID": "near", "DECIMAL": 24},
            {"SYMBOL": "nDAI", "NEAR_ID": "6b175474e89094c44da98b954eedeac495271d0f.factory.bridge.near", "MD_ID": "dai", "DECIMAL": 18},
            {"SYMBOL": "nUSDT", "NEAR_ID": "dac17f958d2ee523a2206206994597c13d831ec7.factory.bridge.near", "MD_ID": "tether", "DECIMAL": 6},
            {"SYMBOL": "nUNI", "NEAR_ID": "1f9840a85d5af5bf1d1762f925bdaddc4201f984.factory.bridge.near", "MD_ID": "uniswap", "DECIMAL": 18},
            {"SYMBOL": "nLINK", "NEAR_ID": "514910771af9ca656af840dff83e8264ecf986ca.factory.bridge.near", "MD_ID": "chainlink", "DECIMAL": 18},
            {"SYMBOL": "nUSDC", "NEAR_ID": "a0b86991c6218b36c1d19d4a2e9eb0ce3606eb48.factory.bridge.near", "MD_ID": "usd-coin", "DECIMAL": 6},
            {"SYMBOL": "nWBTC", "NEAR_ID": "2260fac5e5542a773aa44fbcfedf7c193bc2c599.factory.bridge.near", "MD_ID": "wrapped-bitcoin", "DECIMAL": 8},
            {"SYMBOL": "nAAVE", "NEAR_ID": "7fc66500c84a76ad7e9c93437bfc5ac33e2ddae9.factory.bridge.near", "MD_ID": "aave", "DECIMAL": 18},
            {"SYMBOL": "nCRO", "NEAR_ID": "a0b73e1ff0b80914ab6fe0444e65848c4c34450b.factory.bridge.near", "MD_ID": "crypto-com-chain", "DECIMAL": 8},
            {"SYMBOL": "nFTT", "NEAR_ID": "50d1c9771902476076ecfc8b2a83ad6b9355a4c9.factory.bridge.near", "MD_ID": "ftx-token", "DECIMAL": 18},
            {"SYMBOL": "nBUSD", "NEAR_ID": "4fabb145d64652a948d72533023f6e7a623c7c53.factory.bridge.near", "MD_ID": "binance-usd", "DECIMAL": 18},
            {"SYMBOL": "nHT", "NEAR_ID": "6f259637dcd74c767781e37bc6133cd6a68aa161.factory.bridge.near", "MD_ID": "huobi-token", "DECIMAL": 18},
            {"SYMBOL": "nSUSHI", "NEAR_ID": "6b3595068778dd592e39a122f4f5a5cf09c90fe2.factory.bridge.near", "MD_ID": "sushi", "DECIMAL": 18},
            {"SYMBOL": "nSNX", "NEAR_ID": "c011a73ee8576fb46f5e1c5751ca3b9fe0af2a6f.factory.bridge.near", "MD_ID": "havven", "DECIMAL": 18},
            {"SYMBOL": "nGRT", "NEAR_ID": "c944e90c64b2c07662a292be6244bdf05cda44a7.factory.bridge.near", "MD_ID": "the-graph", "DECIMAL": 18},
            {"SYMBOL": "nMKR", "NEAR_ID": "9f8f72aa9304c8b593d555f12ef6589cc3a579a2.factory.bridge.near", "MD_ID": "maker", "DECIMAL": 18},
            {"SYMBOL": "nCOMP", "NEAR_ID": "c00e94cb662c3520282e6f5717214004a7f26888.factory.bridge.near", "MD_ID": "compound-governance-token", "DECIMAL": 18},
            {"SYMBOL": "nYFI", "NEAR_ID": "0bc529c00c6401aef6d220be8c6ea1667f6ad93e.factory.bridge.near", "MD_ID": "yearn-finance", "DECIMAL": 18},
            {"SYMBOL": "nWETH", "NEAR_ID": "c02aaa39b223fe8d0a0e5c4f27ead9083c756cc2.factory.bridge.near", "MD_ID": "weth", "DECIMAL": 18},
            {"SYMBOL": "nHBTC", "NEAR_ID": "0316eb71485b0ab14103307bf65a021042c6d380.factory.bridge.near", "MD_ID": "huobi-btc", "DECIMAL": 18},
            {"SYMBOL": "n1INCH", "NEAR_ID": "111111111117dc0aa78b770fa6a738034120c302.factory.bridge.near", "MD_ID": "1inch", "DECIMAL": 18},
        ],
    }
    MARKET_URL = "api.coingecko.com"


if __name__ == '__main__':
    print(type(Cfg))
    print(type(Cfg.TOKENS))
    print(type(Cfg.NETWORK_ID), Cfg.NETWORK_ID)