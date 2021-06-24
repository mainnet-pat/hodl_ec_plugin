import queue
from .hodl_contract import HodlContract
from electroncash import util
from electroncash.address import Address, ScriptOutput
from itertools import permutations, combinations

def synchronous_get_many(network, requests):
    """ modified synchrronous_get to handle batched requests """
    responses = []

    q = queue.Queue()
    network.send(requests, q.put)
    try:
        for _ in range(0, len(requests)):
            response = q.get(True, 30)
            if response.get('error'):
                raise util.ServerError(response.get('error'))
            responses.append(response)
    except queue.Empty:
        raise util.TimeoutException('Server did not answer')

    return responses

def find_contract_in_wallet(wallet, contract_cls: HodlContract):
    contract_tuple_list=[]
    requests = []
    contract_map = {}

    for hash, t in wallet.transactions.items():
        contract = scan_transaction(t, contract_cls)
        if contract is None:
            continue

        contract_map[contract.address.to_scripthash_hex()] = contract
        requests.append(("blockchain.scripthash.listunspent", [contract.address.to_scripthash_hex()]))

    try:
        responses = synchronous_get_many(wallet.network, requests)
    except Exception as e:
        print(e)
        responses = []

    for response in responses:
        if unfunded_contract(response['result']):  # skip unfunded and ended contracts
            continue

        contract = contract_map[response['params'][0]]

        a=contract.addresses
        # print("hello there", contract.address.to_ui_string())
        contract_tuple_list.append((response['result'], contract, find_my_role(a, wallet)))

    remove_duplicates(contract_tuple_list)
    return contract_tuple_list

def remove_duplicates(contracts):
    c = contracts
    for c1, c2 in combinations(contracts,2):
        if c1[1].address == c2[1].address:
            c.remove(c1)
    return c


def unfunded_contract(r):
    """Checks if the contract is funded"""
    s = False
    if len(r) == 0:
        s = True
    for t in r:
        if t.get('value') == 0: # when contract was drained it's still in utxo
            s = True
    return s


def scan_transaction(tx, contract_cls: HodlContract):
    out = tx.outputs()
    address, v, data  = parse_p2sh_notification(out, contract_cls)
    if address is None or v is None or data is None:
        return
    no_participants = contract_cls.participants(v)
    if no_participants > (len(out)+1):
        return None
    candidates = get_candidates(out[1:], no_participants)
    for c in candidates:
        contract = contract_cls(c,tx.as_dict(),v=v, data=data)
        if contract.address.to_ui_string() == address:
            return contract


def parse_p2sh_notification(outputs, contract_cls: HodlContract):
    opreturn = outputs[0]
    try:
        assert isinstance(opreturn[1], ScriptOutput)
        assert opreturn[1].to_ui_string().split(",")[1] == f" (4) '{contract_cls.op_return_signature()}'"
        a = opreturn[1].to_ui_string().split("'")[3][:42]
        version = float(opreturn[1].to_ui_string().split("'")[3][42:])
        data = [int(e) for e in opreturn[1].to_ui_string().split("'")[5].split(' ')]
        return Address.from_string(a).to_ui_string(), version, data
    except:
        return None, None, None


def get_candidates(outputs, participants):
    """Creates all permutations of addresses that are not p2sh type"""
    candidates = []
    for o in permutations(outputs, participants):
        kinds = [i[1].kind for i in o]
        if 1 in kinds:
            continue
        addresses = [i[1] for i in o]
        candidates.append(addresses)
    return candidates


def find_my_role(candidates, wallet):
    return [0]
