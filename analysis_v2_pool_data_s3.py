import json
import sys
import time
from db_info import BUCKET_NAME_TEST, AWS_S3_AKI_TEST, AWS_S3_SAK_TEST, AWS_REGION_NAME_TEST
import boto3
import os
sys.path.append('/')
from db_provider import add_v2_pool_data

s3 = boto3.client('s3', region_name=AWS_REGION_NAME_TEST, aws_access_key_id=AWS_S3_AKI_TEST, aws_secret_access_key=AWS_S3_SAK_TEST)


def add_data_to_db(file_name, network_id):
    now_time = int(time.time())
    # file_path = "C:\\Users\\86176\Desktop\\v2_pool_analysis\\123\\" + file_name
    # path_to_jsonfiles = Cfg.NETWORK[network_id]["BLOCK_HEIGHT_FOLDER_PATH"] + block_height_folder_name
    v2_pool_data_list = []
    with open(file_name, 'r') as fi:
        pool_dict = json.load(fi)
        for pool_id, pool_data in pool_dict.items():
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
                                "p": point_data["p"], "timestamp": now_time,
                                }
                v2_pool_data_list.append(v2_pool_data)
    add_v2_pool_data(v2_pool_data_list, network_id)


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
    s3.download_file(BUCKET_NAME_TEST, object_name, file_name)


def analysis_v2_pool_data_to_s3(file_name, network_id):
    file_path = download_file_s3(file_name)
    add_data_to_db(file_path, network_id)


if __name__ == "__main__":
    print("#########analysis_v2_pool_data start###########")
    analysis_v2_pool_data_to_s3("output/height_91440568/dcl_endpoint_stats.json", "TESTNET")
    print("#########analysis_v2_pool_data end###########")
