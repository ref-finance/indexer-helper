import boto3
import os
import json
import shutil
import sys
sys.path.append('../')
from db_provider import add_pool_assets_data, get_token_price, handle_account_pool_assets_data
import decimal


AWS_REGION_NAME = 'us-east-1'  # 区域

'''
BUCKET_NAME = "stateparser-bucket"  # Dev存储桶名称
AWS_S3_AKI = 'AKIAYQWJUBPWS5CMQOVZ' #aws_access_key_id
AWS_S3_SAK = 'D3aMuKhGR6lx1fCzocZa7bd4pSqg2/EaSWB2QZIy' #aws_secret_access_key
'''

BUCKET_NAME = "prod-stateparser-bucket"  # Prod存储桶名称
AWS_S3_AKI = 'AKIAQVRJFS5CVPUL4KVM'  # aws_access_key_id
AWS_S3_SAK = '5/fHaluNWA841u0jco1qLgk6ArzlwAuoyLMvfxRJ'  # aws_secret_access_key

# s3 实例
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
        if "ex_pool" in file_name or "farm_accounts" in file_name or "farm_seeds" in file_name or "farmv2_accounts" in file_name or "farmv2_seeds" in file_name:
            loc = file_name.find('/') + 1
            path_local = "./" + file_name[loc:len(file_name)]
            print(path_local)
            download_file_local(file_name, path_local)
    return block_height_folder_name


def add_data_to_db(block_height_folder_name):
    import re
    # path_to_jsonfiles = "C:\\Users\\sjl\\Desktop\\portfolio\\" + block_height_folder_name
    path_to_jsonfiles = "/www/wwwroot/mainnet-indexer.ref-finance.com/indexer-helper/backends/" + block_height_folder_name
    tokens_price = get_token_price()
    for file in os.listdir(path_to_jsonfiles):
        pool_assets_data_list = []
        full_filename = "%s/%s" % (path_to_jsonfiles, file)
        with open(full_filename, 'r') as fi:
            dict = json.load(fi)
            if "ex_pool" in file:
                pool_id = str(re.findall("ex_pool_(.*?).json", file)[0])
                pool_shares = dict["shares"]
                pool_shares_total_supply = dict["shares_total_supply"]
                token_account_ids = dict["token_account_ids"]
                pool_amounts = dict["amounts"]
                for account, amount in pool_shares.items():
                    token_data = count_account_amount(tokens_price, pool_amounts, pool_shares_total_supply, amount, token_account_ids)
                    pool_assets_data = {"pool_id": pool_id, "account_id": account,
                                        "tokens": str(dict["token_account_ids"]), "token_amounts": token_data["token_amounts"],
                                        "token_decimals": token_data["token_decimals"],
                                        "token_prices": token_data["token_prices"], "amount": token_data["amount"]}
                    pool_assets_data_list.append(pool_assets_data)
        if len(pool_assets_data_list) > 0:
            add_pool_assets_data(pool_assets_data_list)
            # print("pool_assets_data_list", pool_assets_data_list)
    return path_to_jsonfiles


def count_account_amount(tokens_price, pool_amounts, pool_shares_total_supply, amount, token_account_ids):
    count_amount = 0
    token_decimals = []
    token_prices = []
    token_amounts = []
    for i in range(0, len(pool_amounts)):
        token_amount = amount * pool_amounts[i] / pool_shares_total_supply
        token_amounts.append(float_to_str(token_amount))
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
    if len(sys.argv) == 2:
        network_id = str(sys.argv[1]).upper()
        if network_id in ["MAINNET", "TESTNET", "DEVNET"]:
            height_folder_name = download_file_s3()
            print("start add_data_to_db")
            folder_path = add_data_to_db(height_folder_name)
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

    # folder_path = add_data_to_db("height_7")
    # print("start clear_folder")
    # clear_folder(folder_path)
    # print("start handle_account_pool_assets_data")
    # handle_account_pool_assets_data("MAINNET")
    # print("analysis_pool_and_farm_data end")

