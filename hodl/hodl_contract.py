from electroncash.bitcoin import regenerate_key, MySigningKey, Hash
from electroncash.address import Address, Script, OpCodes as Op
from electroncash.transaction import Transaction,TYPE_ADDRESS
import ecdsa
from .contract import Contract
from math import ceil
import struct

import time
LOCKTIME_THRESHOLD = 500000000
UTXO=0
CONTRACT=1
MODE=2
SELF = 0


def joinbytes(iterable):
    """Joins an iterable of bytes and/or integers into a single byte string"""
    return b''.join((bytes((x,)) if isinstance(x,int) else x) for x in iterable)

def len_bytes(value):
    if isinstance(value, int):
        return (value.bit_length() + 7) // 8

    raise "Unsupported data type"


class HodlContract(Contract):
    """Hodl Contract implementation"""
    def __init__(self, addresses, initial_tx=None,v=0, data=None):
        Contract.__init__(self, addresses,initial_tx,v)
        try:
            self.i_time = data[0]
        except:
            self.i_time = 0

        self.i_time_len = len_bytes(self.i_time)
        self.i_time_bytes = self.i_time.to_bytes(self.i_time_len, 'little')

        assert self.i_time >= 0
        assert len(self.i_time_bytes) == self.i_time_len

        self.redeemscript_v1 = joinbytes([
            self.i_time_len, self.i_time_bytes,
            Op.OP_CHECKLOCKTIMEVERIFY, Op.OP_DROP,
            Op.OP_DUP, Op.OP_HASH160,
            Script.push_data(addresses[0].hash160),
            Op.OP_EQUALVERIFY, Op.OP_CHECKSIG
        ])

        self.redeemscript=self.redeemscript_v1
        self.set_version(v)
        self.address = Address.from_multisig_script(self.redeemscript)
        data1 = self.address.to_ui_string() + ' ' + str(self.version)
        data2 = str(self.i_time)
        self.op_return = joinbytes(
            [Op.OP_RETURN, 4, self.op_return_signature().encode('utf8'), len(data1), data1.encode('utf8'), len(data2), data2.encode('utf8')])

    def __eq__(self, o) -> bool:
        return self.i_time == o.i_time and \
            self.address == o.address and \
            self.addresses[0] == o.addresses[0]

    @staticmethod
    def op_return_signature():
        """4 byte string to distinguish the contract"""
        return "hodl"

    @staticmethod
    def participants(version):
        return 1

    @staticmethod
    def fee(version):
        """Top fee estimate"""
        return 1000

    def set_version(self, v):
        self.version = 1
        self.redeemscript = self.redeemscript_v1


class ContractManager:
    """A device that spends from a Mecenas Contract in two different ways."""
    def __init__(self, contract_tuple_list, keypairs, public_keys, wallet):
        self.contract_tuple_list = contract_tuple_list
        self.contract_index=0
        self.chosen_utxo = 0
        self.sequence = 0
        self.txin = dict()
        self.keypair = keypairs
        self.pubkeys = public_keys
        self.wallet = wallet

        if len(self.contract_tuple_list):
            self.choice(self.contract_tuple_list[0], 0, 0)

    def choice(self, contract_tuple, utxo_index, m):
        self.tx = contract_tuple[UTXO][utxo_index]
        self.contract = contract_tuple[CONTRACT]
        self.mode = m
        self.dummy_scriptsig = '00'*(110 + len(self.contract.redeemscript))
        self.version = self.contract.version
        self.script_pub_key = Script.P2SH_script(self.contract.address.hash160).hex()
        self.value = int(self.tx.get('value'))

        self.txin=[]
        self.chosen_utxo=utxo_index
        self.contract_index = self.contract_tuple_list.index(contract_tuple)

        self.sequence = 0

        utxo = contract_tuple[UTXO][utxo_index]

        self.value = int(utxo.get('value'))
        self.txin = [dict(
            prevout_hash=utxo.get('tx_hash'),
            prevout_n=int(utxo.get('tx_pos')),
            # sequence=self.sequence,
            scriptSig=self.dummy_scriptsig,
            type='unknown',
            address=self.contract.address,
            scriptCode=self.contract.redeemscript.hex(),
            num_sig=1,
            signatures=[None],
            x_pubkeys=[self.pubkeys[self.contract_index][self.mode]],
            value=int(utxo.get('value')),
        )]

    def complete_method(self, action='default'):
        return self.complete

    def signtx(self, tx):
        """generic tx signer for compressed pubkey"""
        tx.sign(self.keypair)

    def complete(self, tx):
        """
        Completes transaction by creating scriptSig. You need to sign the
        transaction before using this (see `signtx`).
        This works on multiple utxos if needed.
        """
        pub = bytes.fromhex(self.pubkeys[self.contract_index][self.mode])
        for txin in tx.inputs():
            # find matching inputs
            if txin['address'] != self.contract.address:
                continue
            sig = txin['signatures'][0]
            if not sig:
                continue
            sig = bytes.fromhex(sig)

            if txin['scriptSig'] == self.dummy_scriptsig:
                script = [
                    Script.push_data(sig),
                    Script.push_data(pub),
                    Script.push_data(self.contract.redeemscript)
                    ]
                # print("scriptSig length " + str(joinbytes(script).hex().__sizeof__()))
                txin['scriptSig'] = joinbytes(script).hex()
        # need to update the raw, otherwise weird stuff happens.
        tx.raw = tx.serialize()

    def spend_tx(self, inputs):
        """
        Prepares a raw unsigned transaction to spend smart contract
        Inputs are provided as parameter
        Output is a P2PKH address specified (commonly random) upon contract creation
        Fee is calculated with a target of 1 sat/byte
        """
        outputs = [
            (TYPE_ADDRESS, self.contract.addresses[SELF], self.value)]

        tx = Transaction.from_io(inputs, outputs, locktime=self.contract.i_time)
        tx.version = 2
        fee = (len(tx.serialize(True)) // 2 + 1)
        if fee > self.value:
            raise Exception("Not enough funds to make the transaction!")
        outputs = [
            (TYPE_ADDRESS, self.contract.addresses[SELF], self.value - fee)]
        tx = Transaction.from_io(inputs, outputs, locktime=self.contract.i_time)
        tx.version = 2
        return tx
