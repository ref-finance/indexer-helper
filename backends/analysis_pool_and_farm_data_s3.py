import boto3
import os
import json
import shutil
import sys

sys.path.append('../')
from db_provider import add_account_assets_data, get_token_price, handle_account_pool_assets_data
import decimal
from config import Cfg
import math

AWS_REGION_NAME = 'us-east-1'
CONSTANT_D = 1.0001

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
        if "ex_pool" in file_name or "farm_accounts" in file_name or "farmv2_accounts" in file_name or "ex_accounts" in file_name or "farmv2_seeds" in file_name or "dcl_pool" in file_name or "dcl_user_assets" in file_name or "dcl_user_liquidities" in file_name or "xref_accounts" in file_name:
            loc = file_name.find('/') + 1
            path_local = "./" + file_name[loc:len(file_name)]
            print(path_local)
            download_file_local(file_name, path_local)
    return block_height_folder_name


def add_data_to_db(block_height_folder_name, network_id):
    import re
    # path_to_jsonfiles = "C:\\Users\\Administrator\\Desktop\\portfolio\\" + block_height_folder_name
    path_to_jsonfiles = Cfg.NETWORK[network_id]["BLOCK_HEIGHT_FOLDER_PATH"] + block_height_folder_name
    tokens_price = get_token_price()
    pool_data_list = {}
    farm_data_list = {}
    dcl_pool_data_list = {}
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
            # print("farm_data_list:", farm_data_list)
        if "dcl_pool" in file:
            with open(full_filename, 'r') as fi:
                dcl_pool_data = json.load(fi)
                for pool_id, pool_data in dcl_pool_data.items():
                    dcl_pool_data_list[pool_id] = {
                        "current_point": pool_data["current_point"],
                        "liquidity": pool_data["liquidity"],
                        "liquidity_x": pool_data["liquidity_x"]
                    }
            # print("dcl_pool_data_list:", dcl_pool_data_list)

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
                                                                           token_amounts, token_decimals, token_prices,
                                                             amount))
        # if "farm_accounts" in file:
        #     with open(full_filename, 'r') as fi:
        #         farm_dict = json.load(fi)
        #         for account, account_data in farm_dict.items():
        #             tokens = []
        #             token_amounts = []
        #             token_decimals = []
        #             token_prices = []
        #             near_amount = account_data["amount"]
        #             near_price = float(tokens_price["wrap.near"]["price"])
        #             near_decimal = tokens_price["wrap.near"]["decimal"]
        #             tokens.append("wrap.near")
        #             token_amounts.append(near_amount)
        #             token_decimals.append(near_decimal)
        #             token_prices.append(near_price)
        #             dis = int("1" + "0" * near_decimal)
        #             amount = near_amount / dis * near_price
        #             rewards_tokens = account_data["rewards"]
        #             if len(rewards_tokens) > 0:
        #                 account_assets_data_list.append(handle_tokens_data(rewards_tokens, tokens_price,
        #                                                                    "farm_rewards_assets", account, tokens,
        #                                                                    token_amounts, token_decimals, token_prices,
        #                                                                    amount))
        #             farm_seeds = account_data["seeds"]
        #             for farm_id, farm_amount in farm_seeds.items():
        #                 pool_id = farm_id.split("@")[1]
        #                 if pool_id in pool_data_list:
        #                     pool_data = pool_data_list[pool_id]
        #                     token_data = count_account_amount(tokens_price, pool_data["pool_amounts"],
        #                                                       pool_data["shares_total_supply"], farm_amount,
        #                                                       pool_data["token_account_ids"])
        #                     farm_assets_data = {"type": "farm", "pool_id": pool_id, "farm_id": farm_id,
        #                                         "account_id": account,
        #                                         "tokens": str(pool_data["token_account_ids"]),
        #                                         "token_amounts": token_data["token_amounts"],
        #                                         "token_decimals": token_data["token_decimals"],
        #                                         "token_prices": token_data["token_prices"],
        #                                         "amount": token_data["amount"]}
        #                     account_assets_data_list.append(farm_assets_data)
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
                                                                           token_amounts, token_decimals, token_prices,
                                                                           amount))
                    farmv2_seeds = account_data["seeds"]
                    for farm_id, farmv2_seed_data in farmv2_seeds.items():
                        farmer_seed_power = farmv2_seed_data["free_amount"] + farmv2_seed_data["x_locked_amount"]
                        pool_id = farm_id.split("@")[1]
                        if pool_id in pool_data_list:
                            pool_data = pool_data_list[pool_id]
                            token_data = count_account_amount(tokens_price, pool_data["pool_amounts"],
                                                              pool_data["shares_total_supply"],
                                                              farmv2_seed_data["free_amount"],
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
                            if user_farm_id in farm_data_list:
                                reward_amount = (farm_data_list[user_farm_id][
                                                     "rps"] - user_farm_rps) * farmer_seed_power / math.pow(10, 27)
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
                                farm_assets_data = {"type": "farm_unclaimed_rewards_assets", "pool_id": "",
                                                    "farm_id": user_farm_id,
                                                    "account_id": account,
                                                    "tokens": str(farm_unclaimed_tokens),
                                                    "token_amounts": str(farm_unclaimed_amounts),
                                                    "token_decimals": str(farm_unclaimed_decimals),
                                                    "token_prices": str(farm_unclaimed_prices),
                                                    "amount": str(farm_unclaimed_count_amount)}
                                account_assets_data_list.append(farm_assets_data)
        if "dcl_user_assets" in file:
            with open(full_filename, 'r') as fi:
                dcl_user_assets = json.load(fi)
                for dcl_account, dcl_account_data in dcl_user_assets.items():
                    dcl_user_count_amount = 0
                    dcl_pool_tokens = []
                    dcl_pool_amounts = []
                    dcl_pool_decimals = []
                    dcl_pool_prices = []
                    for dcl_token, dcl_amount in dcl_account_data.items():
                        dcl_pool_tokens.append(dcl_token)
                        dcl_pool_amounts.append(dcl_amount)
                        if dcl_token in tokens_price:
                            token_price = float(tokens_price[dcl_token]["price"])
                            token_decimal = tokens_price[dcl_token]["decimal"]
                            dcl_pool_decimals.append(token_decimal)
                            dcl_pool_prices.append(token_price)
                            dis = int("1" + "0" * token_decimal)
                            dcl_user_amount = dcl_amount / dis * token_price
                            dcl_user_count_amount = dcl_user_count_amount + dcl_user_amount
                        else:
                            dcl_pool_decimals.append(0)
                            dcl_pool_prices.append(0)
                    dcl_account_assets_data = {"type": "dcl_account_assets", "pool_id": "",
                                               "farm_id": "",
                                               "account_id": dcl_account,
                                               "tokens": str(dcl_pool_tokens),
                                               "token_amounts": str(dcl_pool_amounts),
                                               "token_decimals": str(dcl_pool_decimals),
                                               "token_prices": str(dcl_pool_prices),
                                               "amount": str(float_to_str(dcl_user_count_amount))}
                    account_assets_data_list.append(dcl_account_assets_data)
        if "dcl_user_liquidities" in file:
            with open(full_filename, 'r') as fi:
                dcl_user_liquidities = json.load(fi)
                for dcl_liquidity_account, dcl_liquidity_account_data in dcl_user_liquidities.items():
                    dcl_user_liquidity_count_amount = 0
                    dcl_user_pool_count_amount = 0
                    dcl_pool_liquidity_tokens = []
                    dcl_pool_liquidity_amounts = []
                    dcl_pool_liquidity_decimals = []
                    dcl_pool_liquidity_prices = []
                    dcl_pool_assets_amounts = []
                    for lpt_id, dcl_liquidity_data in dcl_liquidity_account_data.items():
                        pool_id = str(dcl_liquidity_data["pool_id"])
                        current_point = dcl_pool_data_list[pool_id]["current_point"]
                        liquidity = dcl_pool_data_list[pool_id]["liquidity"]
                        liquidity_x = dcl_pool_data_list[pool_id]["liquidity_x"]
                        unclaimed_fee_x = int(dcl_liquidity_data["unclaimed_fee_x"])
                        unclaimed_fee_y = int(dcl_liquidity_data["unclaimed_fee_y"])
                        dcl_pool_token_list = pool_id.split("|")
                        token_x = dcl_pool_token_list[0]
                        token_y = dcl_pool_token_list[1]
                        dcl_pool_liquidity_tokens.append(token_x)
                        dcl_pool_liquidity_tokens.append(token_y)
                        dcl_pool_liquidity_amounts.append(unclaimed_fee_x)
                        dcl_pool_liquidity_amounts.append(unclaimed_fee_y)
                        if token_x in tokens_price:
                            token_price = float(tokens_price[token_x]["price"])
                            token_decimal = tokens_price[token_x]["decimal"]
                            dcl_pool_liquidity_decimals.append(token_decimal)
                            dcl_pool_liquidity_prices.append(token_price)
                            dis = int("1" + "0" * token_decimal)
                            dcl_user_liquidity_amount = unclaimed_fee_x / dis * token_price
                            dcl_user_liquidity_count_amount = dcl_user_liquidity_count_amount + dcl_user_liquidity_amount
                        else:
                            dcl_pool_liquidity_decimals.append(0)
                            dcl_pool_liquidity_prices.append(0)
                        if token_y in tokens_price:
                            token_price = float(tokens_price[token_y]["price"])
                            token_decimal = tokens_price[token_y]["decimal"]
                            dcl_pool_liquidity_decimals.append(token_decimal)
                            dcl_pool_liquidity_prices.append(token_price)
                            dis = int("1" + "0" * token_decimal)
                            dcl_user_liquidity_amount = unclaimed_fee_y / dis * token_price
                            dcl_user_liquidity_count_amount = dcl_user_liquidity_count_amount + dcl_user_liquidity_amount
                        else:
                            dcl_pool_liquidity_decimals.append(0)
                            dcl_pool_liquidity_prices.append(0)
                        pool_liquidity_amount_data = get_liquidity_x_y(current_point, dcl_liquidity_data["left_point"],
                                                                       dcl_liquidity_data["right_point"],
                                                                       dcl_liquidity_data["amount"],
                                                                       liquidity, liquidity_x, tokens_price[token_x],
                                                                       tokens_price[token_y])
                        dcl_pool_assets_amounts.append(pool_liquidity_amount_data["token_x_amount"])
                        dcl_pool_assets_amounts.append(pool_liquidity_amount_data["token_y_amount"])
                        dcl_user_pool_count_amount = dcl_user_pool_count_amount + pool_liquidity_amount_data[
                            "token_x_amount"] * float(tokens_price[token_x]["price"])
                        dcl_user_pool_count_amount = dcl_user_pool_count_amount + pool_liquidity_amount_data[
                            "token_y_amount"] * float(tokens_price[token_y]["price"])
                        print("pool_liquidity_amount_data:", pool_liquidity_amount_data)

                    dcl_account_assets_data = {"type": "dcl_unclaimed_fee_assets", "pool_id": pool_id,
                                               "farm_id": "",
                                               "account_id": dcl_liquidity_account,
                                               "tokens": str(dcl_pool_liquidity_tokens),
                                               "token_amounts": str(dcl_pool_liquidity_amounts),
                                               "token_decimals": str(dcl_pool_liquidity_decimals),
                                               "token_prices": str(dcl_pool_liquidity_prices),
                                               "amount": str(float_to_str(dcl_user_liquidity_count_amount))}
                    account_assets_data_list.append(dcl_account_assets_data)
                    dcl_account_assets_data = {"type": "dcl_pool_assets", "pool_id": pool_id,
                                               "farm_id": "",
                                               "account_id": dcl_liquidity_account,
                                               "tokens": str(dcl_pool_liquidity_tokens),
                                               "token_amounts": str(dcl_pool_assets_amounts),
                                               "token_decimals": str(dcl_pool_liquidity_decimals),
                                               "token_prices": str(dcl_pool_liquidity_prices),
                                               "amount": str(float_to_str(dcl_user_pool_count_amount))}
                    account_assets_data_list.append(dcl_account_assets_data)
        if "xref_accounts" in file:
            with open(full_filename, 'r') as fi:
                xref_accounts_data = json.load(fi)
                xref_token = "xtoken.ref-finance.near"
                for xref_account, xref_amount in xref_accounts_data.items():
                    xref_price = float(tokens_price[xref_token]["price"])
                    xref_decimal = tokens_price[xref_token]["decimal"]
                    xref_tokens = []
                    xref_amounts = []
                    xref_decimals = []
                    xref_prices = []
                    xref_tokens.append(xref_token)
                    xref_amounts.append(xref_amount)
                    xref_decimals.append(xref_decimal)
                    xref_prices.append(xref_price)
                    dis = int("1" + "0" * xref_decimal)
                    xref_count_amount = xref_amount / dis * xref_price
                    xref_assets_data = {"type": "xref_assets", "pool_id": "",
                                        "farm_id": "",
                                        "account_id": xref_account,
                                        "tokens": str(xref_tokens),
                                        "token_amounts": str(xref_amounts),
                                        "token_decimals": str(xref_decimals),
                                        "token_prices": str(xref_prices),
                                        "amount": str(float_to_str(xref_count_amount))}
                    account_assets_data_list.append(xref_assets_data)
        if len(account_assets_data_list) > 0:
            add_account_assets_data(account_assets_data_list)
            # print("account_assets_data_list:", account_assets_data_list)

    return path_to_jsonfiles


def get_liquidity_x_y(current_point, left_point, right_point, amount, liquidity, liquidity_x, token_x, token_y):
    ret_data = {
        "token_x_amount": 0,
        "token_y_amount": 0
    }
    if left_point <= current_point < right_point:
        token_x_amount = get_x(current_point + 1, right_point, amount, token_x)
        token_y_amount = get_y(left_point, current_point, amount, token_y)
        token_amount_data = get_x_y_in_current_point(liquidity, liquidity_x, current_point, amount, token_x, token_y)
        ret_data["token_x_amount"] = token_x_amount + token_amount_data["token_x"]
        ret_data["token_y_amount"] = token_y_amount + token_amount_data["token_y"]
        return ret_data
    if current_point >= right_point:
        ret_data["token_y_amount"] = get_y(left_point, right_point, amount, token_y)
        return ret_data
    if left_point > current_point:
        ret_data["token_x_amount"] = get_x(left_point, right_point, amount, token_x)
        return ret_data


def get_y(left_point, right_point, amount, token):
    token_y_amount = round(amount * (
            (math.pow(math.sqrt(CONSTANT_D), right_point) - math.pow(math.sqrt(CONSTANT_D), left_point)) / (
            math.sqrt(CONSTANT_D) - 1)))
    dis = int("1" + "0" * token["decimal"])
    y = token_y_amount / dis
    return y


def get_x(left_point, right_point, amount, token):
    token_x_amount = round(amount * ((math.pow(math.sqrt(CONSTANT_D), right_point - left_point) - 1) / (
            math.pow(math.sqrt(CONSTANT_D), right_point) - math.pow(math.sqrt(CONSTANT_D), right_point - 1))))
    dis = int("1" + "0" * token["decimal"])
    x = token_x_amount / dis
    return x


def get_x_y_in_current_point(liquidity, liquidity_x, current_point, amount, token_x, token_y):
    liquidity_y_big = liquidity - liquidity_x
    l_y = 0
    l_x = 0
    if liquidity_y_big >= amount:
        l_y = amount
    else:
        l_y = round(liquidity_y_big)
        l_x = round(amount - l_y)
    amount_x = get_x_amount_per_point_by_lx(l_x, current_point)
    amount_y = get_y_amount_per_point_by_lx(l_y, current_point)
    x_dis = int("1" + "0" * token_x["decimal"])
    amount_x_read = amount_x / x_dis
    y_dis = int("1" + "0" * token_y["decimal"])
    amount_y_read = amount_y / y_dis
    ret_data = {
        "token_x": amount_x_read,
        "token_y": amount_y_read
    }
    return ret_data


def get_x_amount_per_point_by_lx(amount, point):
    x_amount = round(amount / (math.pow(math.sqrt(CONSTANT_D), point)))
    return x_amount


def get_y_amount_per_point_by_lx(amount, point):
    x_amount = round(amount * (math.pow(math.sqrt(CONSTANT_D), point)))
    return x_amount


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

    # folder_path = add_data_to_db("height_7", "MAINNET")
    # print("start clear_folder")
    # clear_folder(folder_path)
    # print("start handle_account_pool_assets_data")
    # handle_account_pool_assets_data("MAINNET")
    # print("analysis_pool_and_farm_data end")
