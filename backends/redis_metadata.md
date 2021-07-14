# Data Structure in Redis

## Farming
---
### FARMS
Key: FARMS_MAINNET / FARMS_TESTNET  
Hash-Key: <farm_id>  
Hash-Value:  
```
{
    farm_id: 'ref-finance.testnet@6#0',
    farm_kind: 'SIMPLE_FARM',
    farm_status: 'Ended',
    seed_id: 'ref-finance.testnet@6',
    reward_token: 'rft.tokenfactory.testnet',
    start_at: '51012675',
    reward_per_session: '18000000000',
    session_interval: '3600',
    total_reward: '9000000000000',
    cur_round: '500',
    last_round: '0',
    claimed_reward: '0',
    unclaimed_reward: '9000000000000'
  }
```
## Swapping
---
### POOLS
Key: POOLS_MAINNET / POOLS_TESTNET
Hash-Key: "0"  
Hash-Value:  
```
{
    "id": 0,
    pool_kind: 'SIMPLE_POOL',
    token_account_ids: [ 'ndai.ft-fin.testnet', 'nusdt.ft-fin.testnet' ],
    amounts: [ '20700009997', '56443138' ],
    total_fee: 30,
    shares_total_supply: '102991180388172233593650535',
    "farming": false,
    "token_symbols": ["ndai", "nusdt"],
}
```

### TOP_POOLS
TOP_POOLS_MAINNET / TOP_POOLS_TESTNET
Hash-Key: "ndai.ft-fin.testnet-nusdt.ft-fin.testnet"  
Hash-Value:  
```
{
    "id": 0,
    pool_kind: 'SIMPLE_POOL',
    token_account_ids: [ 'ndai.ft-fin.testnet', 'nusdt.ft-fin.testnet' ],
    amounts: [ '20700009997', '56443138' ],
    total_fee: 30,
    shares_total_supply: '102991180388172233593650535',
    "farming": false,
    "token_symbols": ["ndai", "nusdt"],
    "vol01": {"input": "21446390442353750416480", "output": "120575689186752695966185140254"},
    "vol10": {"input": "122086562332274468655791467175", "output": "2171487143557087500828"},
}
```

### POOLS_BY_TOKEN
POOLS_BY_TOKEN_MAINNET / POOLS_BY_TOKEN_TESTNET  
Hash-Key: "ndai.ft-fin.testnet-nusdt.ft-fin.testnet"  
Hash-Value:  
```
[
    {
        "id": 0,
        pool_kind: 'SIMPLE_POOL',
        token_account_ids: [ 'ndai.ft-fin.testnet', 'nusdt.ft-fin.testnet' ],
        amounts: [ '20700009997', '56443138' ],
        total_fee: 30,
        shares_total_supply: '102991180388172233593650535',
        "farming": false,
        "token_symbols": ["ndai", "nusdt"],
    },
    ...
]
```


## Token
---
### TOKEN_PRICE_MAINNET  
Hash-Key: <token_contract_id>  
Hash-Value: "1.00001111"

### TOKEN_METADATA_MAINNET  
Hash-Key: <token_contract_id>  
Hash-Value: 
```
{
    "spec":"", 
    "name": contract_id, 
    "symbol": contract_id, 
    "icon":"",
    "reference": "",
    "reference_hash": "",
    "decimals": 0
} 
```

### WHITELIST_MAINNET
Hash-Key: <token_contract_id>  
Hash-Value: 
```
{
    "spec":"", 
    "name": contract_id, 
    "symbol": contract_id, 
    "icon":"",
    "reference": "",
    "reference_hash": "",
    "decimals": 0
} 
```