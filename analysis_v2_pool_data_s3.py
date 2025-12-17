import json
import sys
import time
from db_info import BUCKET_NAME
import boto3
import os
sys.path.append('/')
from db_provider import add_v2_pool_data, add_dcl_user_liquidity_data, add_dcl_user_liquidity_fee_data

s3 = boto3.client('s3')


def add_data_to_db(file_name, network_id):
    now_time = int(time.time())
    # file_name = "C:\\Users\\86176\Desktop\\v2_pool_analysis\\" + file_name
    v2_pool_data_list = []
    pool_id_list = []
    with open(file_name, 'r') as fi:
        pool_dict = json.load(fi)
        for pool_id, pool_data in pool_dict.items():
            pool_id_list.append(pool_id)
            for point, point_data in pool_data.items():
                v2_pool_data = {"pool_id": pool_id, "point": point, "fee_x": point_data["fee_x"],
                                "fee_y": point_data["fee_y"], "l": point_data["l"],
                                "tvl_x_l": point_data["tvl_x_l"], "tvl_x_o": point_data["tvl_x_o"],
                                "tvl_y_l": point_data["tvl_y_l"], "tvl_y_o": point_data["tvl_y_o"],
                                "vol_x_in_l": point_data["vol_x_in_l"], "vol_x_in_o": point_data["vol_x_in_o"],
                                "vol_x_out_l": point_data["vol_x_out_l"], "vol_x_out_o": point_data["vol_x_out_o"],
                                "vol_y_in_l": point_data["vol_y_in_l"], "vol_y_in_o": point_data["vol_y_in_o"],
                                "vol_y_out_l": point_data["vol_y_out_l"], "vol_y_out_o": point_data["vol_y_out_o"],
                                "p_fee_x": point_data["p_fee_x"], "p_fee_y": point_data["p_fee_y"],
                                "p": point_data["p"], "cp": point_data["cp"], "timestamp": now_time,
                                }
                v2_pool_data_list.append(v2_pool_data)
    add_v2_pool_data(v2_pool_data_list, network_id, pool_id_list)


def add_dcl_user_liquidity_to_db(file_name, network_id):
    now_time = int(time.time())
    # file_name = "C:\\Users\\86176\Desktop\\v2_pool_analysis\\20230609\\" + file_name
    dcl_user_liquidity_data_list = []
    with open(file_name, 'r') as fi:
        user_dict = json.load(fi)
        for account_id, user_data in user_dict.items():
            for pool_id, pool_data in user_data.items():
                for point, point_data in pool_data.items():
                    v2_pool_data = {"pool_id": pool_id, "account_id": account_id, "point": point, "l": point_data["l"],
                                    "tvl_x_l": point_data["tvl_x_l"], "tvl_y_l": point_data["tvl_y_l"],
                                    "p": point_data["p"], "timestamp": now_time,
                                    }
                    dcl_user_liquidity_data_list.append(v2_pool_data)
    add_dcl_user_liquidity_data(dcl_user_liquidity_data_list, network_id)


def add_dcl_user_liquidity_fee_to_db(file_name, network_id):
    now_time = int(time.time())
    # file_name = "C:\\Users\\86176\Desktop\\v2_pool_analysis\\20230609\\" + file_name
    dcl_user_liquidity_fee_data_list = []
    with open(file_name, 'r') as fi:
        dcl_user_liquidity = json.load(fi)
        for dcl_liquidity_account, dcl_liquidity_account_data in dcl_user_liquidity.items():
            pool_fee_data = {}
            for lpt_id, dcl_liquidity_data in dcl_liquidity_account_data.items():
                pool_id = str(dcl_liquidity_data["pool_id"])
                unclaimed_fee_x = int(dcl_liquidity_data["unclaimed_fee_x"])
                unclaimed_fee_y = int(dcl_liquidity_data["unclaimed_fee_y"])
                if pool_id in pool_fee_data:
                    pool_fee_data[pool_id]["unclaimed_fee_x"] = pool_fee_data[pool_id]["unclaimed_fee_x"] + unclaimed_fee_x
                    pool_fee_data[pool_id]["unclaimed_fee_y"] = pool_fee_data[pool_id]["unclaimed_fee_y"] + unclaimed_fee_y
                else:
                    pool_fee_data[pool_id] = {
                        "unclaimed_fee_x": unclaimed_fee_x,
                        "unclaimed_fee_y": unclaimed_fee_y,
                    }
            for pool_id, pool_fee in pool_fee_data.items():
                dcl_user_liquidity_fee_data = {"pool_id": pool_id,
                                               "account_id": dcl_liquidity_account,
                                               "unclaimed_fee_x": pool_fee["unclaimed_fee_x"],
                                               "unclaimed_fee_y": pool_fee["unclaimed_fee_y"],
                                               "timestamp": now_time}
                dcl_user_liquidity_fee_data_list.append(dcl_user_liquidity_fee_data)
    add_dcl_user_liquidity_fee_data(dcl_user_liquidity_fee_data_list, network_id)


def download_file_s3(file_name):
    loc = file_name.find('/') + 1
    path_local = "./" + file_name[loc:len(file_name)]
    loc1 = path_local.split("/")
    path_local_folder_name = loc1[1]
    if not os.path.exists("./" + path_local_folder_name):
        os.mkdir(path_local_folder_name)
    download_file_local(file_name, path_local)
    return path_local


def download_file_local(object_name, file_name):
    s3.download_file(BUCKET_NAME, object_name, file_name)


def cleanup_local_file(file_path):
    try:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
        folder = os.path.dirname(file_path)
        if folder and folder != "." and os.path.exists(folder) and not os.listdir(folder):
            os.rmdir(folder)
    except OSError as exc:
        print(f"cleanup_local_file error: {exc}")


def analysis_v2_pool_data_to_s3(file_name, network_id):
    file_path = download_file_s3(file_name)
    try:
        add_data_to_db(file_path, network_id)
    finally:
        cleanup_local_file(file_path)


def analysis_v2_pool_account_data_to_s3(file_name, network_id):
    file_path = download_file_s3(file_name)
    try:
        add_dcl_user_liquidity_to_db(file_path, network_id)
    finally:
        cleanup_local_file(file_path)

    file_name_f = file_name.replace("dcl_user_liquidity_stats", "dcl_user_liquidities")
    file_path_f = download_file_s3(file_name_f)
    try:
        add_dcl_user_liquidity_fee_to_db(file_path_f, network_id)
    finally:
        cleanup_local_file(file_path_f)


if __name__ == "__main__":
    print("#########analysis_v2_pool_data start###########")
    # analysis_v2_pool_data_to_s3("output/height_91440568/dcl_endpoint_stats.json", "MAINNET")
    # add_dcl_user_liquidity_to_db("output/height_93807302/dcl_user_liquidity_stats.json", "MAINNET")
    # analysis_v2_pool_account_data_to_s3("output/height_95081475/dcl_user_liquidity_stats.json", "MAINNET")
    # add_dcl_user_liquidity_fee_to_db("dcl_user_liquidities.json", "MAINNET")
    add_data_to_db("dcl_endpoint_stats.json", "MAINNET")
    print("#########analysis_v2_pool_data end###########")
