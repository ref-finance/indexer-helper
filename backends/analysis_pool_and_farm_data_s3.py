import boto3
import os
import json
import shutil
import sys

sys.path.append('../')
from db_provider import add_account_assets_data, get_token_price, handle_account_pool_assets_data
import decimal
from config import Cfg

AWS_REGION_NAME = 'us-east-1'

'''
BUCKET_NAME = "xxxxxxxxxx"  
AWS_S3_AKI = 'xxxxxxxxxx' #aws_access_key_id
AWS_S3_SAK = 'xxxxxxxxxx' #aws_secret_access_key
'''

BUCKET_NAME = "xxxxxxxxxx"
AWS_S3_AKI = 'xxxxxxxxxx'  # aws_access_key_id
AWS_S3_SAK = 'xxxxxxxxxx'  # aws_secret_access_key

# s3
s3 = boto3.client('s3', region_name=AWS_REGION_NAME, aws_access_key_id=AWS_S3_AKI, aws_secret_access_key=AWS_S3_SAK)

ctx = decimal.Context()
ctx.prec = 20


# return all objects using paging
def get_last_block_height_from_all_s3_folders_list(Prefix=None):
    folders_list = []
    paginator = s3.get_paginator('list_objects_v2')
    pages = paginator.paginate(Bucket=BUCKET_NAME, Delimiter='/', Prefix=Prefix)
    for page in pages:
        common_prefixes = page.get("CommonPrefixes")
        for dir in common_prefixes:
            pathname = dir.get("Prefix")
            loc = pathname.find('_') + 1
            block_height = pathname[loc:len(pathname) - 1]
            folders_list.append(int(block_height))

    return max(folders_list)


def get_all_files_list(Prefix=None):
    file_name_list = []
    print(f'Start getting files from s3.')
    try:
        if Prefix is not None:
            paginator = s3.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=BUCKET_NAME, Prefix=Prefix)
            for page in pages:
                # print(page)
                contents = page.get("Contents")
                for content in contents:
                    pathname = content.get("Key")
                    file_name_list.append(pathname)
        else:
            paginator = s3.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=BUCKET_NAME, Prefix=Prefix)
            for page in pages:
                # print(page)
                contents = page.get("Contents")
                for content in contents:
                    pathname = content.get("Key")
                    file_name_list.append(pathname)

    except Exception as e:
        print(f'Get files list failed. | Exception: {e}')
        return file_name_list

    print(f'Get file list successful.')

    return file_name_list


def download_file_local(object_name, file_name):
    s3.download_file(BUCKET_NAME, object_name, file_name)


def download_file_s3():
    last_block_height = get_last_block_height_from_all_s3_folders_list(Prefix='output/')
    print("last_block_height = ", last_block_height)
    block_height_folder_name = "height_" + str(last_block_height)
    if not os.path.exists("./" + block_height_folder_name):
        os.mkdir(block_height_folder_name)
    folder = "output/" + block_height_folder_name + "/"
    file_list = get_all_files_list(folder)
    # print("file_list", file_list)
    # last_modified = s3.head_object(Bucket=BUCKET_NAME, Key=file_list[0])['LastModified']
    # print("last_modified =", last_modified)
    for file_name in file_list:
        if "ex_pool" in file_name or "farm_accounts" in file_name or "farmv2_accounts" in file_name or "ex_accounts" in file_name or "farmv2_seeds" in file_name:
            loc = file_name.find('/') + 1
            path_local = "./" + file_name[loc:len(file_name)]
            print(path_local)
            download_file_local(file_name, path_local)
    return block_height_folder_name


