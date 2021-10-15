import requests
import base64
import json

from config import Cfg


class MultiNodeJsonProviderError(Exception):
    pass


class MultiNodeJsonProvider(object):

    def __init__(self, network_id):
        nodes = Cfg.NETWORK[network_id]["NEAR_RPC_URL"]
        best_height = 0
        best_node = None
        for node in nodes:
            self._rpc_addr = node
            node_status = self.ping_node()
            print(node, node_status)
            if not node_status['syncing'] and node_status['latest_block_height'] > best_height + 10:
                best_height = node_status['latest_block_height']
                best_node = node
        if best_node is not None:
            print("Choose near rpc node", best_node)
            self._rpc_addr = best_node
        else:
            raise MultiNodeJsonProviderError("No available nodes")

    def rpc_addr(self):
        return self._rpc_addr

    def json_rpc(self, method, params, timeout=2):
        j = {
            'method': method,
            'params': params,
            'id': 'dontcare',
            'jsonrpc': '2.0'
        }
        r = requests.post(self.rpc_addr(), json=j, timeout=timeout)
        r.raise_for_status()
        content = json.loads(r.content)
        if "error" in content:
            raise MultiNodeJsonProviderError(content["error"])
        return content["result"]

    def send_tx(self, signed_tx):
        return self.json_rpc('broadcast_tx_async', [base64.b64encode(signed_tx).decode('utf8')])

    def send_tx_and_wait(self, signed_tx, timeout):
        return self.json_rpc('broadcast_tx_commit', [base64.b64encode(signed_tx).decode('utf8')], timeout=timeout)

    def get_status(self):
        return self.json_rpc('status', [None])

    def get_validators(self):
        return self.json_rpc('validators', [None])

    def query(self, query_object):
        return self.json_rpc('query', query_object)

    def get_account(self, account_id, finality='optimistic'):
        return self.json_rpc('query', {"request_type": "view_account", "account_id": account_id, "finality": finality})

    def get_access_key_list(self, account_id, finality='optimistic'):
        return self.json_rpc('query', {"request_type": "view_access_key_list", "account_id": account_id, "finality": finality})

    def get_access_key(self, account_id, public_key, finality='optimistic'):
        return self.json_rpc('query', {"request_type": "view_access_key", "account_id": account_id,
                                       "public_key": public_key, "finality": finality})

    def view_call(self, account_id, method_name, args, finality='optimistic'):
        return self.json_rpc('query', {"request_type": "call_function", "account_id": account_id,
                                       "method_name": method_name, "args_base64": base64.b64encode(args).decode('utf8'), "finality": finality})

    def get_block(self, block_id):
        return self.json_rpc('block', [block_id])

    def get_chunk(self, chunk_id):
        return self.json_rpc('chunk', [chunk_id])

    def get_tx(self, tx_hash, tx_recipient_id):
        return self.json_rpc('tx', [tx_hash, tx_recipient_id])

    def get_changes_in_block(self, changes_in_block_request):
        return self.json_rpc('EXPERIMENTAL_changes_in_block', changes_in_block_request)

    def ping_node(self):
        ret = {'latest_block_height': 0, 'syncing': True}

        try:
            status = self.get_status()
            if "sync_info" in status:
                ret['latest_block_height'] = status['sync_info']['latest_block_height']
                ret['syncing'] = status['sync_info']['syncing']
        except MultiNodeJsonProviderError as e:
            print("ping node MultiNodeJsonProviderError: ", e)
        except Exception as e:
            print("ping node Exception: ", e)
    
        return ret

if __name__ == "__main__":
    conn = MultiNodeJsonProvider("MAINNET")

    status = conn.get_status()
    if "version" in status:
        print(status["version"])
    if "sync_info" in status:
        print(status['sync_info'])
