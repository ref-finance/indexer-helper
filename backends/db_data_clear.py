import sys
sys.path.append('../')

import sys
from db_provider import clear_token_price


def clear_db_data():
    try:
        clear_token_price()
    except Exception as e:
        print("Error occurred when clear db data, Error is: ", e)


if __name__ == '__main__':
    # update_price("TESTNET")
    if len(sys.argv) == 2:
        network_id = str(sys.argv[1]).upper()
        if network_id in ["MAINNET", "TESTNET", "DEVNET"]:
            clear_db_data()
        else:
            print("Error, network_id should be MAINNET, TESTNET or DEVNET")
            exit(1)
    else:
        print("Error, must put NETWORK_ID as arg")
        exit(1)