def add_data_to_db(block_height_folder_name, network_id):
    import re
    import math
    # path_to_jsonfiles = "C:\\Users\\sjl\\Desktop\\portfolio\\" + block_height_folder_name
    path_to_jsonfiles = Cfg.NETWORK[network_id]["BLOCK_HEIGHT_FOLDER_PATH"] + block_height_folder_name
    tokens_price = get_token_price()
    pool_data_list = {}
    farm_data_list = {}
    for file in os.listdir(path_to_jsonfiles):
        account_assets_data_list = []
        full_filename = "%s/%s" % (path_to_jsonfiles, file)
        if "ex_pool" in file:
            with open(full_filename, 'r') as fi:
                pool_dict = json.load(fi)
                pool_id = str(re.findall("ex_pool_(.*?).json", file)[0])
                pool_shares = pool_dict["shares"]
                pool_shares_total_supply = pool_dict["shares_total_supply"]
                token_account_ids = pool_dict["token_account_ids"]
                pool_amounts = pool_dict["amounts"]
                for account, amount in pool_shares.items():
                    token_data = count_account_amount(tokens_price, pool_amounts, pool_shares_total_supply, amount,
                                                      token_account_ids)
                    pool_assets_data = {"type": "pool", "pool_id": pool_id, "farm_id": "", "account_id": account,
                                        "tokens": str(pool_dict["token_account_ids"]),
                                        "token_amounts": token_data["token_amounts"],
                                        "token_decimals": token_data["token_decimals"],
                                        "token_prices": token_data["token_prices"], "amount": token_data["amount"]}
                    account_assets_data_list.append(pool_assets_data)
                pool_data_list[pool_id] = {
                    "shares_total_supply": pool_shares_total_supply,
                    "token_account_ids": token_account_ids,
                    "pool_amounts": pool_amounts
                }
        if len(account_assets_data_list) > 0:
            add_account_assets_data(account_assets_data_list)
            # print("ex_pool:", account_assets_data_list)
        if "farmv2_seeds" in file:
            with open(full_filename, 'r') as fi:
                farmv2_seeds = json.load(fi)
                for seed_id, seed_data in farmv2_seeds.items():
                    farms = seed_data["farms"]
                    for farm in farms:
                        farm_data_list[farm["farm_id"]] = {
                            "reward_token": farm["terms"]["reward_token"],
                            "rps": farm["rps"]
                        }
            print("farm_data_list", farm_data_list)

    for file in os.listdir(path_to_jsonfiles):
        account_assets_data_list = []
        full_filename = "%s/%s" % (path_to_jsonfiles, file)
        if "ex_accounts" in file:
            with open(full_filename, 'r') as fi:
                ex_accounts_dict = json.load(fi)
                for account, account_data in ex_accounts_dict.items():
                    tokens = []
                    token_amounts = []
                    token_decimals = []
                    token_prices = []
                    near_amount = account_data["near_amount"]
                    near_price = float(tokens_price["wrap.near"]["price"])
                    near_decimal = tokens_price["wrap.near"]["decimal"]
                    tokens.append("wrap.near")
                    token_amounts.append(near_amount)
                    token_decimals.append(near_decimal)
                    token_prices.append(near_price)
                    dis = int("1" + "0" * near_decimal)
                    amount = near_amount / dis * near_price
                    account_tokens = account_data["tokens"]
                    if len(account_tokens) > 0:
                        account_assets_data_list.append(handle_tokens_data(account_tokens, tokens_price,
                                                                       "ex_fixed_assets", account, tokens,
                                                                       token_amounts, token_decimals, token_prices, amount))
        if "farm_accounts" in file:
            with open(full_filename, 'r') as fi:
                farm_dict = json.load(fi)
                for account, account_data in farm_dict.items():
                    tokens = []
                    token_amounts = []
                    token_decimals = []
                    token_prices = []
                    near_amount = account_data["amount"]
                    near_price = float(tokens_price["wrap.near"]["price"])
                    near_decimal = tokens_price["wrap.near"]["decimal"]
                    tokens.append("wrap.near")
                    token_amounts.append(near_amount)
                    token_decimals.append(near_decimal)
                    token_prices.append(near_price)
                    dis = int("1" + "0" * near_decimal)
                    amount = near_amount / dis * near_price
                    rewards_tokens = account_data["rewards"]
                    if len(rewards_tokens) > 0:
                        account_assets_data_list.append(handle_tokens_data(rewards_tokens, tokens_price,
                                                                       "farm_rewards_assets", account, tokens,
                                                                       token_amounts, token_decimals, token_prices, amount))
                    farm_seeds = account_data["seeds"]
                    for farm_id, farm_amount in farm_seeds.items():
                        pool_id = farm_id.split("@")[1]
                        if pool_id in pool_data_list:
                            pool_data = pool_data_list[pool_id]
                            token_data = count_account_amount(tokens_price, pool_data["pool_amounts"],
                                                              pool_data["shares_total_supply"], farm_amount,
                                                              pool_data["token_account_ids"])
                            farm_assets_data = {"type": "farm", "pool_id": pool_id, "farm_id": farm_id, "account_id": account,
                                                "tokens": str(pool_data["token_account_ids"]),
                                                "token_amounts": token_data["token_amounts"],
                                                "token_decimals": token_data["token_decimals"],
                                                "token_prices": token_data["token_prices"], "amount": token_data["amount"]}
                            account_assets_data_list.append(farm_assets_data)
        if "farmv2_accounts" in file:
            with open(full_filename, 'r') as fi:
                farmv2_dict = json.load(fi)
                for account, account_data in farmv2_dict.items():
                    tokens = []
                    token_amounts = []
                    token_decimals = []
                    token_prices = []
                    amount = 0
                    rewards_tokens = account_data["rewards"]
                    if len(rewards_tokens) > 0:
                        account_assets_data_list.append(handle_tokens_data(rewards_tokens, tokens_price,
                                                                       "farmv2_rewards_assets", account, tokens,
                                                                       token_amounts, token_decimals, token_prices, amount))
                    farmv2_seeds = account_data["seeds"]
                    for farm_id, farmv2_seed_data in farmv2_seeds.items():
                        farmer_seed_power = farmv2_seed_data["free_amount"] + farmv2_seed_data["x_locked_amount"]
                        pool_id = farm_id.split("@")[1]
                        if pool_id in pool_data_list:
                            pool_data = pool_data_list[pool_id]
                            token_data = count_account_amount(tokens_price, pool_data["pool_amounts"],
                                                              pool_data["shares_total_supply"], farmv2_seed_data["free_amount"],
                                                              pool_data["token_account_ids"])
                            farm_assets_data = {"type": "farmv2", "pool_id": pool_id, "farm_id": farm_id,
                                                "account_id": account,
                                                "tokens": str(pool_data["token_account_ids"]),
                                                "token_amounts": token_data["token_amounts"],
                                                "token_decimals": token_data["token_decimals"],
                                                "token_prices": token_data["token_prices"],
                                                "amount": token_data["amount"]}
                            account_assets_data_list.append(farm_assets_data)
                        user_rps = farmv2_seed_data["user_rps"]
                        for user_farm_id, user_farm_rps in user_rps.items():
                            farm_unclaimed_count_amount = 0
                            farm_unclaimed_tokens = []
                            farm_unclaimed_amounts = []
                            farm_unclaimed_decimals = []
                            farm_unclaimed_prices = []
                            reward_amount = (farm_data_list[user_farm_id]["rps"] - user_farm_rps) * farmer_seed_power / math.pow(10, 27)
                            reward_token = farm_data_list[user_farm_id]["reward_token"]
                            farm_unclaimed_tokens.append(reward_token)
                            farm_unclaimed_amounts.append(float_to_str(reward_amount))
                            if reward_token in tokens_price:
                                token_price = float(tokens_price[reward_token]["price"])
                                token_decimal = tokens_price[reward_token]["decimal"]
                                farm_unclaimed_decimals.append(token_decimal)
                                farm_unclaimed_prices.append(token_price)
                                dis = int("1" + "0" * token_decimal)
                                farm_unclaimed_count_amount = reward_amount / dis * token_price
                            else:
                                farm_unclaimed_decimals.append(0)
                                farm_unclaimed_prices.append(0)
                            farm_assets_data = {"type": "farm_unclaimed_rewards_assets", "pool_id": "", "farm_id": user_farm_id,
                                                "account_id": account,
                                                "tokens": str(farm_unclaimed_tokens),
                                                "token_amounts": str(farm_unclaimed_amounts),
                                                "token_decimals": str(farm_unclaimed_decimals),
                                                "token_prices": str(farm_unclaimed_prices),
                                                "amount": str(farm_unclaimed_count_amount)}
                            account_assets_data_list.append(farm_assets_data)

        if len(account_assets_data_list) > 0:
            add_account_assets_data(account_assets_data_list)
            # print("account_assets_data_list", account_assets_data_list)

    return path_to_jsonfiles


def handle_tokens_data(rewards_tokens, tokens_price, assets_type, account, tokens, token_amounts, token_decimals,
                       token_prices, amount):
    for token, token_amount in rewards_tokens.items():
        tokens.append(token)
        token_amounts.append(token_amount)
        if token in tokens_price:
            token_price = float(tokens_price[token]["price"])
            token_decimal = tokens_price[token]["decimal"]
            token_decimals.append(token_decimal)
            token_prices.append(token_price)
            dis = int("1" + "0" * token_decimal)
            amount = amount + (token_amount / dis * token_price)
        else:
            token_decimals.append(0)
            token_prices.append(0)
            amount = amount + 0
    fixed_assets_data = {"type": assets_type, "pool_id": "", "farm_id": "", "account_id": account,
                         "tokens": str(tokens),
                         "token_amounts": str(token_amounts),
                         "token_decimals": str(token_decimals),
                         "token_prices": str(token_prices),
                         "amount": amount}
    return fixed_assets_data


def count_account_amount(tokens_price, pool_amounts, pool_shares_total_supply, amount, token_account_ids):
    count_amount = 0
    token_decimals = []
    token_prices = []
    token_amounts = []
    for i in range(0, len(pool_amounts)):
        token_amount = amount * pool_amounts[i] / pool_shares_total_supply
        token_amounts.append(int(float(float_to_str(token_amount))))
        if token_account_ids[i] in tokens_price:
            token_price = float(tokens_price[token_account_ids[i]]["price"])
            token_decimal = tokens_price[token_account_ids[i]]["decimal"]
            token_decimals.append(token_decimal)
            token_prices.append(token_price)
            dis = int("1" + "0" * token_decimal)
            count_amount = count_amount + (token_amount / dis * token_price)
        else:
            token_decimals.append(0)
            token_prices.append(0)
            count_amount = count_amount + 0
    ret_data = {
        "token_decimals": str(token_decimals),
        "token_prices": str(token_prices),
        "amount": count_amount,
        "token_amounts": str(token_amounts)
    }
    return ret_data


def float_to_str(f):
    """
    Convert the given float to a string,
    without resorting to scientific notation
    """
    d1 = ctx.create_decimal(repr(f))
    return format(d1, 'f')


def clear_folder(path):
    # shutil.rmtree(path)
    print("clear_folder path:", path)


if __name__ == "__main__":
    print("#########analysis_pool_and_farm_data###########")
    height_folder_name = ""
    try:
        if len(sys.argv) == 2:
            network_id = str(sys.argv[1]).upper()
            if network_id in ["MAINNET", "TESTNET", "DEVNET"]:
                height_folder_name = download_file_s3()
                print("start add_data_to_db")
                folder_path = add_data_to_db(height_folder_name, network_id)
                print("start clear_folder")
                clear_folder(folder_path)
                print("start handle_account_pool_assets_data")
                handle_account_pool_assets_data(network_id)
                print("analysis_pool_and_farm_data end")
            else:
                print("Error, network_id should be MAINNET, TESTNET or DEVNET")
                exit(1)
        else:
            print("Error, must put NETWORK_ID as arg")
            exit(1)
    except Exception as e:
        print("analysis pool and farm data error,height folder name:", height_folder_name)
        print(e)

    # folder_path = add_data_to_db("height_9", "MAINNET")
    # print("start clear_folder")
    # clear_folder(folder_path)
    # print("start handle_account_pool_assets_data")
    # handle_account_pool_assets_data("MAINNET")
    # print("analysis_pool_and_farm_data end")
